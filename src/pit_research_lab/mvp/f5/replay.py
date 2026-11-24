"""Owned external artifacts, genuine-input gate, separate attempts and replay receipts."""

import os
import platform
import resource
import stat
import subprocess
import sys
import time
import uuid
from collections import Counter
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from pathlib import Path
from typing import Any

from pit_research_lab.mvp.f2 import research_panel as f2
from pit_research_lab.mvp.f3_l1 import replay as f3_replay

from .contracts import (
    COMPLETE,
    DEGRADED,
    INCOMPLETE,
    POLICIES,
    F5Error,
    Protocol,
    envelope,
    hex64,
    require,
    safe_reason,
    wire,
)
from .experiment import census, evaluate, prepare
from .inputs import (
    OriginWitness,
    ProducerOrigin,
    establish_from_witness,
    import_f3,
    regular_bytes,
)
from .prices import check_compatibility, pinned_body

ARTIFACTS = ("spec", "decisions", "ledger", "metrics", "evidence")
CODE_FILES = (
    "__init__",
    "contracts",
    "inputs",
    "prices",
    "policies",
    "accounting",
    "experiment",
    "replay",
    "cli",
)
TEST_FILES = (
    "__init__",
    "test_inputs",
    "test_prices",
    "test_policies",
    "test_accounting",
    "test_replay",
)


def provenance() -> dict[str, Any]:
    require(sys.version_info[:2] == (3, 12), "PYTHON_312_REQUIRED")
    result = f3_replay.provenance()
    files = list(result["files"])
    paths = ["src/pit_research_lab/mvp/f5/" + n + ".py" for n in CODE_FILES]
    paths += ["tests/unit/mvp_f5/" + n + ".py" for n in TEST_FILES]
    for name in paths:
        raw = regular_bytes(f2.ROOT / name)
        files.append({"path": name, "sha256": sha256(raw).hexdigest(), "byte_length": len(raw)})
    return {
        "f5_head": result["base_head"],
        "code_claim": result["code_claim"],
        "files": sorted(files, key=lambda p: p["path"]),
        "runtime": {"python": sys.version, "implementation": platform.python_implementation()},
    }


def safe_output(out: Path) -> None:
    require(out.is_absolute() and ".." not in out.parts, "UNSAFE_OUTPUT")
    require(not any(p.is_symlink() for p in (out, *out.parents)), "OUTPUT_SYMLINK")
    require(not os.path.lexists(out), "OUTPUT_ALREADY_EXISTS")
    worktrees = subprocess.check_output(
        ["git", "--no-optional-locks", "-C", str(f2.ROOT), "worktree", "list", "--porcelain"],
        text=True,
    )
    roots = [
        Path(line.removeprefix("worktree "))
        for line in worktrees.splitlines()
        if line.startswith("worktree ")
    ]
    require(
        not any(out.is_relative_to(r) or r.is_relative_to(out) for r in roots), "OUTPUT_IN_CHECKOUT"
    )
    m = out.parent.lstat()
    require(
        stat.S_ISDIR(m.st_mode) and m.st_uid == os.getuid() and not m.st_mode & 0o077,
        "OUTPUT_PARENT",
    )


def _write(out: Path, name: str, payload: Any, *, update: bool = False) -> None:
    require(name in (*ARTIFACTS, "attempt"), "ARTIFACT_NAME")
    raw = envelope(name.upper(), payload)
    require(
        len(raw) <= 64 * 1024 * 1024
        and sum(p.stat().st_size for p in out.iterdir()) + len(raw) <= 256 * 1024 * 1024,
        "ARTIFACT_BUDGET",
    )
    p = out / (name + ".json")
    flags = os.O_WRONLY | os.O_NOFOLLOW | (os.O_TRUNC if update else os.O_CREAT | os.O_EXCL)
    if update:
        m = p.lstat()
        require(
            stat.S_ISREG(m.st_mode)
            and m.st_uid == os.getuid()
            and stat.S_IMODE(m.st_mode) == 0o600,
            "ATTEMPT_FILE",
        )
    fd = os.open(p, flags, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(raw)


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds")


def blocked_census(reason: str) -> dict[str, Any]:
    """Account intended slots without inventing policy calls or source qualification."""
    from .contracts import DecisionSlot, seal_slots

    try:
        # Structural calendar integrity only; no event price API/native read.
        cutoffs = pinned_body()["cutoffs"]
        slots = tuple(
            DecisionSlot(
                t, cutoffs[t], p, None, "BLOCKED_NOT_ATTEMPTED", False, None, None, reason, None
            )
            for t in range(48, 96)
            for p in POLICIES
        )
        sealed = seal_slots(slots, reason)
        return sealed.payload() | {
            "slot_set_digest": sealed.slot_set_digest,
            "coverage": census(sealed),
            "census_state": "SEALED_BLOCKED",
            "verified_oos_cells": 0,
            "verified_historical_bindings": 0,
            "qualified_common_mark_cells": 0,
            "weekly_returns_evaluated": 0,
        }
    except Exception:
        # If even the calendar cannot be verified, retain only EXPECTED keys;
        # do not call this a sealed/qualified DecisionSlot census.
        return {
            "census_state": "EXPECTED_ONLY_NOT_SEALED",
            "expected_slots": 144,
            "expected_ticks": 48,
            "attempted": 0,
            "valid": 0,
            "common_failure": reason,
            "slots": [
                {
                    "tick": t,
                    "policy_id": p,
                    "outcome": "BLOCKED_NOT_ATTEMPTED",
                    "attempted": False,
                    "policy_action": None,
                    "failure_cause": reason,
                }
                for t in range(48, 96)
                for p in POLICIES
            ],
        }


def run_to_directory(
    out: Path,
    directory: Path | None = None,
    expected: str | None = None,
    *,
    origin: ProducerOrigin | None = None,
    origin_witness: OriginWitness | None = None,
) -> dict[str, Any]:
    """Trusted embedding may inject a verified witness, never receipt-file authority.

    Each fresh process invokes its own independently configured witness. The
    ordinary CLI supplies none and remains BLOCKED_INPUT. A witness is not
    authenticated here; see inputs.establish_from_witness for the trust boundary.
    """
    safe_output(out)
    require(
        directory is None
        or (not out.is_relative_to(directory) and not directory.is_relative_to(out)),
        "INPUT_OUTPUT_OVERLAP",
    )
    out.mkdir(mode=0o700)
    started = time.monotonic()
    attempt: dict[str, Any] = {
        "attempt_id": str(uuid.uuid4()),
        "process_id": os.getpid(),
        "started_at": _now(),
        "finished_at": None,
        "elapsed_seconds": None,
        "execution_status": "RUNNING",
        "comparison_status": INCOMPLETE,
        "replay_status": "NOT_RUN",
        "completed_stages": [],
        "first_failure": None,
        "evidence_sha256": None,
        "peer_evidence_sha256": None,
        "peer_attempt_id": None,
        "peer_process_id": None,
        "producer_root": str(directory) if directory is not None else None,
        "origin_handoff_status": "NOT_ESTABLISHED",
    }
    _write(out, "attempt", attempt)

    def stage(name: str) -> None:
        attempt["completed_stages"].append(name)
        _write(out, "attempt", attempt, update=True)

    try:
        # Gate A is explicit trusted code supplied by the authorized embedding.
        # No flag/path/hash/file can automatically supply that external authority.
        require(origin is None or origin_witness is None, "AMBIGUOUS_ORIGIN_HANDOFF")
        if origin_witness is not None:
            origin = establish_from_witness(directory, expected, origin_witness)
            attempt["origin_handoff_status"] = "RECORD_BOUND_ARTIFACT_AND_SEMANTICS_PENDING"
            _write(out, "attempt", attempt, update=True)
        # Gates B/C still run before every policy/evaluation callback. No auto-run.
        observations, producer = import_f3(directory, expected, origin)
        attempt["origin_handoff_status"] = "ORIGIN_ARTIFACT_AND_SEMANTICS_VERIFIED"
        stage("F3_ORIGIN_AND_SOURCE_SEMANTICS_VERIFIED")
        observed = provenance()
        check_compatibility()
        body = pinned_body()  # structural source validation, not an event-price read
        protocol = Protocol()
        protocol.validate()
        sealed = prepare(observations, tuple(body["cutoffs"]))
        stage("TYPED_SLOT_CENSUS_SEALED")
        spec = {
            "protocol": wire(protocol),
            "source_sha256": f2.SOURCE_SHA256,
            "manifest_sha256": f2.MANIFEST_SHA256,
            "calendar": body["calendar"],
            "cutoffs": body["cutoffs"],
            "producer_origin": producer,
            "provenance": observed,
            "policies": list(POLICIES),
            "non_if03": True,
        }
        _write(out, "spec", spec)
        _write(
            out,
            "decisions",
            sealed.payload()
            | {
                "slot_set_digest": sealed.slot_set_digest,
                "coverage": census(sealed),
                "observations": [
                    wire(o) | {"information_digest": o.information_digest} for o in observations
                ],
                "observation_coverage": {
                    "actual_ticks": len(observations),
                    "verified_oos_cells": sum(len(o.issuers) for o in observations),
                    "verified_historical_bindings": 480,
                    "qualified_issuer_ticks": sum(
                        i.research_eligible for o in observations for i in o.issuers
                    ),
                    "q_by_tick": [
                        [o.tick, sum(i.research_eligible for i in o.issuers)] for o in observations
                    ],
                    "forecast_states": dict(
                        Counter(i.forecast.state for o in observations for i in o.issuers)
                    ),
                    "revenue_states": dict(
                        Counter(
                            f.state
                            for o in observations
                            for i in o.issuers
                            for f in (i.current, i.previous)
                        )
                    ),
                    "unavailable_causes": dict(
                        Counter(
                            i.eligibility_reason
                            for o in observations
                            for i in o.issuers
                            if not i.research_eligible
                        )
                    ),
                },
            },
        )
        require(
            sealed.common_failure is None, sealed.common_failure or "COMMON_PREPARATION_FAILURE"
        )
        calendar = tuple(
            (r["date"], r["close"]) for r in body["calendar"] if r["status"] == "SESSION"
        )
        result = evaluate(sealed, calendar, tuple(body["cutoffs"]))
        stage("PORTFOLIOS_EVALUATED")
        _write(out, "ledger", {k: result[k] for k in ("events", "marks", "valuations")})
        _write(
            out,
            "metrics",
            {k: v for k, v in result.items() if k not in {"events", "marks", "valuations"}},
        )
        require(
            result["common_failure"] is None,
            result["common_failure"]["reason"]
            if result["common_failure"]
            else "EVALUATION_FAILURE",
        )
        require(
            resource.getrusage(resource.RUSAGE_SELF).ru_maxrss <= 1024 * 1024
            and time.monotonic() - started <= 720,
            "RESOURCE_BUDGET",
        )
        require(observed == provenance(), "SOURCE_CHANGED_DURING_RUN")
        check_compatibility()
        refs = [
            {
                "file": n + ".json",
                "sha256": sha256(regular_bytes(out / (n + ".json"))).hexdigest(),
                "byte_length": (out / (n + ".json")).stat().st_size,
            }
            for n in ARTIFACTS
            if n != "evidence"
        ]
        _write(
            out,
            "evidence",
            {
                "artifacts": refs,
                "candidate_class": result["candidate_class"],
                "test_execution_attestation": "NOT_ATTESTED_BY_RUNTIME",
                "scope": "AUTHORED_SYNTHETIC_ONLY",
            },
        )
        attempt["evidence_sha256"] = sha256(regular_bytes(out / "evidence.json")).hexdigest()
        stage("DETERMINISTIC_EVIDENCE_WRITTEN")
        attempt["execution_status"] = "EVALUATED_REPLAY_PENDING"
    except Exception as error:
        reason = safe_reason(error)
        attempt.update(
            execution_status="BLOCKED_INPUT" if not attempt["completed_stages"] else "FAILED",
            first_failure=reason,
        )
        if not (out / "decisions.json").exists():
            _write(out, "decisions", blocked_census(reason))
        if not (out / "metrics.json").exists():
            _write(
                out,
                "metrics",
                {
                    "candidate_class": INCOMPLETE,
                    "full_period_comparison": {"state": "NOT_COMPUTABLE", "reason": reason},
                    "coverage": {
                        "expected_slots": 144,
                        "expected_oos_cells": 240,
                        "expected_common_mark_cells": 1205,
                    },
                },
            )
    attempt.update(finished_at=_now(), elapsed_seconds=str(time.monotonic() - started))
    _write(out, "attempt", attempt, update=True)
    return attempt


def _read(out: Path, name: str) -> dict[str, Any]:
    raw = regular_bytes(out / (name + ".json"))
    value = f2.decode(raw)
    f2.closed(value, "schema non_if03 payload")
    require(
        value["schema"] == "F5_WEEKLY_SYNTHETIC_" + name.upper() + "_V1"
        and value["non_if03"] is True
        and type(value["payload"]) is dict
        and envelope(name.upper(), value["payload"]) == raw,
        "ARTIFACT_SCHEMA",
    )
    result: dict[str, Any] = value["payload"]
    return result


def _run_root(out: Path) -> None:
    require(
        out.is_absolute()
        and ".." not in out.parts
        and not any(p.is_symlink() for p in (out, *out.parents)),
        "UNSAFE_INPUT_PATH",
    )
    mode = out.lstat()
    require(
        stat.S_ISDIR(mode.st_mode)
        and mode.st_uid == os.getuid()
        and stat.S_IMODE(mode.st_mode) == 0o700,
        "REPLAY_ROOT",
    )
    listing = subprocess.check_output(
        ["git", "--no-optional-locks", "-C", str(f2.ROOT), "worktree", "list", "--porcelain"],
        text=True,
    )
    roots = [
        Path(line.removeprefix("worktree "))
        for line in listing.splitlines()
        if line.startswith("worktree ")
    ]
    require(not any(out.is_relative_to(r) or r.is_relative_to(out) for r in roots), "REPLAY_ROOT")


def _file_stamp(path: Path) -> tuple[int, ...]:
    m = path.lstat()
    return (
        m.st_dev,
        m.st_ino,
        m.st_mode,
        m.st_uid,
        m.st_nlink,
        m.st_size,
        m.st_mtime_ns,
        m.st_ctime_ns,
    )


def _snapshot(out: Path) -> dict[str, Any]:
    """Bounded hashes/stat identities, not a retained copy of up to512MiB pair bytes."""
    _run_root(out)
    names = {n + ".json" for n in (*ARTIFACTS, "attempt")}
    require({p.name for p in out.iterdir()} == names, "ARTIFACT_INVENTORY")
    root_stamp = _file_stamp(out)
    result: dict[str, Any] = {"root": root_stamp}
    total = 0
    for name in sorted(names):
        p = out / name
        m = p.lstat()
        require(
            stat.S_ISREG(m.st_mode)
            and m.st_uid == os.getuid()
            and stat.S_IMODE(m.st_mode) == 0o600
            and m.st_nlink == 1,
            "REPLAY_FILE",
        )
        before = _file_stamp(p)
        total += m.st_size
        require(total <= 256 * 1024 * 1024, "ARTIFACT_BUDGET")
        raw = regular_bytes(p)
        require(before == _file_stamp(p), "REPLAY_DRIFT")
        result[name] = (before, sha256(raw).hexdigest())
    require(root_stamp == _file_stamp(out), "REPLAY_DRIFT")
    return result


def verify_directory(out: Path) -> dict[str, Any]:
    # Candidate integrity only; it is never paired execution evidence by itself.
    _run_root(out)
    require(
        {p.name for p in out.iterdir()} == {n + ".json" for n in (*ARTIFACTS, "attempt")},
        "ARTIFACT_INVENTORY",
    )
    evidence = _read(out, "evidence")
    f2.closed(evidence, "artifacts candidate_class test_execution_attestation scope")
    require(
        [p["file"] for p in evidence["artifacts"]]
        == [n + ".json" for n in ARTIFACTS if n != "evidence"],
        "ARTIFACT_INVENTORY",
    )
    for pin in evidence["artifacts"]:
        f2.closed(pin, "file sha256 byte_length")
        raw = regular_bytes(out / pin["file"])
        require(
            len(raw) == pin["byte_length"] and sha256(raw).hexdigest() == pin["sha256"],
            "ARTIFACT_PIN",
        )
    spec, decisions, ledger, result, attempt = (
        _read(out, n) for n in ("spec", "decisions", "ledger", "metrics", "attempt")
    )
    require(
        spec["protocol"] == wire(Protocol()) and spec["provenance"] == provenance(),
        "REPLAY_SOURCE_PROTOCOL",
    )
    require(
        len(decisions["slots"]) == 144
        and len(ledger["marks"]) == 1205
        and result["coverage"]["complete_calendar"] is True,
        "REPLAY_COVERAGE",
    )
    require(
        result["candidate_class"] == evidence["candidate_class"]
        and result["candidate_class"] in {COMPLETE, DEGRADED},
        "REPLAY_CLASS",
    )
    require(
        attempt["execution_status"] in {"EVALUATED_REPLAY_PENDING", "SUCCEEDED"}
        and attempt["first_failure"] is None
        and attempt["evidence_sha256"] == sha256(regular_bytes(out / "evidence.json")).hexdigest(),
        "REPLAY_ATTEMPT",
    )
    _uuid4(attempt["attempt_id"])
    require(
        attempt["completed_stages"]
        == [
            "F3_ORIGIN_AND_SOURCE_SEMANTICS_VERIFIED",
            "TYPED_SLOT_CENSUS_SEALED",
            "PORTFOLIOS_EVALUATED",
            "DETERMINISTIC_EVIDENCE_WRITTEN",
        ],
        "REPLAY_ATTEMPT",
    )
    return result


_STAGES = [
    "F3_ORIGIN_AND_SOURCE_SEMANTICS_VERIFIED",
    "TYPED_SLOT_CENSUS_SEALED",
    "PORTFOLIOS_EVALUATED",
    "DETERMINISTIC_EVIDENCE_WRITTEN",
]
_ATTEMPT_FIELDS = (
    "attempt_id process_id started_at finished_at elapsed_seconds execution_status "
    "comparison_status replay_status completed_stages first_failure evidence_sha256 "
    "peer_evidence_sha256 peer_attempt_id peer_process_id producer_root origin_handoff_status"
)


def _uuid4(value: Any) -> None:
    require(
        type(value) is str and uuid.UUID(value).version == 4 and str(uuid.UUID(value)) == value,
        "REPLAY_ATTEMPT_ID",
    )


def _attempt(out: Path, candidate: str) -> dict[str, Any]:
    a = _read(out, "attempt")
    f2.closed(a, _ATTEMPT_FIELDS)
    _uuid4(a["attempt_id"])
    require(type(a["process_id"]) is int and a["process_id"] > 0, "REPLAY_PROCESS_ID")
    for key in ("started_at", "finished_at"):
        value = a[key]
        require(type(value) is str and len(value) <= 80, "REPLAY_TIME")
        require(datetime.fromisoformat(value).utcoffset() is not None, "REPLAY_TIME")
    require(type(a["elapsed_seconds"]) is str and len(a["elapsed_seconds"]) <= 64, "REPLAY_TIME")
    try:
        elapsed = Decimal(a["elapsed_seconds"])
        require(elapsed.is_finite() and elapsed >= 0, "REPLAY_TIME")
    except InvalidOperation as error:
        raise F5Error("REPLAY_TIME") from error
    require(
        a["completed_stages"] == _STAGES
        and a["first_failure"] is None
        and a["origin_handoff_status"] == "ORIGIN_ARTIFACT_AND_SEMANTICS_VERIFIED",
        "REPLAY_COMPLETION",
    )
    require(
        type(a["producer_root"]) is str
        and Path(a["producer_root"]).is_absolute()
        and ".." not in Path(a["producer_root"]).parts,
        "REPLAY_PRODUCER_BINDING",
    )
    hex64(a["evidence_sha256"])
    require(
        a["evidence_sha256"] == sha256(regular_bytes(out / "evidence.json")).hexdigest(),
        "REPLAY_ATTEMPT",
    )
    pending = ("EVALUATED_REPLAY_PENDING", "NOT_RUN", INCOMPLETE)
    completed = ("SUCCEEDED", "VERIFIED", candidate)
    state = (a["execution_status"], a["replay_status"], a["comparison_status"])
    require(state in (pending, completed), "REPLAY_LIFECYCLE")
    if state == pending:
        require(
            all(
                a[k] is None for k in ("peer_evidence_sha256", "peer_attempt_id", "peer_process_id")
            ),
            "REPLAY_PENDING_RECEIPT",
        )
    else:
        _uuid4(a["peer_attempt_id"])
        require(type(a["peer_process_id"]) is int and a["peer_process_id"] > 0, "REPLAY_PROCESS_ID")
        hex64(a["peer_evidence_sha256"])
    return a


def _validate_pair(
    first: Path,
    second: Path,
    *,
    completed: bool,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], tuple[dict[str, Any], dict[str, Any]]]:
    """Read-only current pair validation, shared by completion and every report.

    IDs/stages/origin are cooperative metadata, not external producer attestation.
    Only both-pending or exact reciprocal both-completed pairs are eligible. A
    mixed/partially posted pair has no automatic recovery or rebinding path.
    """
    _run_root(first)
    _run_root(second)
    require(
        first != second
        and not os.path.samestat(first.stat(), second.stat())
        and not first.is_relative_to(second)
        and not second.is_relative_to(first),
        "REPLAY_SAME_DIRECTORY",
    )
    before = (_snapshot(first), _snapshot(second))
    a, b = verify_directory(first), verify_directory(second)
    require(a["candidate_class"] == b["candidate_class"], "REPLAY_MISMATCH")
    aa, bb = _attempt(first, a["candidate_class"]), _attempt(second, b["candidate_class"])
    require(
        aa["attempt_id"] != bb["attempt_id"] and aa["process_id"] != bb["process_id"],
        "REPLAY_NOT_FRESH_PROCESSES",
    )
    require(aa["producer_root"] == bb["producer_root"], "REPLAY_PRODUCER_BINDING")
    # Recompare every actual deterministic byte, including the evidence manifest.
    for name in ARTIFACTS:
        require(
            regular_bytes(first / (name + ".json")) == regular_bytes(second / (name + ".json")),
            "REPLAY_MISMATCH",
        )
    require(aa["execution_status"] == bb["execution_status"], "REPLAY_MIXED_LIFECYCLE")
    is_complete = aa["execution_status"] == "SUCCEEDED"
    require(not completed or is_complete, "REPLAY_NOT_VERIFIED")
    if is_complete:
        for own, peer in ((aa, bb), (bb, aa)):
            require(
                (own["peer_attempt_id"], own["peer_process_id"], own["peer_evidence_sha256"])
                == (peer["attempt_id"], peer["process_id"], peer["evidence_sha256"]),
                "REPLAY_PEER_BINDING",
            )
    require(before == (_snapshot(first), _snapshot(second)), "REPLAY_DRIFT")
    return a, aa, bb, before


def effective_report(out: Path, peer: Path | None = None) -> dict[str, Any]:
    """Read-only release requires BOTH current roots, bytes and reciprocal receipts.

    Expected damaged evidence returns no books/metrics. Runtime implementation
    errors outside the expected filesystem/schema errors still propagate.
    """
    try:
        _run_root(out)
        attempt = _read(out, "attempt")
        if attempt.get("first_failure") is not None:
            require(type(attempt["first_failure"]) is str, "REPLAY_FAILURE_REASON")
            raise F5Error(safe_reason(F5Error(attempt["first_failure"])))
        require(peer is not None, "REPLAY_PEER_REQUIRED")
        assert peer is not None
        result, _, _, _ = _validate_pair(out, peer, completed=True)
        return {
            "comparison_status": result["candidate_class"],
            "books": result["books"],
            "coverage": result["coverage"],
        }
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as error:
        return {
            "comparison_status": INCOMPLETE,
            "full_period_comparison": {"state": "NOT_COMPUTABLE", "reason": safe_reason(error)},
        }


def verify_pair(first: Path, second: Path) -> None:
    """Complete two pending attempts; exact completed-pair retry is read-only.

    No cross-root transaction is promised. A failed/truncated first or second
    same-file update is retained; mixed receipts fail closed on every reader and
    completion retry. No unrelated/unverified receipt is rewritten on failure.
    """
    result, aa, bb, before = _validate_pair(first, second, completed=False)
    if aa["execution_status"] == "SUCCEEDED":
        return
    require(before == (_snapshot(first), _snapshot(second)), "REPLAY_DRIFT")
    receipts = [
        own
        | {
            "replay_status": "VERIFIED",
            "comparison_status": result["candidate_class"],
            "execution_status": "SUCCEEDED",
            "peer_evidence_sha256": peer["evidence_sha256"],
            "peer_attempt_id": peer["attempt_id"],
            "peer_process_id": peer["process_id"],
        }
        for own, peer in ((aa, bb), (bb, aa))
    ]
    try:
        for index, out in enumerate((first, second)):
            if index == 1:
                require(_snapshot(second) == before[1], "REPLAY_DRIFT")
            _write(out, "attempt", receipts[index], update=True)
            after = _snapshot(out)
            require(
                after["root"] == before[index]["root"]
                and all(after[n + ".json"] == before[index][n + ".json"] for n in ARTIFACTS)
                and _read(out, "attempt") == receipts[index],
                "REPLAY_DRIFT",
            )
        _validate_pair(first, second, completed=True)
    except (OSError, ValueError, KeyError, TypeError) as error:
        # A write can raise after posting complete bytes. Retire ONLY our exact
        # first receipt, on the same verified inode/root; never repair a peer or
        # alter any deterministic file. Broken/pending receipts already block.
        try:
            _run_root(first)
            require(
                _file_stamp(first)[:2] == before[0]["root"][:2]
                and _file_stamp(first / "attempt.json")[:2] == before[0]["attempt.json"][0][:2],
                "REPLAY_DRIFT",
            )
            if _read(first, "attempt") == receipts[0]:
                reason = safe_reason(error)
                failed = receipts[0] | {
                    "execution_status": "FAILED",
                    "replay_status": "FAILED",
                    "comparison_status": INCOMPLETE,
                    "first_failure": reason
                    if reason != "INTERNAL_ERROR"
                    else "REPLAY_COMPLETION_WRITE_FAILED",
                }
                _write(first, "attempt", failed, update=True)
                require(_read(first, "attempt") == failed, "REPLAY_DRIFT")
        except (OSError, ValueError, KeyError, TypeError):
            error.add_note("REPLAY_FAILURE_RECEIPT_NOT_CONFIRMED_RETAIN_EVIDENCE")
        raise
