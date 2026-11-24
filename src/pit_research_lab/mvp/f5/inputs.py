"""Trusted F3 import and F2 projection. No producer execution or policy price API."""

import hmac
import os
import secrets
import stat
import time
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from hashlib import sha256
from pathlib import Path
from typing import Any

from pit_research_lab.mvp.f2 import research_panel as f2
from pit_research_lab.mvp.f3_l1 import experiment as f3
from pit_research_lab.mvp.f3_l1 import replay as f3_replay
from pit_research_lab.mvp.f3_l1.contracts import FOLDS, LIMITATIONS, Protocol, fraction_read
from pit_research_lab.mvp.research_vslice.contracts import research_bytes

from .contracts import (
    CALENDAR_SHA,
    FIT_TIMES,
    ISSUERS,
    DecisionFact,
    DecisionForecast,
    DecisionObservation,
    IssuerInput,
    hex64,
    require,
)

_ORIGIN_KEY = secrets.token_bytes(32)

F3_PINS = {
    "contracts.py": "f5fb3ff7e3248e4cc756380e5deb4dd66d6c39eda9f5b8df867ba92652e3e635",
    "experiment.py": "d47e747f6d8b9882c70879a53fdf3f5cc91afc8733d7bf7bc91e9ea3844bf9d7",
    "replay.py": "a40897a91b3780b149eab25b0f2c47ddc3e1b5618f3cd46e3569a91fffbe45fd",
}


@dataclass(frozen=True, slots=True)
class ProducerOrigin:
    """Out-of-band Owner-established execution receipt, never inferred from F3 JSON.

    The trusted caller must establish this receipt separately. CLI deliberately
    cannot promote --f3-evidence-sha256 alone to an origin. Hostile callers are not
    sandboxed. No origin receipt has been supplied for the initial implementation.
    """

    directory: Path
    evidence_sha256: str
    producer_head: str
    python: str
    implementation: str
    source_pins: tuple[tuple[str, str, int], ...]
    receipt_id: str
    _grant: bytes = field(default=b"", repr=False, compare=False)

    def semantic(self) -> dict[str, Any]:
        return {
            "evidence_sha256": self.evidence_sha256,
            "producer_head": self.producer_head,
            "python": self.python,
            "implementation": self.implementation,
            "source_pins": [list(x) for x in self.source_pins],
            "receipt_id": self.receipt_id,
        }


def _establish_owner_origin(origin: ProducerOrigin) -> ProducerOrigin:
    """Trusted embedding only AFTER external Owner receipt/origin establishment.

    Called only after the explicitly injected trusted witness returns. This
    process-local grant binds the separately established receipt; it does not
    prove execution, authenticate a third party or provide hostile-code isolation.
    """
    body = {"directory": str(origin.directory), "receipt": origin.semantic()}
    return replace(origin, _grant=hmac.digest(_ORIGIN_KEY, research_bytes(body), "sha256"))


# A callable is a cooperative trusted-embedding capability, not external proof.
# It is never loaded from a CLI flag, environment variable or receipt file.
OriginWitness = Callable[[Path, str], ProducerOrigin]


def establish_from_witness(
    directory: Path | None, expected: str | None, witness: OriginWitness | None
) -> ProducerOrigin:
    """Gate A: bind an independently verified execution receipt in THIS process.

    The authorized embedding must supply trusted code which independently checks
    original execution/witness evidence and returns its ProducerOrigin record.
    The embedding must repeat that check in every fresh process; serialize only
    the external receipt, never a grant. No implementation of that external
    authority is provided here. An arbitrary callable is not authenticated by us.

    This function checks only the returned record's request binding, then grants
    local cooperative use. Gate B (original artifact/attempt/closure) and gate C
    (source semantics) remain mandatory inside import_f3. A unit witness is not
    a genuine producer. Default command-line execution supplies no witness.
    """
    require(directory is not None and expected is not None and callable(witness), "BLOCKED_INPUT")
    assert directory is not None and expected is not None and witness is not None
    hex64(expected)
    receipt = witness(directory, expected)
    require(type(receipt) is ProducerOrigin, "ORIGIN_WITNESS_RECORD")
    require(
        receipt.directory == directory
        and receipt.evidence_sha256 == expected
        and type(receipt.receipt_id) is str
        and bool(receipt.receipt_id),
        "ORIGIN_WITNESS_BINDING",
    )
    require(receipt._grant == b"", "ORIGIN_WITNESS_REUSED_GRANT")
    return _establish_owner_origin(receipt)


def regular_bytes(path: Path, *, limit: int = 64 * 1024 * 1024) -> bytes:
    require(path.is_absolute() and ".." not in path.parts, "UNSAFE_INPUT_PATH")
    require(not any(p.is_symlink() for p in (path, *path.parents)), "INPUT_SYMLINK")
    m = path.lstat()
    require(
        stat.S_ISREG(m.st_mode)
        and m.st_uid == os.getuid()
        and not m.st_mode & 0o022
        and m.st_size <= limit,
        "INPUT_FILE",
    )
    raw = path.read_bytes()
    require(len(raw) == m.st_size and len(raw) <= limit, "INPUT_DRIFT")
    return raw


def require_origin(
    directory: Path | None, expected: str | None, origin: ProducerOrigin | None
) -> ProducerOrigin:
    require(origin is not None and directory is not None and expected is not None, "BLOCKED_INPUT")
    assert origin is not None and directory is not None and expected is not None
    grant_body = {"directory": str(origin.directory), "receipt": origin.semantic()}
    require(
        hmac.compare_digest(
            origin._grant, hmac.digest(_ORIGIN_KEY, research_bytes(grant_body), "sha256")
        ),
        "PRODUCER_ORIGIN_NOT_ESTABLISHED",
    )
    hex64(expected)
    require(
        type(origin) is ProducerOrigin
        and origin.directory == directory
        and origin.evidence_sha256 == expected
        and bool(origin.receipt_id),
        "PRODUCER_ORIGIN",
    )
    require(
        len(origin.producer_head) == 40
        and bool(origin.python)
        and origin.implementation == "CPython",
        "PRODUCER_ORIGIN",
    )
    require(
        directory.is_absolute()
        and ".." not in directory.parts
        and not any(p.is_symlink() for p in (directory, *directory.parents)),
        "UNSAFE_INPUT_PATH",
    )
    m = directory.lstat()
    require(
        stat.S_ISDIR(m.st_mode) and m.st_uid == os.getuid() and stat.S_IMODE(m.st_mode) == 0o700,
        "PRODUCER_ROOT",
    )
    require(not directory.is_relative_to(f2.ROOT), "INPUT_IN_CHECKOUT")
    names = {n + ".json" for n in (*f3_replay.ARTIFACTS, "evidence", "attempt")}
    require({p.name for p in directory.iterdir()} == names, "ARTIFACT_INVENTORY")
    raw = {n: regular_bytes(directory / n) for n in sorted(names)}
    require(sum(map(len, raw.values())) <= 256 * 1024 * 1024, "ARTIFACT_BUDGET")
    require(sha256(raw["evidence.json"]).hexdigest() == expected, "PRODUCER_EVIDENCE_PIN")
    return origin


def artifact(directory: Path, name: str) -> dict[str, Any]:
    value = f2.decode(regular_bytes(directory / (name + ".json")))
    f2.closed(value, "schema non_if03 payload")
    require(value["non_if03"] is True and type(value["payload"]) is dict, "ARTIFACT_SCHEMA")
    result: dict[str, Any] = value["payload"]
    return result


def validate_provenance(spec: dict[str, Any], origin: ProducerOrigin) -> None:
    p = spec["provenance"]
    require(
        p["base_head"] == origin.producer_head
        and p["code_claim"] == "ACTUAL_UNCOMMITTED_WORKTREE_BYTES_NOT_HEAD_CONTENT",
        "PRODUCER_PROVENANCE",
    )
    require(
        p["runtime"] == {"python": origin.python, "implementation": origin.implementation}
        and origin.python.startswith("3.12."),
        "PRODUCER_RUNTIME",
    )
    recorded = tuple((x["path"], x["sha256"], x["byte_length"]) for x in p["files"])
    require(
        recorded == origin.source_pins
        and tuple(sorted(recorded)) == recorded
        and len(set(x[0] for x in recorded)) == len(recorded),
        "PRODUCER_CODE_PINS",
    )
    current = f3_replay.provenance()["files"]
    require(
        recorded == tuple((x["path"], x["sha256"], x["byte_length"]) for x in current),
        "PRODUCER_CODE_CLOSURE",
    )
    for name, expected in F3_PINS.items():
        require(
            sha256((f2.ROOT / "src/pit_research_lab/mvp/f3_l1" / name).read_bytes()).hexdigest()
            == expected,
            "F3_CODE_PIN",
        )


def fact(value: f2.RevenueFact, cutoff: str) -> DecisionFact:
    public = value.available_at is not None and f2.instant(value.available_at) < f2.instant(cutoff)
    return DecisionFact(
        value.month,
        value.state,
        value.amount,
        value.unit,
        value.basis,
        value.source_ref if public else None,
        value.version_ref if public else None,
        value.publication if public else None,
        value.available_at if public else None,
        value.native_state,
        value.reason,
        value.qualification_ref,
    )


def project(
    observation: f2.PanelObservation, row: dict[str, Any], state: dict[str, Any]
) -> IssuerInput:
    o = f2.verify_observation(observation)
    require(
        state["dataset_digest"] == o.dataset_digest
        and state["protocol_ref"] == Protocol().identity,
        "FORECAST_STATE_DATASET_PROTOCOL",
    )
    f2.closed(row, "sample_id issuer tick decision_time binding_id state value reason")
    require(
        (row["sample_id"], row["issuer"], row["tick"], row["decision_time"], row["binding_id"])
        == (o.sample_id, o.issuer, o.tick, o.cutoff, o.binding_id),
        "FORECAST_BINDING",
    )
    value = fraction_read(row["value"]) if row["value"] is not None else None
    forecast = DecisionForecast(
        o.sample_id,
        o.issuer,
        o.tick,
        o.cutoff,
        o.dataset_digest,
        CALENDAR_SHA,
        o.binding_id,
        state["fold"],
        state["fit_cutoff"],
        state["protocol_ref"],
        state["state_id"],
        "OLS_INTERCEPT_ONE_REGRESSOR_V1",
        20,
        row["state"],
        value,
        row["reason"],
    )
    forecast.validate()
    reason = next(
        ("INFORMATION_" + x.state for x in (o.current, o.previous) if x.state != "KNOWN"), "NONE"
    )
    return IssuerInput(
        o.issuer,
        o.sample_id,
        o.binding_id,
        fact(o.current, o.cutoff),
        fact(o.previous, o.cutoff),
        f3.growth(o) if reason == "NONE" else None,
        "KNOWN" if reason == "NONE" else "UNAVAILABLE",
        reason,
        forecast,
        reason == "NONE",
        reason,
    )


def verify_semantics(
    values: dict[str, Any], panel: f2.ResearchPanel
) -> tuple[DecisionObservation, ...]:
    """Trusted kernel reconstruction; prior mature labels only, never OOS scoring."""
    started = time.monotonic()
    protocol = Protocol()
    spec = values["spec"]
    require(
        spec["protocol"] == protocol.payload()
        and spec["protocol_ref"] == protocol.identity
        and spec["dataset_digest"] == panel.dataset_digest,
        "F3_PROTOCOL_DATASET",
    )
    expected_bindings = [panel.observation(i, t).public() for t in range(96) for i in ISSUERS]
    require(
        values["bindings"]["observations"] == expected_bindings and len(expected_bindings) == 480,
        "HISTORICAL_BINDING_GRID",
    )
    require(
        values["bindings"]["qualification_receipts"] == panel.qualification_receipts(),
        "QUALIFICATION_RECEIPTS",
    )
    require(
        len(values["states"]["states"])
        == len(values["predictions"]["batches"])
        == len(values["folds"]["training"])
        == 2,
        "FOLD_GRID",
    )
    output, handoff = [], []
    for index, fold in enumerate(FOLDS):
        require(time.monotonic() - started <= 600, "VERIFICATION_BUDGET")
        training = f3.training_set(panel, fold, protocol)
        require(training.fit_cutoff == FIT_TIMES[index], "FIT_CUTOFF_MISMATCH")
        require(
            values["folds"]["training"][index]
            == {"training_ref": f2.digest(training.payload()), **training.payload()},
            "TRAINING_MEMBERSHIP_MISMATCH",
        )
        # Existing exact F3 kernel, no tuning/new framework or OOS-label capability.
        state = f3.fit(training, protocol)
        state_payload = {"state_id": state.state_id, **state.payload()}
        require(values["states"]["states"][index] == state_payload, "FITTED_STATE_MISMATCH")
        observations = tuple(
            panel.observation(i, t) for t in range(fold.test_start, fold.test_end) for i in ISSUERS
        )
        batch = f3.predict(state, observations, protocol)
        require(
            values["predictions"]["batches"][index]
            == {"prediction_id": batch.prediction_id, **batch.payload()},
            "PREDICTION_SEMANTICS",
        )
        for tick in range(fold.test_start, fold.test_end):
            rows = [r for r in batch.rows if r.tick == tick]
            cells = tuple(
                project(panel.observation(r.issuer, tick), r.payload(), state_payload) for r in rows
            )
            obs = DecisionObservation(
                tick, panel.cutoffs[tick], CALENDAR_SHA, panel.dataset_digest, cells
            )
            obs.validate(production=True)
            output.append(obs)
        for row in batch.rows:
            handoff.append(
                {
                    **row.payload(),
                    "horizon": "20_SUBSEQUENT_SESSIONS",
                    "meaning": "UNADJUSTED_SIMPLE_RETURN_FORECAST_NOT_ACTION",
                    "method": "OLS_INTERCEPT_ONE_REGRESSOR_V1",
                    "fold": fold.name,
                    "fit_cutoff": training.fit_cutoff,
                    "state_id": state.state_id,
                    "dataset_digest": panel.dataset_digest,
                    "protocol_ref": protocol.identity,
                    "research_result_ref": values["result_ref"],
                    "limitations": list(LIMITATIONS),
                    "eligibility": "AUTHORED_SYNTHETIC_LOCAL_RELEASE_NO_APP_ADMISSION",
                }
            )
    require(values["handoff"]["rows"] == handoff and len(handoff) == 240, "HANDOFF_SEMANTICS")
    return tuple(output)


def import_f3(
    directory: Path | None, expected: str | None, origin: ProducerOrigin | None
) -> tuple[tuple[DecisionObservation, ...], dict[str, Any]]:
    receipt = require_origin(directory, expected, origin)
    assert directory is not None
    # The independently established origin is checked BEFORE any link verifier.
    from .prices import check_compatibility

    check_compatibility()
    for name, pin in F3_PINS.items():
        require(
            sha256(regular_bytes(f2.ROOT / "src/pit_research_lab/mvp/f3_l1" / name)).hexdigest()
            == pin,
            "F3_CODE_PIN",
        )
    # Gate B: original artifacts, attempt and producer closure; not origin issuance.
    f3_replay.verify_directory(directory)
    values: dict[str, Any] = {n: artifact(directory, n) for n in f3_replay.ARTIFACTS}
    validate_provenance(values["spec"], receipt)
    values["result_ref"] = sha256(regular_bytes(directory / "result.json")).hexdigest()
    panel = f2.load_panel()
    # Gate C: exact lawful historical training and OOS prediction reconstruction.
    observations = verify_semantics(values, panel)
    require_origin(directory, expected, origin)
    return observations, receipt.semantic()
