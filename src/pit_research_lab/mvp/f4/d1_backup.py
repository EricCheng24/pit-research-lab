"""Snapshot-bound backup and a fixed Owner-only PostgreSQL 17 client adapter."""

import json
import os
import re
import subprocess
from collections.abc import Callable
from decimal import Decimal
from pathlib import Path
from typing import Any

from psycopg import sql

from pit_research_lab.infrastructure.database.config import IMAGE

from .d1_custody import custody_lock, publish, put_blob, read_blob
from .d1_profile import (
    Refusal,
    Target,
    decode,
    digest,
    json_bytes,
    private_read,
    profile_body,
    require,
    sha,
    timestamp,
)
from .d1_records import classified, counts
from .d1_store import (
    ATTEMPT_LOCK,
    DB,
    TABLES,
    VIEWS,
    connect,
    grants,
    inventory,
    lock_all,
    projection,
    public_value,
    read_receipt,
    revision,
    table,
)

SEQUENCE = "observation_ordinal_seq"
DUMP_LIMIT = 64 * 1024 * 1024
MANIFEST_LIMIT = 2 * 1024 * 1024
# The only shell fragment is constant. The password crosses the pipe, never argv.
CLIENT_SCRIPT = (
    'IFS= read -r PGPASSWORD || exit 1; export PGPASSWORD; export PGCONNECT_TIMEOUT=5; exec "$@"'
)


class OwnerClient:
    def __init__(self, target: Target, container: str) -> None:
        require(target.role == "migrator", "MAINTENANCE_ROLE_REQUIRED")
        require(re.fullmatch(r"[0-9a-f]{64}", container), "EXACT_CONTAINER_ID_REQUIRED")
        require(
            not any(k.startswith("DOCKER_") for k in os.environ),
            "AMBIENT_DOCKER_OVERRIDE",
        )
        self.target = target
        self.container = container

    def _run(self, args: list[str], raw: bytes | None = None) -> bytes:
        try:
            result = subprocess.run(
                ["docker", *args],
                input=raw,
                capture_output=True,
                timeout=90,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            raise Refusal("OWNER_CLIENT_UNAVAILABLE") from None
        require(
            result.returncode == 0 and len(result.stdout) <= DUMP_LIMIT,
            "OWNER_CLIENT_FAILURE",
        )
        return result.stdout

    def verify_container(self) -> None:
        context = self._run(["context", "show"]).decode("ascii").strip()
        require(
            re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", context),
            "OWNER_CONTEXT_NAME",
        )
        endpoint = (
            self._run(
                [
                    "context",
                    "inspect",
                    "--format",
                    '{{(index .Endpoints "docker").Host}}',
                    context,
                ]
            )
            .decode("ascii")
            .strip()
        )
        require(endpoint.startswith("unix://"), "OWNER_LOCAL_CONTEXT_REQUIRED")
        image = self._run(["image", "inspect", "--format", "{{.Id}}", IMAGE]).strip()
        require(re.fullmatch(rb"sha256:[0-9a-f]{64}", image), "PINNED_IMAGE_UNVERIFIED")
        fields = (
            self._run(
                [
                    "inspect",
                    "--type",
                    "container",
                    "--format",
                    (
                        "{{.Id}}\n{{.Image}}\n{{.Config.Image}}\n{{.State.Running}}\n"
                        "{{json .Config.Labels}}\n{{json .NetworkSettings.Ports}}\n"
                        "{{json .Mounts}}\n{{json .NetworkSettings.Networks}}"
                    ),
                    self.container,
                ]
            )
            .decode("utf-8")
            .splitlines()
        )
        require(len(fields) == 8, "OWNER_CONTAINER_IDENTITY_MISMATCH")
        require(
            fields[:4] == [self.container, image.decode("ascii"), IMAGE, "true"],
            "OWNER_CONTAINER_IDENTITY_MISMATCH",
        )
        t = self.target
        project = f"pitlab-{t.namespace}-{t.target}"
        labels, ports, mounts, networks = map(json.loads, fields[4:])
        require(
            labels.get("io.pitlab.purpose") == t.target
            and labels.get("io.pitlab.namespace") == t.namespace
            and labels.get("io.pitlab.instance") == t.instance
            and labels.get("com.docker.compose.project") == project
            and labels.get("com.docker.compose.service") == f"postgres_{t.target}"
            and ports == {"5432/tcp": [{"HostIp": "127.0.0.1", "HostPort": str(t.port)}]}
            and set(networks) == {project + "_default"}
            and len(mounts) == 2
            and any(
                m["Type"] == "volume"
                and m.get("Name") == f"{project}_pgdata_{t.target}"
                and m["Destination"] == "/var/lib/postgresql/data"
                and m["RW"]
                for m in mounts
            )
            and any(
                m["Type"] == "bind"
                and not m["RW"]
                and m["Destination"] == "/docker-entrypoint-initdb.d/10-pitlab.sh"
                for m in mounts
            ),
            "OWNER_CONTAINER_IDENTITY_MISMATCH",
        )

    def _client(self, command: str, args: list[str], raw: bytes = b"") -> bytes:
        self.verify_container()
        prefix = ["exec", "-i", "--user", "postgres", self.container]
        executable = f"/usr/bin/{command}"
        version = self._run([*prefix, executable, "--version"])
        require(
            version.startswith(f"{command} (PostgreSQL) 17.11".encode()),
            "PINNED_CLIENT_VERSION_MISMATCH",
        )
        return self._run(
            [*prefix, "/bin/sh", "-c", CLIENT_SCRIPT, "f4-client", executable, *args],
            self.target.password.encode("ascii") + b"\n" + raw,
        )

    def _connection(self) -> list[str]:
        return [
            "-h",
            "127.0.0.1",
            "-p",
            "5432",
            "-U",
            self.target.user,
            "-d",
            self.target.database,
            "--no-password",
        ]

    def dump(self, snapshot: str) -> bytes:
        require(
            re.fullmatch(r"[0-9A-Fa-f]+-[0-9A-Fa-f]+-[0-9]+", snapshot),
            "INVALID_EXPORTED_SNAPSHOT",
        )
        allowlist = [f"--table=public.f4_d1_{name}" for name in (*TABLES, SEQUENCE)]
        # The exporting connection holds SHARE locks. The dump only acquires ACCESS SHARE.
        return self._client(
            "pg_dump",
            [
                *self._connection(),
                "--data-only",
                "--no-owner",
                "--no-acl",
                "--format=custom",
                "--strict-names",
                f"--snapshot={snapshot}",
                *allowlist,
            ],
        )

    def validate_toc(self, raw: bytes) -> None:
        toc = self._client("pg_restore", ["--list"], raw).decode("utf-8")
        entries = []
        for line in toc.splitlines():
            if line and not line.startswith(";"):
                match = re.fullmatch(
                    r"\d+; \d+ \d+ (TABLE DATA|SEQUENCE SET) public (f4_d1_[a-z_]+) "
                    r"pitlab_(?:dev|test)_migrator",
                    line,
                )
                require(match, "UNEXPECTED_DUMP_MEMBER")
                assert match is not None
                entries.append((match[1], match[2]))
        expected = [("TABLE DATA", f"f4_d1_{name}") for name in TABLES]
        expected.append(("SEQUENCE SET", f"f4_d1_{SEQUENCE}"))
        require(sorted(entries) == sorted(expected), "UNEXPECTED_DUMP_MEMBER_SET")

    def restore(self, raw: bytes) -> None:
        self._client(
            "pg_restore",
            [
                *self._connection(),
                "--data-only",
                "--single-transaction",
                "--exit-on-error",
                "--no-owner",
                "--no-acl",
            ],
            raw,
        )


def exact_children(
    expected: list[dict[str, Any]],
    row_results: list[dict[str, Any]],
    issuers: list[dict[str, Any]],
    assertions: list[dict[str, Any]],
) -> None:
    """Compare typed SQL row projections against the deterministic parsed source."""
    rows_expected = [{key: row[key] for key in ("row_no", "status", "reason")} for row in expected]
    issuer_expected = []
    assertion_expected = []
    for row in expected:
        if row["status"] != "ACCEPTED":
            continue
        if "issuer" in row:
            issuer_expected.append(row["issuer"] | {"row_no": row["row_no"]})
            continue
        item = row["assertion"]
        body, subject = item["body"], item["body"]["subject"]
        assertion_expected.append(
            {
                "row_no": row["row_no"],
                **{
                    key: item[key]
                    for key in (
                        "issuer_key",
                        "field",
                        "report_date",
                        "version_sha",
                        "subject_sha",
                    )
                },
                **{
                    key: subject[key]
                    for key in (
                        "period_start",
                        "period_end_exclusive",
                        "basis",
                        "currency",
                        "unit",
                    )
                },
                "body": json_bytes(body),
                "subject_body": json_bytes(subject),
                "amount": Decimal(body["value"]) if body["value"] is not None else None,
                "state": body["state"],
            }
        )
    require(row_results == rows_expected, "ARTIFACT_ROW_CLASSIFICATION_MISMATCH")
    require(issuers == issuer_expected, "ARTIFACT_ISSUER_OCCURRENCE_MISMATCH")
    require(assertions == assertion_expected, "ARTIFACT_ASSERTION_OCCURRENCE_MISMATCH")


def verify_ledger(db: DB, root: Path, artifacts: dict[str, int]) -> dict[str, Any]:
    historical_issuers: set[tuple[str, str, str]] = set()
    version_keys: set[str] = set()
    exact: dict[str, Any] = {}
    observations = db.execute("""
        SELECT o.*, a.input_name, a.input_sha, a.started_at, a.request_sha, a.deployment,
               p.profile, p.body AS profile_body, c.outcome, c.recorded_at
        FROM public.f4_d1_observation o
        JOIN public.f4_d1_attempt a ON a.id=o.id AND a.profile_sha=o.profile_sha
        JOIN public.f4_d1_profile p ON p.sha=o.profile_sha
        LEFT JOIN public.f4_d1_custody_event c ON c.id=o.id
        ORDER BY o.ordinal
    """).fetchall()
    for o in observations:
        observation = str(o["id"])
        key, size = o["artifact_sha"], o["size"]
        receipt = read_receipt(o)
        expected = []
        profile = profile_body(o["profile"])
        require(
            o["profile_body"] == json_bytes(profile)
            and o["profile_sha"] == digest("profile", profile)
            and o["request_sha"]
            == digest(
                "receipt",
                {
                    "profile": o["profile_sha"],
                    "input": o["input_name"],
                    "sha": o["input_sha"],
                },
            ),
            "ATTEMPT_PROFILE_OR_REQUEST_MISMATCH",
        )
        if key is not None:
            require(
                key == o["input_sha"] and artifacts.get(key) == size,
                "ARTIFACT_LINK_MISMATCH",
            )
            expected = classified(o["profile"], read_blob(root, key, size), historical_issuers)
        require(
            o["projection"] == projection(expected),
            "ARTIFACT_SEALED_PROJECTION_MISMATCH",
        )
        captured, completed, started = (
            o["captured_at"],
            o["completed_at"],
            o["started_at"],
        )
        reason = receipt.get("reason")
        require(
            type(reason) is str and re.fullmatch(r"[A-Z_]{1,64}", reason)
            if key is None
            else reason is None,
            "RECEIPT_REASON_MISMATCH",
        )
        require(
            (key is not None) == (o["result"] == "IMPORTED_UNQUALIFIED")
            and o["outcome"] in ({"PUBLISHED", "RECOVERED"} if key else {"NO_BYTES"})
            and o["recorded_at"] is not None
            and started <= completed <= o["recorded_at"]
            and (started <= captured <= completed if key else captured is None)
            and receipt
            == {
                "attempt": observation,
                "observation": f"f4d1:observation:{observation}",
                "deployment": o["deployment"],
                "profile": o["profile"],
                "profile_sha": o["profile_sha"],
                "request_sha": o["request_sha"],
                "result": o["result"],
                "reason": reason,
                "artifact": f"f4d1:artifact:sha256:{key}" if key else None,
                "byte_count": size,
                "counts": counts(expected) if key else None,
                "started_at": timestamp(started),
                "captured_at": timestamp(captured) if captured else None,
                "completed_at": timestamp(completed),
                "clock_precision": "MICROSECOND",
                "clock_origin": "LOCAL_DATABASE_AND_IMPORT_PROCESS_UTC",
                "publication": "UNRESOLVED",
                "history_coverage": "UNRESOLVED",
                "method": "FIXTURE_IMPORT",
                "mode": "SYNTHETIC_ONLY",
            },
            "RECEIPT_REFERENCE_MISMATCH",
        )
        row_results = db.execute(
            "SELECT row_no,status,reason FROM public.f4_d1_row_result "
            "WHERE observation=%s ORDER BY row_no",
            (observation,),
        ).fetchall()
        issuers = db.execute(
            "SELECT row_no,issuer_key AS key,code,name,sector,listed_date "
            "FROM public.f4_d1_issuer_occurrence WHERE observation=%s ORDER BY row_no",
            (observation,),
        ).fetchall()
        assertions = db.execute(
            """
            SELECT a.row_no,a.field,a.report_date,v.*
            FROM public.f4_d1_assertion_occurrence a
            LEFT JOIN public.f4_d1_assertion_version v ON v.version_sha=a.version_sha
            WHERE a.observation=%s ORDER BY a.row_no,a.field
        """,
            (observation,),
        ).fetchall()
        for issuer in issuers:
            issuer["listed_date"] = public_value(issuer["listed_date"])
        for assertion in assertions:
            for field in ("report_date", "period_start", "period_end_exclusive"):
                assertion[field] = public_value(assertion[field])
        exact_children(expected, row_results, issuers, assertions)
        historical_issuers.update((r["code"], r["key"], r["name"]) for r in issuers)
        version_keys.update(row["version_sha"] for row in assertions)
        exact[observation] = {
            "receipt": o["receipt_sha"],
            "artifact": key,
            "projection_sha": sha(json_bytes(o["projection"])),
            "assertions": [[r["row_no"], r["field"], r["version_sha"]] for r in assertions],
        }
    require(
        version_keys
        == {
            r["version_sha"]
            for r in db.execute("SELECT version_sha FROM public.f4_d1_assertion_version")
        }
        and {key for _, key, _ in historical_issuers}
        == {r["key"] for r in db.execute("SELECT key FROM public.f4_d1_issuer")},
        "DATABASE_CANONICAL_REACHABILITY",
    )
    return exact


def state(db: DB, root: Path) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    for name in TABLES:
        raw = [
            r["body"]
            for r in db.execute(
                sql.SQL(
                    'SELECT to_jsonb(t)::text AS body FROM {} t ORDER BY to_jsonb(t)::text COLLATE "C"'
                ).format(table(name))
            ).fetchall()
        ]
        metadata[name] = {"count": len(raw), "sha256": sha(json_bytes(raw))}
    definitions = db.execute(
        """
        SELECT c.relname, q.conname, pg_get_constraintdef(q.oid) AS definition
        FROM pg_constraint q JOIN pg_class c ON c.oid=q.conrelid
        JOIN pg_namespace n ON n.oid=c.relnamespace
        WHERE n.nspname='public' AND c.relname=ANY(%s)
        ORDER BY c.relname,q.conname
    """,
        (["f4_d1_" + name for name in TABLES],),
    ).fetchall()
    require(
        {entry["relname"] for entry in definitions} == {"f4_d1_" + name for name in TABLES},
        "F4_CONSTRAINTS_MISSING",
    )
    seals = db.execute(
        """
        SELECT c.relname, t.tgname, pg_get_triggerdef(t.oid) AS trigger,
               pg_get_functiondef(p.oid) AS function
        FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid
        JOIN pg_namespace n ON n.oid=c.relnamespace
        JOIN pg_proc p ON p.oid=t.tgfoid
        WHERE n.nspname='public' AND c.relname=ANY(%s)
          AND NOT t.tgisinternal AND t.tgenabled='O'
        ORDER BY c.relname,t.tgname
    """,
        (["f4_d1_" + name for name in TABLES],),
    ).fetchall()
    require(
        {item["relname"] for item in seals}
        == {
            "f4_d1_observation",
            "f4_d1_row_result",
            "f4_d1_issuer_occurrence",
            "f4_d1_assertion_occurrence",
        }
        and len(seals) == 4,
        "F4_SEALS_MISSING",
    )
    artifacts: dict[str, int] = {}
    for r in db.execute("SELECT sha,size FROM public.f4_d1_artifact ORDER BY sha").fetchall():
        read_blob(root, r["sha"], r["size"])
        artifacts[r["sha"]] = r["size"]
    used = {
        r["artifact_sha"]
        for r in db.execute(
            "SELECT DISTINCT artifact_sha FROM public.f4_d1_observation WHERE artifact_sha IS NOT NULL"
        ).fetchall()
    }
    require(set(artifacts) == used, "DATABASE_ARTIFACT_REACHABILITY")
    bindings = verify_ledger(db, root, artifacts)
    sequence = db.execute(sql.SQL("SELECT last_value,is_called FROM {}").format(table(SEQUENCE)))
    return {
        "tables": metadata,
        "artifacts": artifacts,
        "bindings": bindings,
        "sequence": sequence.fetchone(),
        "constraints_sha": sha(json_bytes({"constraints": definitions, "seals": seals})),
        "inventory_sha": sha(json_bytes(inventory(db))),
    }


def backup(
    target: Target,
    container: str,
    name: str,
    *,
    on_snapshot: Callable[[], None] | None = None,
) -> dict[str, Any]:
    require(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", name), "UNSAFE_OUTPUT_NAME")
    client = OwnerClient(target, container)
    root = target.root
    with custody_lock(root), connect(target) as db:
        require(revision(db) == "d1_001", "F4_REVISION_REQUIRED")
        lock_all(db)
        record = db.execute("SELECT pg_export_snapshot() AS id").fetchone()
        assert record is not None
        if on_snapshot is not None:
            on_snapshot()
        captured = state(db, root)
        dump = client.dump(record["id"])
        client.validate_toc(dump)
        result = {
            "format": "f4-d1-backup-v1",
            "source": target.marker,
            "source_port": target.port,
            "revision": "d1_001",
            "image": IMAGE,
            "dump_sha": sha(dump),
            "dump_size": len(dump),
            "state": captured,
        }
        # Write into an exclusive new directory. Only a final manifest is a completed backup.
        encoded = json_bytes(result)
        require(len(encoded) <= MANIFEST_LIMIT, "BACKUP_MANIFEST_LIMIT")
        output = root / name
        output.mkdir(mode=0o700)
        publish(output / "f4.dump", dump)
        for key, size in captured["artifacts"].items():
            put_blob(output, read_blob(root, key, size))
        publish(output / "manifest.json", encoded)
        return result


def check_bundle(root: Path) -> tuple[dict[str, Any], bytes]:
    raw = private_read(root / "manifest.json", MANIFEST_LIMIT)
    manifest = decode(raw)
    require(
        isinstance(manifest, dict)
        and raw == json_bytes(manifest)
        and set(manifest)
        == {
            "format",
            "source",
            "source_port",
            "revision",
            "image",
            "dump_sha",
            "dump_size",
            "state",
        }
        and manifest["format"] == "f4-d1-backup-v1"
        and manifest["revision"] == "d1_001"
        and manifest["image"] == IMAGE,
        "INVALID_BACKUP_MANIFEST",
    )
    dump = private_read(root / "f4.dump", DUMP_LIMIT)
    require(
        manifest["dump_size"] == len(dump) and manifest["dump_sha"] == sha(dump),
        "DUMP_INTEGRITY_FAILURE",
    )
    artifacts = manifest["state"]["artifacts"]
    for key, size in artifacts.items():
        read_blob(root, key, size)
    expected = {"manifest.json", "f4.dump"}
    for key in artifacts:
        expected.update({"sha256", f"sha256/{key[:2]}", f"sha256/{key[:2]}/{key}"})
    actual = set()
    for here, dirs, files in os.walk(root, followlinks=False):
        for item in dirs + files:
            path = Path(here) / item
            require(not path.is_symlink(), "UNSAFE_BACKUP_MEMBER")
            actual.add(path.relative_to(root).as_posix())
    require(actual == expected, "UNEXPECTED_BACKUP_MEMBER_SET")
    return manifest, dump


def closed_empty(db: DB, target: Target) -> None:
    require(revision(db) == "d1_001", "F4_REVISION_REQUIRED")
    access = db.execute(
        """
        SELECT role.name AS role, object.name AS object
        FROM unnest(%s::text[]) role(name), unnest(%s::text[]) object(name)
        WHERE has_table_privilege(role.name,object.name,
               'SELECT, INSERT, UPDATE, DELETE, TRUNCATE, REFERENCES, TRIGGER, MAINTAIN')
           OR has_function_privilege(role.name,%s,'EXECUTE')
        """,
        (
            [target.account(role) for role in ("reader", "custodian", "publisher")],
            [f"public.f4_d1_{name}" for name in (*TABLES, *VIEWS)],
            ATTEMPT_LOCK,
        ),
    ).fetchall()
    require(not access, "RESTORE_TARGET_IS_NOT_CLOSED")
    for name in TABLES:
        row = db.execute(
            sql.SQL("SELECT EXISTS(SELECT 1 FROM {}) AS used").format(table(name))
        ).fetchone()
        require(row == {"used": False}, "RESTORE_TARGET_NOT_EMPTY")
    require(not (target.root / "sha256").exists(), "RESTORE_CUSTODY_NOT_EMPTY")


def restore(target: Target, container: str, bundle: Path) -> dict[str, Any]:
    client = OwnerClient(target, container)
    require(bundle.is_absolute(), "ABSOLUTE_PRIVATE_BACKUP_REQUIRED")
    with custody_lock(target.root):
        require(
            private_read(target.root / "restore-target.json", 4096)
            == json_bytes({"marker": target.marker}),
            "RESTORE_TARGET_MARKER_MISMATCH",
        )
        manifest, raw = check_bundle(bundle)
        require(
            manifest["source"] != target.marker
            and manifest["source_port"] != target.port
            and target.root not in bundle.parents,
            "RESTORE_SOURCE_TARGET_COLLISION",
        )
        client.validate_toc(raw)
        with connect(target) as db:
            # Existing readers/writers have no F4 grants. Do not hold a table lock across
            # pg_restore, which must take its own locks using the verified migrator.
            closed_empty(db, target)
        client.restore(raw)
        for key, size in manifest["state"]["artifacts"].items():
            put_blob(target.root, read_blob(bundle, key, size))
        with connect(target) as db:
            lock_all(db, restore=True)
            result = state(db, target.root)
            require(result == manifest["state"], "RESTORE_STATE_MISMATCH")
            grants(db, target, available=True)
        return {
            "result": "FIXTURE_RESTORED",
            "source": manifest["source"],
            "destination": target.marker,
            "state": result,
            "dump_sha": manifest["dump_sha"],
        }
