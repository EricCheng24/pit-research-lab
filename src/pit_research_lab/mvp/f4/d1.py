"""The local, synthetic-only D1 foundation operator."""

import argparse
import json
import re
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psycopg
from sqlalchemy.exc import SQLAlchemyError

from .d1_backup import backup, closed_empty, restore, state
from .d1_custody import custody_lock, directory, publish, put_blob, read_blob
from .d1_profile import (
    AUDIENCE,
    LIMIT,
    Refusal,
    Target,
    acquire,
    decode,
    digest,
    json_bytes,
    load_target,
    private_read,
    require,
    sha,
    timestamp,
    uuid4_text,
)
from .d1_records import rows
from .d1_store import (
    begin,
    connect,
    finish,
    grants,
    inventory,
    is_active,
    lock_all,
    match_roles,
    migrate,
    provision,
    read_receipt,
    revision,
    set_profile,
    started,
)


def require_role(target: Target, role: str) -> None:
    require(target.role == role, "OPERATOR_ROLE_REQUIRED")


def empty_name(value: str) -> str:
    require(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", value), "UNSAFE_OUTPUT_NAME")
    return value


def init(
    admin: Target,
    migrator: Target,
    writer: Target,
    reader: Target,
    publisher: Target,
    *,
    restore_only: bool,
    profiles_until: datetime | None = None,
    revoke: str | None = None,
) -> None:
    require(
        not restore_only or (profiles_until is None and revoke is None),
        "RESTORE_ONLY_CONFIG_MISMATCH",
    )
    require(profiles_until is None or revoke is None, "CONFLICTING_PROFILE_ACTIONS")
    require_role(migrator, "migrator")
    with custody_lock(migrator.root):
        marker = migrator.root / "restore-target.json"
        if restore_only:
            raw = json_bytes({"marker": migrator.marker})
            try:
                publish(marker, raw)
            except FileExistsError:
                require(private_read(marker, 4096) == raw, "RESTORE_TARGET_MARKER_MISMATCH")
        else:
            require(
                not marker.exists() and not marker.is_symlink(),
                "RESTORE_TARGET_REQUIRES_RESTORE",
            )
        provision(admin, migrator, writer, reader, publisher)
        migrate(migrator)
        with connect(migrator) as db:
            lock_all(db, restore=restore_only)
            if restore_only:
                # A fresh restore target is closed by construction, never revoke a
                # populated or already opened target under the guise of restoring.
                closed_empty(db, migrator)
                return
            if profiles_until is not None:
                require(bool(writer.profiles), "FIXTURE_PROFILE_NOT_PINNED")
                for profile in sorted(writer.profiles):
                    set_profile(db, profile, profiles_until)
            if revoke is not None:
                require(revoke in writer.profiles, "FIXTURE_PROFILE_NOT_PINNED")
                set_profile(db, revoke, None)
            grants(db, migrator, available=True)


def prior(target: Target, row: dict[str, Any]) -> dict[str, Any]:
    receipt = read_receipt(row)
    if receipt["artifact"] is not None:
        key = receipt["artifact"].split(":")[-1]
        require(key == row["input_sha"], "RECEIPT_ARTIFACT_MISMATCH")
        read_blob(target.root, key, receipt["byte_count"])
    return receipt


def finalize_stage(
    target: Target,
    row: dict[str, Any],
    stage: dict[str, Any],
    *,
    publisher: Target,
    recovered: bool,
    checkpoint: Callable[[str], None],
) -> dict[str, Any]:
    require(
        set(stage) == {"request_sha", "artifact", "size", "captured_at"}
        and stage["request_sha"] == row["request_sha"]
        and stage["artifact"] == row["input_sha"]
        and type(stage["size"]) is int
        and 0 < stage["size"] <= LIMIT
        and isinstance(stage["captured_at"], str),
        "INVALID_STAGE_BINDING",
    )
    try:
        captured = datetime.fromisoformat(stage["captured_at"])
    except ValueError:
        raise Refusal("INVALID_STAGE_CLOCK") from None
    require(timestamp(captured) == stage["captured_at"], "INVALID_STAGE_CLOCK")
    artifact = (stage["artifact"], stage["size"])
    raw = read_blob(target.root, *artifact)
    with connect(publisher) as db:
        receipt = finish(
            db,
            target,
            row,
            result="IMPORTED_UNQUALIFIED",
            artifact=artifact,
            captured=captured,
            raw=raw,
            recovered=recovered,
        )
        checkpoint("before_commit")
    checkpoint("after_commit")
    return receipt


def refusal(publisher: Target, row: dict[str, Any], result: str, reason: str) -> dict[str, Any]:
    with connect(publisher) as db:
        return finish(db, publisher, row, result=result, reason=reason)


def _recover(
    target: Target,
    row: dict[str, Any],
    checkpoint: Callable[[str], None],
    publisher: Target,
) -> dict[str, Any]:
    if row["receipt"] is not None:
        return prior(target, row)
    profile, pin = target.pin(row["profile"], row["input_name"])
    require(
        profile == row["profile_sha"] and pin == row["input_sha"],
        "RECOVERY_PIN_MISMATCH",
    )
    with connect(target) as db:
        active = is_active(db, row["profile"], profile)
    if not active:
        return refusal(publisher, row, "REFUSED", "FIXTURE_PROFILE_NOT_ACTIVE")
    stage_path = target.root / "attempts" / f"{row['id']}.json"
    try:
        stage = decode(private_read(stage_path, 4096))
    except FileNotFoundError:
        return refusal(publisher, row, "INTERRUPTED", "NO_FINALIZED_STAGE")
    except (Refusal, OSError):
        return refusal(publisher, row, "REFUSED", "UNSAFE_STAGE")
    try:
        require(isinstance(stage, dict), "INVALID_STAGE_BINDING")
        return finalize_stage(
            target,
            row,
            stage,
            publisher=publisher,
            recovered=True,
            checkpoint=checkpoint,
        )
    except Refusal as error:
        return refusal(publisher, row, "REFUSED", str(error))


def no_checkpoint(_: str) -> None:
    pass


def recover(target: Target, attempt: str, *, publisher: Target) -> dict[str, Any]:
    require_role(target, "custodian")
    match_roles(target, publisher, "publisher")
    attempt = uuid4_text(attempt)
    with custody_lock(target.root):
        with connect(target) as db:
            row = started(db, attempt)
            require(row is not None, "UNKNOWN_ATTEMPT")
        assert row is not None
        return _recover(target, row, no_checkpoint, publisher)


def import_fixture(
    target: Target,
    profile: str,
    attempt: str,
    name: str,
    *,
    publisher: Target,
    checkpoint: Callable[[str], None] = no_checkpoint,
    lock_budget: float = 5,
    on_contention: Callable[[], None] | None = None,
) -> dict[str, Any]:
    match_roles(target, publisher, "publisher")
    key, pin = target.pin(profile, name)
    attempt = uuid4_text(attempt)
    with custody_lock(target.root, budget=lock_budget, on_contention=on_contention):
        with connect(publisher) as db:
            row, fresh = begin(db, attempt, profile, key, name, pin, target.marker)
        if not fresh:
            return _recover(target, row, checkpoint, publisher)
        checkpoint("after_intent")
        try:
            raw = private_read(target.root / "inputs" / name, LIMIT)
            require(sha(raw) == pin, "FIXTURE_INPUT_PIN_MISMATCH")
            # Reject non-fixture envelopes before putting any contents in CAS.
            rows(profile, raw)
        except Refusal as error:
            return refusal(publisher, row, "REFUSED", str(error))
        except OSError:
            return refusal(publisher, row, "REFUSED", "UNSAFE_OR_MISSING_INPUT")
        captured = datetime.now(UTC)
        try:
            artifact, size = put_blob(target.root, raw)
            with directory(target.root / "attempts", create=True):
                stage = {
                    "request_sha": row["request_sha"],
                    "artifact": artifact,
                    "size": size,
                    "captured_at": timestamp(captured),
                }
                publish(target.root / "attempts" / f"{attempt}.json", json_bytes(stage))
        except Refusal as error:
            return refusal(publisher, row, "REFUSED", str(error))
        checkpoint("after_publish")
        try:
            return finalize_stage(
                target,
                row,
                stage,
                publisher=publisher,
                recovered=False,
                checkpoint=checkpoint,
            )
        except Refusal as error:
            return refusal(publisher, row, "REFUSED", str(error))


def inspect(target: Target) -> dict[str, Any]:
    require_role(target, "reader")
    with connect(target) as db:
        db.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        return inventory(db)


def export(target: Target, audience: str, name: str) -> dict[str, Any]:
    require(audience == AUDIENCE, "EXPORT_AUDIENCE_NOT_GRANTED")
    name = empty_name(name)
    data = inspect(target)
    records = []
    for category in ("inventory", "issuers", "values"):
        for item in data[category]:
            record = {"kind": category, **item}
            if category == "values":
                record["assertion_ref"] = f"f4d1:assertion:sha256:{item['version_sha']}"
            records.append(json_bytes(record))
    raw = b"".join(record + b"\n" for record in records)
    manifest = {k: v for k, v in data.items() if k not in {"inventory", "issuers", "values"}}
    manifest.update(audience=audience, body_sha=sha(raw), rows=len(records))
    manifest["export_sha"] = digest("export", manifest)
    output = target.root / name
    output.mkdir(mode=0o700)
    publish(output / "inventory.jsonl", raw)
    publish(output / "manifest.json", json_bytes(manifest))
    return manifest


def verify(target: Target) -> dict[str, Any]:
    require_role(target, "migrator")
    with custody_lock(target.root), connect(target) as db:
        lock_all(db)
        return state(db, target.root)


def arguments(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    actions.add_parser("acquire", help="Always refuse real transport")
    init_parser = actions.add_parser("init")
    for command in (
        "schema-current",
        "import-fixture",
        "inspect",
        "verify",
        "export-inventory",
        "recover",
        "backup",
        "restore",
    ):
        actions.add_parser(command)
    for name in (
        "init",
        "schema-current",
        "import-fixture",
        "inspect",
        "verify",
        "export-inventory",
        "recover",
        "backup",
        "restore",
    ):
        actions.choices[name].add_argument("--config", required=True, type=Path)
    for role in ("admin", "custodian", "reader", "publisher"):
        init_parser.add_argument(f"--{role}-config", required=True, type=Path)
    init_parser.add_argument("--restore-only", action="store_true")
    init_parser.add_argument("--profiles-until")
    init_parser.add_argument("--revoke")
    ingest = actions.choices["import-fixture"]
    ingest.add_argument("--publisher-config", required=True, type=Path)
    actions.choices["recover"].add_argument("--publisher-config", required=True, type=Path)
    ingest.add_argument("--profile", required=True)
    ingest.add_argument("--file", required=True, help="basename in the private pinned inputs root")
    ingest.add_argument("--attempt", required=True)
    actions.choices["recover"].add_argument("--attempt", required=True)
    release = actions.choices["export-inventory"]
    release.add_argument("--audience", required=True)
    release.add_argument("--name", required=True)
    for name in ("backup", "restore"):
        actions.choices[name].add_argument("--container", required=True)
    actions.choices["backup"].add_argument("--name", required=True)
    actions.choices["restore"].add_argument("--bundle", required=True, type=Path)
    return parser.parse_args(argv)


def run(args: argparse.Namespace) -> dict[str, Any]:
    if args.action == "acquire":
        acquire()
    target = load_target(args.config)
    if args.action == "init":
        expires = datetime.fromisoformat(args.profiles_until) if args.profiles_until else None
        if expires is not None:
            require(timestamp(expires) == args.profiles_until, "CANONICAL_UTC_REQUIRED")
        init(
            load_target(args.admin_config),
            target,
            load_target(args.custodian_config),
            load_target(args.reader_config),
            load_target(args.publisher_config),
            restore_only=args.restore_only,
            profiles_until=expires,
            revoke=args.revoke,
        )
        return {
            "revision": "d1_001",
            "marker": target.marker,
            "closed": args.restore_only,
        }
    if args.action == "schema-current":
        require_role(target, "migrator")
        with connect(target) as db:
            return {"revision": revision(db), "marker": target.marker}
    if args.action == "import-fixture":
        return import_fixture(
            target,
            args.profile,
            args.attempt,
            args.file,
            publisher=load_target(args.publisher_config),
        )
    if args.action == "recover":
        return recover(target, args.attempt, publisher=load_target(args.publisher_config))
    if args.action == "inspect":
        return inspect(target)
    if args.action == "verify":
        return verify(target)
    if args.action == "export-inventory":
        return export(target, args.audience, args.name)
    if args.action == "backup":
        return backup(target, args.container, empty_name(args.name))
    if args.action == "restore":
        return restore(target, args.container, args.bundle)
    raise Refusal("UNSUPPORTED_COMMAND")


def main(argv: list[str] | None = None) -> int:
    try:
        result = run(arguments(argv))
        print(json_bytes(result).decode("utf-8"))
        return 2 if result.get("result") in {"REFUSED", "INTERRUPTED"} else 0
    except Refusal as error:
        print(json.dumps({"refused": str(error)}), file=sys.stderr)
        return 2
    except (OSError, ValueError, psycopg.Error, SQLAlchemyError):
        print('{"refused":"LOCAL_OPERATION_FAILED"}', file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
