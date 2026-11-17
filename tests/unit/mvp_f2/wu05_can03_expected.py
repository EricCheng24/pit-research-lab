"""Test-only literal SOURCE audit. Stdlib only; no production/author imports.

This is deliberately not a general codec. Frozen bytes control all expectations.
Metadata hashing is ordinary JSON, never a canonical identity operation.
"""

import json
import stat
from functools import lru_cache
from hashlib import sha256
from pathlib import Path, PurePosixPath
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[3]
FIX = ROOT / "tests/fixtures/mvp_if03"
OLD = FIX / "oracle01_v0_1"
AUTHOR = FIX / "wu05_oracle01_v0_1"
FREEZE_PATH = FIX / "wu05_oracle02_scoped_freeze_v0_1/FREEZE_MANIFEST.json"
FREEZE_HASH = "9099a4faede3c893ec57dc936d33741b1c6a1ac5b8b6f612d56219808d4a73b1"
LEDGER_HASH = "c437c9f30cb7588f8d2e8703c6d37a5a81443077a3336abf24a9c87b4a634b1d"
PROFILE = "typed-json-candidate-v0.1"
DOMAIN = b"PITLAB/ACADEMIC/SOURCE-BYTES/candidate-v0.1"
SCHEMA = b"source-bytes-candidate-v0.1"


def metadata_hash(value):
    return sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        ).encode("utf-8")
    ).hexdigest()


def freeze():
    raw = FREEZE_PATH.read_bytes()
    assert sha256(raw).hexdigest() == FREEZE_HASH
    return json.loads(raw)


def ledger():
    raw = (AUTHOR / "cases.json").read_bytes()
    assert sha256(raw).hexdigest() == LEDGER_HASH
    return {c["case_id"]: c for c in json.loads(raw)["cases"]}


def literal_source(raw):
    """Hand concatenation of three fixed keys, ASCII decimal length and raw hash.

    No generic serializer, production encoder, author predicate or issuer is used.
    Supports only the declared opaque SOURCE-BYTES preimage.
    """
    payload = (
        b'{"body_byte_length":{"type":"uint64","value":"'
        + str(len(raw)).encode("ascii")
        + b'"},"body_sha256":"'
        + sha256(raw).hexdigest().encode("ascii")
        + b'","canonical_profile_version":"typed-json-candidate-v0.1"}'
    )
    frame = b"".join(len(p).to_bytes(8, "big") + p for p in (DOMAIN, SCHEMA, payload))
    return payload, frame, sha256(frame).digest()


@lru_cache(maxsize=1)
def archived_vectors():
    """Check safe archive metadata and literal pins, read only eight vector members.

    No extraction and no reading of historical author scripts/reports in the ZIP.
    """
    manifest = freeze()
    pin = manifest["limited_golden"]["archive"]
    archive_path = ROOT / pin["path"]
    raw = archive_path.read_bytes()
    assert len(raw) == pin["byte_length"] and sha256(raw).hexdigest() == pin["sha256"]
    vectors = {}
    with ZipFile(archive_path) as archive:
        infos = archive.infolist()
        assert len(infos) == len({i.filename for i in infos}) == 409
        assert sum(i.file_size for i in infos) < 16_000_000
        for info in infos:
            path = PurePosixPath(info.filename)
            assert not path.is_absolute() and ".." not in path.parts
            assert "\\" not in info.filename and ":" not in info.filename
            assert not info.is_dir() and stat.S_IFMT(info.external_attr >> 16) != stat.S_IFLNK
            assert 0 <= info.file_size < 4_000_000
        for row in manifest["included"]["complete_positives"]:
            cid, original = row["case_id"], row["original_golden"]
            expected_pin = original["archive_expected_record"]
            expected_raw = archive.read(expected_pin["member"])
            assert len(expected_raw) == expected_pin["byte_length"]
            assert sha256(expected_raw).hexdigest() == expected_pin["sha256"]
            expected = json.loads(expected_raw)
            artifacts = {}
            for artifact in original["artifacts"]:
                p = artifact["pin"]
                body = (ROOT / p["path"]).read_bytes()
                assert body == archive.read(artifact["archive_member"])
                assert len(body) == p["byte_length"] and sha256(body).hexdigest() == p["sha256"]
                artifacts[artifact["name"]] = body
            raw, payload, frame = (
                artifacts[n] for n in ("raw_body.bin", "canonical_payload.bin", "frame.bin")
            )
            derived_payload, derived_frame, digest = literal_source(raw)
            assert raw == bytes.fromhex(expected["exact_input_bytes_hex"]["raw_body"])
            assert (
                payload
                == derived_payload
                == bytes.fromhex(expected["exact_scalar_or_payload_bytes_hex"]["canonical_payload"])
            )
            assert frame == derived_frame == bytes.fromhex(expected["exact_frame_bytes_hex"])
            assert digest == bytes.fromhex(expected["expected_frame_sha256"])
            assert sha256(raw).hexdigest() == original["raw_body_sha256"]
            envelope = expected["expected_envelope_fields"]
            assert envelope == original["expected_envelope"]
            assert set(envelope) == {
                "domain_tag",
                "object_schema_version",
                "canonical_profile_version",
                "digest_algorithm",
                "canonical_payload_byte_length",
                "digest_hex",
            }
            assert envelope == {
                "domain_tag": DOMAIN.decode("ascii"),
                "object_schema_version": SCHEMA.decode("ascii"),
                "canonical_profile_version": PROFILE,
                "digest_algorithm": "SHA-256",
                "canonical_payload_byte_length": {"type": "uint64", "value": str(len(payload))},
                "digest_hex": digest.hex(),
            }
            vectors[cid] = (raw, payload, frame, envelope)
    return vectors


def stored(cid="B01"):
    # Detached envelope; controls must never mutate the cached frozen expectation.
    raw, payload, frame, envelope = archived_vectors()[cid]
    return raw, payload, frame, json.loads(json.dumps(envelope))
