"""Acceptance-only source-authenticated registry; never imported by input/domain code."""

import hashlib
import json
import re
from collections import Counter
from pathlib import Path

DATA = Path(__file__).parent / "data"
SOURCE_PINS = {
    "gate4_golden_v1.0.md": (
        66992,
        "02716d2bd4d0983ed0b8d8e22f51dc7d7e2d0c0ed1d3debc6a6e50c9e9f3f3fb",
    ),
    "p03_case_tier_ledger_v0.1.md": (
        34753,
        "553776a9c0d2f6157894bd8b66686784276f731b8e83e8ecd49a11b2a401fe44",
    ),
}


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError(f"duplicate oracle key: {key}")
        result[key] = value
    return result


def source_texts():
    result = []
    for filename, pin in SOURCE_PINS.items():
        data = (DATA / "sources" / filename).read_bytes()
        if (len(data), hashlib.sha256(data).hexdigest()) != pin:
            raise ValueError("ARTIFACT_IDENTITY_MISMATCH")
        result.append(data.decode("utf-8").splitlines())
    return result


def cells(row):
    return [cell.strip() for cell in row.strip().strip("|").split("|")]


def validate(records):
    golden, ledger = source_texts()
    if not isinstance(records, list):
        raise ValueError("registry must preserve duplicate detection")
    ids = [record["case_id"] for record in records]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate case ID")
    source_rows = {}
    for number, row in enumerate(golden, 1):
        match = re.match(r"\| `(A\d{2}-C\d{2}|RP\d{2}-T\d{2})`", row)
        if match:
            if match[1] in source_rows:
                raise ValueError("duplicate source row")
            source_rows[match[1]] = (number, row)
    if set(ids) != set(source_rows) or len(ids) != 110:
        raise ValueError("missing/extra case ID")
    pairs = []
    deltas = []
    for record in records:
        cid = record["case_id"]
        line, row = source_rows[cid]
        if record["source"]["line"] != line or record["source"]["row"] != row:
            raise ValueError("Golden source row mismatch")
        fields = record["normative_fields"]
        expected_keys = (
            [
                "case_delta",
                "base",
                "delta",
                "expected",
                "reason",
                "lineage_exclusions",
                "forbidden",
                "tiers",
                "owner",
            ]
            if cid.startswith("A")
            else ["case_id", "fault_interleaving", "oracle_forbidden_shortcut", "tiers"]
        )
        if set(fields) != set(expected_keys) or [fields[k] for k in expected_keys] != cells(row):
            raise ValueError("normative assertion omission/mismatch")
        tiers = fields["tiers"].strip("`").split("/")
        if record["required_tiers"] != tiers or len(tiers) != len(set(tiers)):
            raise ValueError("row-specific tier mismatch")
        if cid.startswith("A"):
            if record["delta_ref"] != "D-" + cid or record["base_context"] != fields["base"].strip(
                "`"
            ):
                raise ValueError("Base/Delta mismatch")
            if record["owner"] != fields["owner"].strip("`"):
                raise ValueError("owner mismatch")
            deltas.append(record["delta_ref"])
        ln = record["ledger"]["line"]
        lr = ledger[ln - 1]
        if lr != record["ledger"]["row"] or not lr.startswith(f"| `{cid}` · G:{line} |"):
            raise ValueError("LEDGER_SOURCE_MISMATCH")
        lf = cells(lr)
        gf = cells(row)
        if cid.startswith("A"):
            equal = (
                lf[1].replace("`", "") == fields["base"].strip("`") + " / " + record["delta_ref"]
                and gf[7] == lf[2]
                and gf[2:7] == lf[3:8]
            )
        else:
            equal = gf[3] == lf[1] and gf[1:3] == lf[2:4]
        if not equal:
            raise ValueError("LEDGER_SOURCE_MISMATCH")
        pairs.extend((cid, tier) for tier in tiers)
    if len(deltas) != 64 or len(set(deltas)) != 64:
        raise ValueError("64-delta identity mismatch")
    if len(pairs) != len(set(pairs)) or Counter(t for _, t in pairs) != dict(
        S=56, X=29, M=16, P=53
    ):
        raise ValueError("154-obligation accounting mismatch")
    return records


def load_cases():
    records = json.loads((DATA / "oracle" / "cases.json").read_text(), object_pairs_hook=_pairs)
    return validate(records)


def load_vectors():
    vectors = json.loads(
        (DATA / "oracle" / "reference_vectors.json").read_text(), object_pairs_hook=_pairs
    )
    ids = [v["vector_id"] for v in vectors]
    if len(ids) != 5 or len(set(ids)) != 5:
        raise ValueError("vector identities")
    for vector in vectors:
        data = bytes.fromhex(vector["payload_hex"])
        if (len(data), hashlib.sha256(data).hexdigest()) != (
            vector["byte_length"],
            vector["sha256"],
        ):
            raise ValueError("vector integrity")
    return vectors
