"""Integrity of a reviewed metadata overlay; no Codec/Native/authorization claim.

The literal manifest hash is external to the manifest. Reviewed expectations are
stored data, never regenerated from the author predicate or a production encoder.
Record hashing below is ordinary repository metadata JSON, not IF-03 typed JSON.
"""

import copy
import json
import re
import stat
from hashlib import sha1, sha256
from pathlib import Path, PurePosixPath
from zipfile import ZipFile

import pytest

ROOT = Path(__file__).resolve().parents[3]
AUTHOR = "tests/fixtures/mvp_if03/wu05_oracle01_v0_1/"
OLD = "tests/fixtures/mvp_if03/oracle01_v0_1/"
MANIFEST = ROOT / "tests/fixtures/mvp_if03/wu05_oracle02_scoped_freeze_v0_1/FREEZE_MANIFEST.json"
MANIFEST_SHA256 = "9099a4faede3c893ec57dc936d33741b1c6a1ac5b8b6f612d56219808d4a73b1"
BASELINE = "c2d66cf880d2e34d9f95f9351cbb616e3d5a7783"
FORMAT = "WU05_ORACLE02_SCOPED_FREEZE_MANIFEST_v0.1"
METADATA_SERIALIZATION = (
    'Python json.dumps(record, sort_keys=True, separators=(",", ":"), '
    'ensure_ascii=False, allow_nan=False).encode("utf-8"); no trailing newline; '
    "preserve array order and Unicode scalar sequences."
)
RELATIONS = {
    "R-UNICODE": "DISTINCT_SCALAR_BYTES",
    "R-RAW-MUTATION": "DIFFERENT_PREIMAGE_AND_FRAME",
    "R-FOUR-CUTOFFS": "DIAGNOSTIC_DECLARATIONS_ONLY",
    "R-D06-CONSISTENT": "NOT_SUPPLIED",
    "R-D06-POLICY-CHANGE": "DEPENDENCY_PREIMAGE_DIFFERS",
    "R-EVIDENCE-DIRECTION": "ACYCLIC_SYMBOLIC_ONLY",
}
DOCUMENTARY = {
    "R-REDACTION",
    "R-ATTEMPT-SEPARATION",
    "R-DECISION-EVALUATION",
    "P2-DEPTH-64",
    "P2-DEPTH-65",
}
BLOCKED = {f"BLO-{i:02}" for i in range(1, 10)} | {"BLO-TIME"}
COUNTS = {
    "authoring_total": 110,
    "included_complete_positives": 8,
    "included_narrow_refusals": 80,
    "included_executed_relations": 6,
    "included_total": 94,
    "excluded_documentary": 5,
    "excluded_blocked": 10,
    "excluded_deferred": 1,
    "excluded_total": 16,
}
FLAGS = {
    "diagnostic_only": True,
    "admission_eligible": False,
    "trust": "NOT_TRUSTED_PIT_EVIDENCE",
    "source_authentication": "NOT_ESTABLISHED",
    "disposition": "INTEGRATED_PROVISIONAL",
}
CLAIMS = {
    "complete_positives": "EXISTING_COMPLETE_SOURCE_BYTES_GOLDEN_REAFFIRMED",
    "narrow_refusals": "EXPECTED_REFUSAL_REVIEWED_PRODUCTION_CONFORMANCE_NOT_RUN",
    "executed_relations": "RELATIONAL_EXPECTATION_REVIEWED_ACTUAL_RESOURCE_ISSUANCE_NOT_RUN",
}


def need(condition, reason):
    if not condition:
        raise ValueError(reason)


def closed(value, keys):
    need(type(value) is dict and set(value) == set(keys), "metadata fields")


def strict_json(raw):
    def pairs(entries):
        result = {}
        for key, value in entries:
            need(key not in result, "duplicate metadata key")
            result[key] = value
        return result

    def reject_constant(_):
        raise ValueError("nonfinite metadata number")

    need(not raw.startswith(b"\xef\xbb\xbf"), "metadata BOM")
    return json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=reject_constant)


def metadata_hash(value):
    # Exactly the declared metadata serialization. Never an App domain digest.
    raw = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")
    return sha256(raw).hexdigest()


def repo_bytes(name):
    need(type(name) is str and "\\" not in name and ":" not in name, "repository path")
    p = PurePosixPath(name)
    need(
        not p.is_absolute()
        and p.as_posix() == name
        and all(part not in ("", ".", "..") for part in p.parts),
        "repository path",
    )
    path = ROOT
    for part in p.parts:
        path = path / part
        need(not path.is_symlink(), "repository symlink")
    need(path.is_file(), "repository file")
    return path.read_bytes()


def check_pin(pin, raw, baseline=False):
    closed(pin, {"path", "byte_length", "sha256"} | ({"git_blob_sha1"} if baseline else set()))
    need(type(pin["byte_length"]) is int and pin["byte_length"] >= 0, "pin length type")
    need(re.fullmatch("[a-f0-9]{64}", pin["sha256"]) is not None, "pin SHA-256 format")
    need(
        len(raw) == pin["byte_length"] and sha256(raw).hexdigest() == pin["sha256"],
        "source bytes changed",
    )
    if baseline:
        need(re.fullmatch("[a-f0-9]{40}", pin["git_blob_sha1"]) is not None, "pin blob format")
        need(
            sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest() == pin["git_blob_sha1"],
            "baseline blob changed",
        )


def manifest_from_bytes(raw):
    need(
        sha256(raw).hexdigest() == MANIFEST_SHA256,
        "manifest bytes changed; new review/version required",
    )
    m = strict_json(raw)
    closed(
        m,
        "format work_unit baseline status metadata_record_integrity counts ratified_contracts "
        "baseline_sources authoring_sources limited_golden review_provenance group_claims "
        "included excluded boundaries outstanding_blockers revision_policy".split(),
    )
    need(m["format"] == FORMAT and m["work_unit"] == "MVP-F2-WU05-ORACLE02-SF-01", "version")
    need(
        m["baseline"]
        == {
            "commit": BASELINE,
            "authoring_branch": "mvp/f2-wu05-oracle01",
            "origin": "https://github.com/EricCheng24/pit-research-lab.git",
        },
        "baseline identity",
    )
    need(m["status"] == "MATERIALIZED_CANDIDATE_PENDING_INDEPENDENT_INTEGRATION_REVIEW", "status")
    closed(m["metadata_record_integrity"], {"algorithm", "serialization", "scope"})
    need(
        m["metadata_record_integrity"]["algorithm"] == "SHA-256"
        and m["metadata_record_integrity"]["serialization"] == METADATA_SERIALIZATION,
        "metadata serialization",
    )
    need(m["counts"] == COUNTS and all(type(n) is int for n in m["counts"].values()), "counts")
    need(m["boundaries"]["scope_flags"] == FLAGS, "diagnostic flags")
    need(m["outstanding_blockers"] and m["revision_policy"], "remaining gates")
    closed(m["group_claims"], CLAIMS)
    for group, classification in CLAIMS.items():
        closed(m["group_claims"][group], {"classification", "scope"})
        need(
            m["group_claims"][group]["classification"] == classification
            and m["group_claims"][group]["scope"],
            "claim boundary",
        )
    # No file self-hash: the literal integrity anchor lives only in this test.
    return m


def check_scope(m, ledger):
    closed(ledger, {"format", "baseline", "cases"})
    need(
        ledger["format"] == "wu05-oracle01-cases-v0.1" and ledger["baseline"] == BASELINE,
        "ledger identity",
    )
    records = ledger["cases"]
    need(type(records) is list and len(records) == 110, "ledger count")
    ids = [r["case_id"] for r in records]
    need(len(set(ids)) == 110, "duplicate case identity")
    by_id = {r["case_id"]: r for r in records}
    closed(m["included"], CLAIMS)
    included_ids = []
    statuses = {
        "complete_positives": "VALID_COMPLETE_DOMAIN_POSITIVE",
        "narrow_refusals": "EXECUTABLE_REFUSAL",
        "executed_relations": "CONTRACT_RELATIONAL_ASSERTION",
    }
    for group, count in (
        ("complete_positives", 8),
        ("narrow_refusals", 80),
        ("executed_relations", 6),
    ):
        rows = m["included"][group]
        need(type(rows) is list and len(rows) == count, "included count")
        for row in rows:
            keys = {"case_id", "record_metadata_sha256", "record", "review_basis"}
            closed(row, keys | ({"original_golden"} if group == "complete_positives" else set()))
            cid = row["case_id"]
            need(cid in by_id, "missing case")
            record = by_id[cid]
            need(row["record"] == record and row["record"]["case_id"] == cid, "record content")
            need(metadata_hash(record) == row["record_metadata_sha256"], "record integrity")
            need(
                record["status"] == statuses[group] and record["execution"] == "TEST_ONLY",
                "included claim promotion",
            )
            basis = (
                "OWNER_REPORTED_REM1_INDEPENDENT_DELTA_ACCEPTANCE"
                if cid == "N-OWN-ENVELOPE"
                else "ORACLE02_INDEPENDENT_REVIEW"
            )
            need(row["review_basis"] == basis, "review provenance")
            included_ids.append(cid)
    need(
        [r["case_id"] for r in m["included"]["complete_positives"]]
        == [f"B{i:02}" for i in range(1, 9)],
        "complete positive membership",
    )
    need(
        [r["case_id"] for r in m["included"]["narrow_refusals"]]
        == [cid for cid in ids if cid.startswith("N-")],
        "refusal membership/order",
    )
    need(
        [r["case_id"] for r in m["included"]["executed_relations"]] == list(RELATIONS),
        "relation membership/order",
    )
    for cid, expected in RELATIONS.items():
        need(by_id[cid]["expected"] == expected, "bounded relation semantics")
    need(
        by_id["N-OWN-ENVELOPE"]["expected"]
        == {"category": "STRUCTURALLY_INVALID", "code": "REF_CYCLE"},
        "own digest diagnostic",
    )
    need(
        re.fullmatch("[a-f0-9]{64}", by_id["N-OWN-ENVELOPE"]["input"]["own_digest_claim"])
        is not None,
        "explicit own digest claim",
    )
    need("AD01-08" in by_id["N-OWN-ENVELOPE"]["source_clause"][0]["clause"], "own digest clause")
    for cid in ("N-UNKNOWN", "N-MISSING"):
        need(
            by_id[cid]["expected"] == {"category": "STRUCTURALLY_INVALID", "code": "CLOSED_FIELDS"},
            "ordinary field diagnostic",
        )
    need(len(included_ids) == len(set(included_ids)) == 94, "included duplicate")
    excluded_ids = []
    for row in m["excluded"]:
        closed(
            row,
            {
                "case_id",
                "record_metadata_sha256",
                "record_status",
                "execution",
                "freeze_treatment",
                "reason",
            },
        )
        cid = row["case_id"]
        need(cid in by_id and row["freeze_treatment"] == "EXCLUDED", "exclusion")
        record = by_id[cid]
        need(
            metadata_hash(record) == row["record_metadata_sha256"]
            and record["status"] == row["record_status"],
            "excluded record changed",
        )
        need(
            record["execution"] == row["execution"] == "NOT_EXECUTED"
            and record["operation"] is None,
            "excluded execution",
        )
        status = (
            "CONTRACT_RELATIONAL_ASSERTION"
            if cid in DOCUMENTARY
            else "BLOCKED_NOT_CONSTRUCTIBLE"
            if cid in BLOCKED
            else "DEFERRED_SEPARATE_OWNER"
        )
        reason = (
            "PENDING_OWNER_BOUNDARY_DECISION"
            if cid.startswith("P2-DEPTH-")
            else "DOCUMENTARY_NOT_EXECUTED"
            if cid in DOCUMENTARY
            else status
        )
        need(row["record_status"] == status and row["reason"] == reason, "excluded reason/status")
        if cid in BLOCKED or cid == "DEFER-GATES":
            need(
                record["expected"] == {"category": "NOT_CONSTRUCTIBLE", "expected_digest": None},
                "blocked positive identity",
            )
        if cid.startswith("P2-DEPTH-"):
            need(set(record["expected"]) == {"root_depth_1", "root_depth_0"}, "conditional depth")
        excluded_ids.append(cid)
    need(len(excluded_ids) == len(set(excluded_ids)) == 16, "excluded count/duplicate")
    need(set(excluded_ids) == DOCUMENTARY | BLOCKED | {"DEFER-GATES"}, "excluded membership")
    need(
        not set(included_ids) & set(excluded_ids)
        and set(ids) == set(included_ids) | set(excluded_ids),
        "complete disjoint accounting",
    )


def check_sources(m, declared):
    need(
        declared["baseline"] == BASELINE and declared["files"] == m["baseline_sources"],
        "source pin table changed",
    )
    for key, count, is_baseline in (
        ("baseline_sources", 53, True),
        ("authoring_sources", 8, False),
    ):
        pins = m[key]
        need(len(pins) == len({p["path"] for p in pins}) == count, "source inventory")
        for pin in pins:
            check_pin(pin, repo_bytes(pin["path"]), is_baseline)
    indexed = {p["path"]: p for p in m["baseline_sources"]}
    need(
        m["ratified_contracts"]
        == [
            indexed[p]
            for p in (
                "docs/mvp/v1.0/shared-interface-contract-v0.1.md",
                "docs/mvp/v1.0/ux-adr-01-temporal-execution-contract-v0.1.md",
            )
        ],
        "ratified sources",
    )
    need(
        [p["git_blob_sha1"] for p in m["ratified_contracts"]]
        == [
            "d028005f6ac854fc3cde965b562dba4e449159cf",
            "96d463c40a49d94e0b206be3851e26063fc6c581",
        ],
        "ratified blob identity",
    )
    for key in ("freeze_note", "manifest", "archive"):
        pin = m["limited_golden"][key]
        need(pin == indexed[pin["path"]], "original Golden source pin")


@pytest.fixture(scope="module")
def scope():
    return manifest_from_bytes(MANIFEST.read_bytes())


@pytest.fixture(scope="module")
def ledger():
    return strict_json(repo_bytes(AUTHOR + "cases.json"))


def test_exact_reviewed_manifest_and_110_record_accounting(scope, ledger):
    check_scope(scope, ledger)


def test_approved_baseline_and_corrected_authoring_bytes(scope):
    check_sources(scope, strict_json(repo_bytes(AUTHOR + "source_pins.json")))
    coverage = strict_json(repo_bytes(AUTHOR + "domain_coverage.json"))
    seq = next(d for d in coverage["domains"] if d["domain"] == "TEMPORAL-SEQUENCE")
    assert {"ORIGIN", "TIMEZONE_RULES"} <= set(seq["required_resource_roles"])
    assert "conditional ProvenanceParent union" in coverage["resource_role_rule"]


def test_review_provenance_and_non_conformance_boundaries(scope):
    provenance = scope["review_provenance"]
    closed(provenance, {"external_evidence", "pre_rem1_report_boundary", "rem1_acceptance"})
    assert len({p["evidence_id"] for p in provenance["external_evidence"]}) == 6
    for pin in provenance["external_evidence"]:
        closed(
            pin,
            {
                "evidence_id",
                "original_local_path",
                "byte_length",
                "sha256",
                "role",
                "runtime_dependency",
            },
        )
        assert type(pin["byte_length"]) is int and pin["byte_length"] > 0
        assert re.fullmatch("[a-f0-9]{64}", pin["sha256"]) and pin["runtime_dependency"] is False
    # These are historical external evidence pins, not portable test dependencies.
    acceptance = provenance["rem1_acceptance"]
    assert acceptance["basis"] == "OWNER_SUPPLIED_ACCEPTED_INDEPENDENT_DELTA_OUTCOME"
    assert acceptance["accepted_disposition"] == "WU05_ORACLE02_REM1_INDEPENDENT_DELTA_ACCEPTED"
    assert acceptance["separate_independent_delta_report"] == "NOT_SUPPLIED_AS_A_LOCAL_FILE"
    assert (
        acceptance["reviewer_signature_identity_and_historical_clock"]
        == "NOT_SUPPLIED_NOT_FABRICATED"
    )
    b = scope["boundaries"]
    assert b["scope_flags"] == FLAGS and "PENDING_OWNER_BOUNDARY_DECISION" in b["depth_boundary"]
    assert "unrelated unknown field" in b["author_reference_predicate_limitation"]
    assert b["production_codec"] == "NOT_IMPLEMENTED_NOT_RUN"
    assert b["native_channel_a_and_production_channel_b"] == "NOT_RUN_NOT_ACCEPTED"


def test_original_archive_24_binaries_and_eight_expected_envelopes(scope):
    old = strict_json(repo_bytes(OLD + "FREEZE_MANIFEST.json"))
    raw_archive = repo_bytes(scope["limited_golden"]["archive"]["path"])
    assert len(raw_archive) == 383476
    assert (
        sha256(raw_archive).hexdigest()
        == "b3b74b713dbd43b6ef70f32c6c666c0caf8e5ac08c27d96a2d025cda038bdd34"
    )
    with ZipFile(ROOT / scope["limited_golden"]["archive"]["path"]) as archive:
        infos = archive.infolist()
        assert len(infos) == len({i.filename for i in infos}) == 409
        for info in infos:
            p = PurePosixPath(info.filename)
            assert not p.is_absolute() and ".." not in p.parts
            assert "\\" not in info.filename and ":" not in info.filename and not info.is_dir()
            assert (info.external_attr >> 16) & 0o170000 != stat.S_IFLNK
            assert 0 <= info.file_size < 4_000_000
        assert sum(i.file_size for i in infos) < 16_000_000 and archive.testzip() is None
        entries = strict_json(archive.read("MANIFEST.json"))["files"]
        assert len(entries) == len({e["path"] for e in entries}) == 408
        assert {e["path"] for e in entries} == set(archive.namelist()) - {"MANIFEST.json"}
        for entry in entries:
            raw = archive.read(entry["path"])
            assert len(raw) == entry["byte_length"] and sha256(raw).hexdigest() == entry["sha256"]
        for row in scope["included"]["complete_positives"]:
            original = row["original_golden"]
            closed(
                original,
                {"expected_envelope", "raw_body_sha256", "archive_expected_record", "artifacts"},
            )
            expected_pin = original["archive_expected_record"]
            raw_expected = archive.read(expected_pin["member"])
            assert len(raw_expected) == expected_pin["byte_length"]
            assert sha256(raw_expected).hexdigest() == expected_pin["sha256"]
            expected = strict_json(raw_expected)
            assert original["expected_envelope"] == expected["expected_envelope_fields"]
            parts = {}
            assert len(original["artifacts"]) == 3
            for artifact in original["artifacts"]:
                raw = repo_bytes(artifact["pin"]["path"])
                check_pin(artifact["pin"], raw, baseline=True)
                assert raw == archive.read(artifact["archive_member"])
                parts[artifact["name"]] = raw
            assert set(parts) == {"raw_body.bin", "canonical_payload.bin", "frame.bin"}
            payload, frame = parts["canonical_payload.bin"], parts["frame.bin"]
            body = strict_json(payload)
            assert body == {
                "body_byte_length": {"type": "uint64", "value": str(len(parts["raw_body.bin"]))},
                "body_sha256": sha256(parts["raw_body.bin"]).hexdigest(),
                "canonical_profile_version": "typed-json-candidate-v0.1",
            }
            envelope = original["expected_envelope"]
            assert envelope == {
                "domain_tag": "PITLAB/ACADEMIC/SOURCE-BYTES/candidate-v0.1",
                "object_schema_version": "source-bytes-candidate-v0.1",
                "canonical_profile_version": "typed-json-candidate-v0.1",
                "digest_algorithm": "SHA-256",
                "canonical_payload_byte_length": {"type": "uint64", "value": "187"},
                "digest_hex": sha256(frame).hexdigest(),
            }
            segments = (
                envelope["domain_tag"].encode("ascii"),
                envelope["object_schema_version"].encode("ascii"),
                payload,
            )
            assert frame == b"".join(len(p).to_bytes(8, "big") + p for p in segments)
            assert len(payload) == 187 and len(frame) == 281
            assert (
                original["raw_body_sha256"]
                == body["body_sha256"]
                == expected["expected_raw_sha256"]
            )
            assert (
                payload.hex() == expected["exact_scalar_or_payload_bytes_hex"]["canonical_payload"]
            )
            assert frame.hex() == expected["exact_frame_bytes_hex"]
            old_row = next(r for r in old["golden_positives"] if r["vector_id"] == row["case_id"])
            assert (
                envelope["digest_hex"]
                == old_row["expected_frame_digest_sha256"]
                == expected["expected_frame_sha256"]
            )


@pytest.mark.parametrize(
    "mutation", ["expected", "missing", "identity", "blocked_promotion", "depth_promotion"]
)
def test_rejects_in_memory_ledger_tampering(scope, ledger, mutation):
    changed = copy.deepcopy(ledger)
    if mutation == "expected":
        next(c for c in changed["cases"] if c["case_id"] == "N-OWN-ENVELOPE")["expected"][
            "code"
        ] = "CLOSED_FIELDS"
    elif mutation == "missing":
        changed["cases"].pop()
    elif mutation == "identity":
        changed["cases"][0]["case_id"] = "B99"
    else:
        cid = "BLO-01" if mutation == "blocked_promotion" else "P2-DEPTH-65"
        next(c for c in changed["cases"] if c["case_id"] == cid)["status"] = (
            "VALID_COMPLETE_DOMAIN_POSITIVE"
        )
    with pytest.raises(ValueError):
        check_scope(scope, changed)


@pytest.mark.parametrize("mutation", ["missing", "sha256", "blob"])
def test_rejects_in_memory_source_pin_tampering(scope, mutation):
    pins = strict_json(repo_bytes(AUTHOR + "source_pins.json"))
    if mutation == "missing":
        pins["files"].pop()
    else:
        pins["files"][0]["sha256" if mutation == "sha256" else "git_blob_sha1"] = "0" * (
            64 if mutation == "sha256" else 40
        )
    with pytest.raises(ValueError, match="source pin table changed"):
        check_sources(scope, pins)


@pytest.mark.parametrize("mutation", ["expected", "inclusion", "pin"])
def test_stored_manifest_expectations_have_an_external_literal_anchor(scope, mutation):
    changed = copy.deepcopy(scope)
    if mutation == "expected":
        changed["included"]["narrow_refusals"][0]["record"]["expected"]["code"] = "ACCEPT"
    elif mutation == "inclusion":
        changed["included"]["narrow_refusals"].pop()
    else:
        changed["baseline_sources"][0]["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="manifest bytes changed"):
        manifest_from_bytes((json.dumps(changed, ensure_ascii=False, indent=2) + "\n").encode())


def test_metadata_hashing_is_order_explicit_and_not_unicode_normalizing():
    assert metadata_hash({"b": "x", "a": "y"}) == metadata_hash({"a": "y", "b": "x"})
    assert metadata_hash(["a", "b"]) != metadata_hash(["b", "a"])
    assert metadata_hash("é") != metadata_hash("e\u0301")
    with pytest.raises(ValueError):
        strict_json(b'{"a":"x","a":"y"}')


def test_original_byte_mutations_are_rejected_in_memory(scope):
    pin = scope["included"]["complete_positives"][0]["original_golden"]["artifacts"][0]["pin"]
    with pytest.raises(ValueError, match="source bytes changed"):
        check_pin(pin, repo_bytes(pin["path"]) + b"tampered", baseline=True)
