"""Author's bounded, TEST-ONLY reconstruction and contract predicates.

No production imports, resource issuer, Native invocation or admission decision.
Only SOURCE-BYTES has a complete preimage derivation here. Fragment/graph checks
are necessary conditions, never full-domain validation. ORACLE-02 must rederive
expectations separately; this module is not a second independent implementation.
Do not import or copy this module into WU05-CAN.
"""

import json
import re
import struct
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import PurePosixPath
from zipfile import ZipFile

PROFILE = "typed-json-candidate-v0.1"
DOMAIN = b"PITLAB/ACADEMIC/SOURCE-BYTES/candidate-v0.1"
SCHEMA = b"source-bytes-candidate-v0.1"
CUTOFFS = (
    "2027-01-07T18:00:00+08:00",
    "2027-01-15T18:00:00+08:00",
    "2027-01-29T18:00:00+08:00",
    "2027-02-05T18:00:00+08:00",
)


class Refusal(ValueError):
    def __init__(self, code, category="STRUCTURALLY_INVALID"):
        self.code = code
        self.category = category
        super().__init__(code)


def need(condition, code, category="STRUCTURALLY_INVALID"):
    if not condition:
        raise Refusal(code, category)


def source_bytes(raw):
    """Three fixed fields, explicitly ordered; no RS or general encoder used."""
    payload = (
        b'{"body_byte_length":{"type":"uint64","value":"'
        + str(len(raw)).encode("ascii")
        + b'"},"body_sha256":"'
        + sha256(raw).hexdigest().encode("ascii")
        + b'","canonical_profile_version":"typed-json-candidate-v0.1"}'
    )
    frame = b"".join(struct.pack(">Q", len(part)) + part for part in (DOMAIN, SCHEMA, payload))
    return payload, frame


def checked_archive(path, pin):
    """Read data in memory only, after pin/path/size/CRC/manifest checks."""
    raw = path.read_bytes()
    need(len(raw) == pin["byte_length"] and sha256(raw).hexdigest() == pin["sha256"], "ZIP_PIN")
    with ZipFile(path) as archive:
        infos = archive.infolist()
        need(len(infos) == pin["zip_members"], "ZIP_COUNT")
        need(len({i.filename for i in infos}) == len(infos), "ZIP_DUPLICATE")
        for info in infos:
            p = PurePosixPath(info.filename)
            need(
                not p.is_absolute()
                and ".." not in p.parts
                and "\\" not in info.filename
                and ":" not in info.filename
                and not info.is_dir()
                and (info.external_attr >> 16) & 0o170000 != 0o120000,
                "ZIP_PATH",
            )
            need(0 <= info.file_size <= 4_000_000, "ZIP_SIZE")
        need(sum(i.file_size for i in infos) <= 16_000_000, "ZIP_TOTAL_SIZE")
        need(archive.testzip() is None, "ZIP_CRC")
        manifest = json.loads(archive.read("MANIFEST.json"))
        entries = manifest["files"]
        names = {e["path"] for e in entries}
        need(len(entries) == len(names) == pin["manifest_accounted_entries"], "ZIP_MANIFEST_COUNT")
        need(names == {i.filename for i in infos} - {"MANIFEST.json"}, "ZIP_MANIFEST_PATHS")
        for entry in entries:
            body = archive.read(entry["path"])
            need(
                len(body) == entry["byte_length"] and sha256(body).hexdigest() == entry["sha256"],
                "ZIP_MANIFEST_PIN",
            )
        # No extraction, execution, import, or interpretation of archived Python.
        return {
            name: archive.read(name)
            for name in names
            if name == "oracle_scope_register.json"
            or re.fullmatch(
                r"vectors/B0[1-8]/(raw_body.bin|canonical_payload.bin|frame.bin|expected.json)",
                name,
            )
        }


def integer(value, signed=False):
    need(type(value) is dict and set(value) == {"type", "value"}, "INTEGER_FIELDS")
    need(value["type"] == ("int64" if signed else "uint64"), "INTEGER_TAG")
    spelling = value["value"]
    need(type(spelling) is str, "INTEGER_TEXT")
    need(
        re.fullmatch(r"0|-?[1-9][0-9]*" if signed else r"0|[1-9][0-9]*", spelling) is not None,
        "INTEGER_SPELLING",
    )
    need(len(spelling) <= 20, "INTEGER_RANGE")
    number = int(spelling)
    need(-(2**63) <= number < 2**63 if signed else 0 <= number < 2**64, "INTEGER_RANGE")
    return number


def canonical_fragment(raw):
    """Canonical-byte predicate for scalar/record fragments, not domain issuance.

    Rendering is private to this predicate. It cannot establish complete schema,
    Resource semantics, timezone rules, provenance, authorization or domain identity.
    Depth is an implementation budget only; no normative root-depth claim.
    """
    need(not raw.startswith(b"\xef\xbb\xbf"), "BOM")

    def pairs(entries):
        result = {}
        for key, value in entries:
            need(key not in result, "DUPLICATE_KEY")
            need(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key) is not None, "KEY")
            result[key] = value
        return result

    def numeric(_):
        raise Refusal("BARE_NUMBER")

    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=pairs,
            parse_int=numeric,
            parse_float=numeric,
            parse_constant=numeric,
        )
    except Refusal:
        raise
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise Refusal("INVALID_JSON_UTF8") from exc

    def render(v, depth=0):
        need(depth < 100, "TEST_BUDGET")
        if type(v) is str:
            try:
                need(len(v.encode("utf-8")) <= 65536, "TEXT_BOUND")
            except UnicodeError as exc:
                raise Refusal("SURROGATE") from exc
            return (
                '"'
                + "".join(
                    '\\"'
                    if c == '"'
                    else "\\\\"
                    if c == "\\"
                    else f"\\u{ord(c):04x}"
                    if ord(c) < 32
                    else c
                    for c in v
                )
                + '"'
            )
        if type(v) is bool:
            return "true" if v else "false"
        if type(v) is list:
            need(len(v) <= 4096, "ARRAY_BOUND")
            return "[" + ",".join(render(c, depth + 1) for c in v) + "]"
        if type(v) is dict:
            return (
                "{"
                + ",".join(render(k, depth + 1) + ":" + render(v[k], depth + 1) for k in sorted(v))
                + "}"
            )
        raise Refusal("NULL_OR_UNTAGGED")

    need(render(value).encode("utf-8") == raw, "NONCANONICAL_BYTES")
    return value


def source_payload(raw):
    value = canonical_fragment(raw)
    # SOURCE-BYTES has no parent fields: these top-level claims are its OWN
    # digest/reference, forbidden by CAN-05 / AD01-08 before generic extra keys.
    # Do not scan all nested digest_hex fields: typed parent cores may contain them
    # in other domains, whose validation is outside this bounded predicate.
    if type(value) is dict:
        need(not {"digest_hex", "reference"}.intersection(value), "REF_CYCLE")
    need(
        type(value) is dict
        and set(value) == {"body_byte_length", "body_sha256", "canonical_profile_version"},
        "CLOSED_FIELDS",
    )
    need(value["canonical_profile_version"] == PROFILE, "PROFILE", "UNSUPPORTED_SCHEMA")
    integer(value["body_byte_length"])
    need(
        type(value["body_sha256"]) is str
        and re.fullmatch("[0-9a-f]{64}", value["body_sha256"]) is not None,
        "HEX64",
    )
    return value


def source_frame(frame, envelope):
    """Validate a claimed SOURCE-BYTES frame/envelope; never issues a reference."""
    parts, cursor = [], 0
    for index in range(3):
        need(cursor + 8 <= len(frame), "FRAME_PREFIX")
        length = int.from_bytes(frame[cursor : cursor + 8], "big")
        bound = 128 if index < 2 else 16777216
        need(1 <= length <= bound, "FRAME_LENGTH")
        cursor += 8
        need(cursor + length <= len(frame), "FRAME_TRUNCATED")
        parts.append(frame[cursor : cursor + length])
        cursor += length
    need(cursor == len(frame), "FRAME_TRAILING")
    need(parts[:2] == [DOMAIN, SCHEMA], "DOMAIN_SCHEMA", "UNSUPPORTED_SCHEMA")
    source_payload(parts[2])
    need(
        set(envelope)
        == {
            "domain_tag",
            "object_schema_version",
            "canonical_profile_version",
            "digest_algorithm",
            "canonical_payload_byte_length",
            "digest_hex",
        },
        "ENVELOPE_FIELDS",
    )
    need(
        (
            envelope["domain_tag"],
            envelope["object_schema_version"],
            envelope["canonical_profile_version"],
            envelope["digest_algorithm"],
        )
        == (DOMAIN.decode(), SCHEMA.decode(), PROFILE, "SHA-256"),
        "ENVELOPE_NEGOTIATION",
        "UNSUPPORTED_SCHEMA",
    )
    need(integer(envelope["canonical_payload_byte_length"]) == len(parts[2]), "PAYLOAD_LENGTH")
    need(
        type(envelope["digest_hex"]) is str
        and re.fullmatch("[0-9a-f]{64}", envelope["digest_hex"]) is not None,
        "DIGEST_FORMAT",
    )
    need(envelope["digest_hex"] == sha256(frame).hexdigest(), "DIGEST_MISMATCH")


def declared_time(text):
    need(
        type(text) is str
        and re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\+08:00", text)
        is not None,
        "TIME_FORMAT",
    )
    try:
        return datetime.fromisoformat(text).astimezone(UTC)
    except (ValueError, OverflowError) as exc:
        raise Refusal("TIME_FORMAT") from exc


def graph_condition(nodes, root):
    """Symbolic structural graph only; symbols are NOT issued typed parents."""
    visiting, visited = set(), set()

    def visit(key, deterministic):
        need(key not in visiting, "REF_CYCLE")
        need(key in nodes, "DANGLING_PARENT", "MISSING_REQUIRED_EVIDENCE")
        node = nodes[key]
        if deterministic:
            need(
                node["kind"] != "ATTEMPT"
                and not set(node.get("fields", []))
                & {"host", "clock", "attempt_id", "token", "audit_correspondence"},
                "ATTEMPT_ANCESTRY",
            )
        if (key, deterministic) in visited:
            return
        visiting.add(key)
        for parent in node["parents"]:
            visit(parent, deterministic)
        visiting.remove(key)
        visited.add((key, deterministic))

    visit(root, nodes[root]["kind"] in {"QUALIFICATION", "SEQUENCE", "EXPERIMENT", "RESULT"})


def schedule_path(value):
    """Compare full declared refs before missing-resource outcome (D06-A).

    Fixtures use hypothetical complete typed cores. Equality is structural only;
    no ref-to-body cryptographic or semantic verification is available.
    """
    need(value["original_input_refs"] == value["expected_original_input_refs"], "ORIGINAL_INPUTS")
    need(value["PF038"] == value["expected_input_ref"], "STALE_SCHEDULE_INPUT")
    need(value["invariant_policy_ref"] == value["AF009"], "AF009_POLICY_MISMATCH")
    need(
        value["sequence_schedule_ref"] == value["expected_schedule_ref"], "STALE_SEQUENCE_SCHEDULE"
    )
    return "NOT_SUPPLIED"
