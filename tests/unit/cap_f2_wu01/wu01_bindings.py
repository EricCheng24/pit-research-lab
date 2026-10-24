"""Acceptance-only proposed predicates and independent frozen registry accounting."""

import hashlib
import json
import re
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path

SOURCE_PINS = (
    (
        "gate4_golden_v1.0.md",
        66992,
        "02716d2bd4d0983ed0b8d8e22f51dc7d7e2d0c0ed1d3debc6a6e50c9e9f3f3fb",
    ),
    (
        "p03_case_tier_ledger_v0.1.md",
        34753,
        "553776a9c0d2f6157894bd8b66686784276f731b8e83e8ecd49a11b2a401fe44",
    ),
)
DOCUMENTARY_IDS = (
    "A01-C01",
    "A01-C02",
    "A01-C03",
    "A01-C04",
    "A02-C01",
    "A02-C02",
    "A02-C03",
    "A02-C04",
    "A03-C01",
    "A03-C02",
    "A03-C03",
    "A03-C04",
    "A03-C05",
    "A03-C06",
    "A03-C07",
    "A04-C01",
    "A04-C02",
    "A04-C03",
    "A04-C04",
)
S1_CANDIDATES = (
    ("A01-C01", "COMPARE_SUBJECTS", "SAME", "NONE"),
    ("A01-C02", "COMPARE_SUBJECTS", "DIFFERENT", "SUBJECT_MISMATCH"),
    ("A01-C03", "COMPARE_SUBJECTS", "SAME", "NONE"),
    ("A01-C04", "COMPARE_SUBJECTS", "UNRESOLVED", "BASIS_UNRESOLVED"),
    ("A02-C01", "CHECK_BINDING", "BOUND", "NONE"),
    ("A02-C02", "CHECK_BINDING", "UNRESOLVED", "CONTENT_BINDING_INSUFFICIENT"),
    ("A02-C03", "INVENTORY_CONTENT", "BOUND", "NONE"),
    ("A02-C04", "CHECK_BINDING", "UNRESOLVED", "ATTRIBUTION_UNRESOLVED"),
)


def _pinned(path, size, expected):
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("unsafe source path")
    raw = path.read_bytes()
    if (len(raw), hashlib.sha256(raw).hexdigest()) != (size, expected):
        raise ValueError("source pin mismatch")
    return raw


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError("duplicate registry key")
        result[key] = value
    return result


def source_records():
    """Read unchanged narratives only on the acceptance side; never remove their marker."""
    data = Path(__file__).parent.parent / "cap_f2_wu00" / "data"
    lines = tuple(
        _pinned(data / "sources" / name, size, digest).decode().splitlines()
        for name, size, digest in SOURCE_PINS
    )
    raw = _pinned(
        data / "oracle" / "cases.json",
        163492,
        "5e37710f5082ffb1224571c846652187a7e70e2b877e4350ca51dd805fcd810d",
    )
    records = json.loads(raw, object_pairs_hook=_pairs)
    validate_registry(records, *lines)
    return records, lines


def _cells(row):
    return tuple(c.strip() for c in row.strip().strip("|").split("|"))


def validate_registry(records, golden, ledger):
    ids = [r["case_id"] for r in records]
    source_rows = {}
    for line, row in enumerate(golden, 1):
        match = re.match(r"\| `(A\d{2}-C\d{2}|RP\d{2}-T\d{2})`", row)
        if match:
            if match[1] in source_rows:
                raise ValueError("duplicate source row")
            source_rows[match[1]] = (line, row)
    if len(ids) != 110 or len(set(ids)) != 110 or set(ids) != set(source_rows):
        raise ValueError("registry ID mismatch")
    pairs = []
    for record in records:
        line, row = source_rows[record["case_id"]]
        if (record["source"]["line"], record["source"]["row"]) != (line, row):
            raise ValueError("Golden row mismatch")
        if tuple(record["normative_fields"].values()) != _cells(row):
            raise ValueError("normative field mismatch")
        lr = ledger[record["ledger"]["line"] - 1]
        if lr != record["ledger"]["row"] or not lr.startswith(
            "| `" + record["case_id"] + "` · G:" + str(line) + " |"
        ):
            raise ValueError("ledger row mismatch")
        tiers = record["normative_fields"]["tiers"].strip("`").split("/")
        if record["required_tiers"] != tiers or len(set(tiers)) != len(tiers):
            raise ValueError("tier mismatch")
        if record["case_id"].startswith("A"):
            if record["delta_ref"] != "D-" + record["case_id"]:
                raise ValueError("delta mismatch")
            if record["base_context"] != record["normative_fields"]["base"].strip("`"):
                raise ValueError("context mismatch")
            if record["owner"] != record["normative_fields"]["owner"].strip("`"):
                raise ValueError("owner mismatch")
            if _cells(lr)[3:8] != _cells(row)[2:7] or _cells(lr)[2] != _cells(row)[7]:
                raise ValueError("ledger semantic mismatch")
        if "UNSTRUCTURED_REQUIRES_REVIEW" not in json.dumps(record["semantic_comparison"]):
            raise ValueError("original narrative marker missing")
        pairs.extend((record["case_id"], tier) for tier in tiers)
    if len(pairs) != len(set(pairs)) or Counter(t for _, t in pairs) != dict(
        S=56, X=29, M=16, P=53
    ):
        raise ValueError("runtime accounting mismatch")
    if set(DOCUMENTARY_IDS) != {cid for cid in ids if cid[:3] in {"A01", "A02", "A03", "A04"}}:
        raise ValueError("documentary scope mismatch")


@dataclass(frozen=True)
class CandidateBinding:
    case_id: str
    golden_line: int
    ledger_line: int
    source_row: str
    ledger_row: str
    full_required_tiers: tuple[str, ...]
    operation: str
    candidate_state: str
    candidate_reason: str
    predicate_fields: tuple[str, ...]
    status: str = "PROPOSED / NOT_APPROVED"
    serialization: str = "wu01-binding-json-v1-CANDIDATE"


def candidate_bindings():
    records, _ = source_records()
    by_id = {r["case_id"]: r for r in records}
    return tuple(
        CandidateBinding(
            cid,
            by_id[cid]["source"]["line"],
            by_id[cid]["ledger"]["line"],
            by_id[cid]["source"]["row"],
            by_id[cid]["ledger"]["row"],
            tuple(by_id[cid]["required_tiers"]),
            operation,
            state,
            reason,
            (
                "typed_state_reason",
                "input_association",
                "source_numeric_type",
                "complete_scoped_paths",
                "accepted_rejected_attempts",
                "source_identity_inventories",
                "observed_prohibitions",
            ),
        )
        for cid, operation, state, reason in S1_CANDIDATES
    )


def validate_candidates(candidates):
    if len(candidates) != 8 or {c.case_id for c in candidates} != {r[0] for r in S1_CANDIDATES}:
        raise ValueError("candidate ID mismatch")
    reviewed_source = {c.case_id: c for c in candidate_bindings()}
    for candidate in candidates:
        if candidate != reviewed_source[candidate.case_id]:
            raise ValueError("candidate source/schema/tier/status mismatch")


def candidate_content_bytes(candidates):
    validate_candidates(candidates)
    return json.dumps(
        [asdict(c) for c in sorted(candidates, key=lambda c: c.case_id)],
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()


def candidate_content_sha256(candidates):
    return hashlib.sha256(candidate_content_bytes(candidates)).hexdigest()


def runtime_accounting():
    records, _ = source_records()
    return tuple(
        (r["case_id"], tier, "NOT_EXECUTED") for r in records for tier in r["required_tiers"]
    )


def documentary_accounting():
    executable_candidates = {r[0] for r in S1_CANDIDATES}
    return tuple(
        (cid, "PROPOSED_S_ONLY" if cid in executable_candidates else "UNIMPLEMENTED")
        for cid in DOCUMENTARY_IDS
    )
