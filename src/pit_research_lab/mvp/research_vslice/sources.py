"""Only trusted fixture boundary. Full packs and legacy Native graphs stay here."""

import stat
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

from .contracts import CUTOFFS, InputEvent, Provenance, decode, instant, require, research_bytes

BASELINE = "4d3e56291dc5831be3dd85c00106a91055d3d3d1"
SOURCE_PINS = (
    (
        "tests/unit/mvp_f2/data/temporal_foundation_v0.1.json",
        "3b81aae8e3242468c3076911861a13b6f1646f42d068be67b316af9caef1c373",
        72800,
    ),
    (
        "tests/unit/mvp_f2/data/derived_observations_v0.1.json",
        "b9e1babbcc86b0e70ed5589972259fcbe6b666a38d2e7eff77d108f448e4dc0e",
        5440756,
    ),
)


def checkout_root() -> Path:
    path = Path(__file__).absolute()
    require(
        path.parts[-5:] == ("src", "pit_research_lab", "mvp", "research_vslice", "sources.py"),
        "CHECKOUT_LAYOUT",
    )
    return path.parents[4]


def regular_bytes(path: Path) -> bytes:
    for p in (*reversed(path.parents), path):
        require(not p.is_symlink(), "SYMLINK_REFUSED")
    info = path.stat()
    require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, "REGULAR_UNLINKED_FILE_REQUIRED")
    return path.read_bytes()


def verify_pin(body: bytes, pin: tuple[str, str, int]) -> None:
    require(
        type(body) is bytes and len(body) == pin[2] and sha256(body).hexdigest() == pin[1],
        "FIXTURE_PIN_MISMATCH",
    )


@dataclass(frozen=True, slots=True)
class EventLedger:
    """Loader/internal research history; never an adapter observation."""

    events: tuple[InputEvent, ...]

    def __post_init__(self) -> None:
        require(
            type(self.events) is tuple
            and bool(self.events)
            and all(type(e) is InputEvent for e in self.events),
            "IMMUTABLE_LEDGER_REQUIRED",
        )
        identities = [(e.key, e.provenance.version) for e in self.events]
        require(len(set(identities)) == len(identities), "DUPLICATE_SOURCE_HISTORY")
        priority = [(e.key, e.provenance.publication) for e in self.events]
        require(len(set(priority)) == len(priority), "CONFLICTING_SAME_PRIORITY_HISTORY")
        for e in self.events:
            visited = {e.provenance.version}
            current = e
            while current.predecessor is not None:
                parents = [
                    p
                    for p in self.events
                    if p.key == e.key and p.provenance.version == current.predecessor
                ]
                require(len(parents) == 1, "MISSING_REVISION_PARENT")
                parent = parents[0]
                require(parent.provenance.version not in visited, "REVISION_CYCLE")
                require(
                    parent.provenance.source == e.provenance.source
                    and parent.subject == e.subject
                    and parent.field == e.field
                    and parent.unit == e.unit
                    and instant(parent.provenance.publication)
                    < instant(current.provenance.publication),
                    "REVISION_ORDER",
                )
                visited.add(parent.provenance.version)
                current = parent
        for key in sorted({e.key for e in self.events}):
            group = [e for e in self.events if e.key == key]
            require(sum(e.predecessor is None for e in group) == 1, "AMBIGUOUS_HISTORY_ROOT")
            parent_versions = [e.predecessor for e in group if e.predecessor is not None]
            require(len(set(parent_versions)) == len(parent_versions), "BRANCHED_REVISION_HISTORY")


def _timestamp(value: dict[str, Any]) -> str:
    require(
        value["timezone_name"] == "Asia/Taipei"
        and value["offset"] == "+08:00"
        and value["precision"] == "SECOND",
        "ORIGINAL_TIME_DECLARATION",
    )
    result = value["source_text"]
    require(type(result) is str, "INVALID_ORIGINAL_TIMESTAMP")
    instant(result)
    return str(result)


def _extract_foundation(pack: dict[str, Any]) -> list[InputEvent]:
    spec = pack["input_spec"]
    require(
        spec["pack_id"] == "SYN-WU01-FOUNDATION"
        and spec["pack_version"] == "v0.1"
        and spec["provenance"]["kind"] == "SYNTHETIC_AUTHORED",
        "FOUNDATION_IDENTITY",
    )
    # Validate the bounded calendar directly; no generated pack or diagnostic API.
    weeks = (
        ("2027-01-04", "2027-01-10"),
        ("2027-01-11", "2027-01-17"),
        ("2027-01-18", "2027-01-24"),
        ("2027-01-25", "2027-01-31"),
        ("2027-02-01", "2027-02-07"),
    )
    cutoffs = []
    no_sessions = []
    for start, end in weeks:
        sessions = [
            r["date"]
            for r in spec["calendar"]
            if start <= r["date"] <= end and r["status"] == "SESSION"
        ]
        if sessions:
            cutoffs.append(max(sessions) + "T18:00:00+08:00")
        else:
            no_sessions.append(start)
    require(tuple(cutoffs) == CUTOFFS and no_sessions == ["2027-01-18"], "FIXED_FOUR_CALENDAR")
    events = []
    for i, row in enumerate(spec["revenue_events"]):
        require(
            row["publication"]["state"] == "KNOWN" and row["publication"]["proof_kind"] == "EXACT",
            "UNSUPPORTED_PUBLICATION",
        )
        stamp = _timestamp(row["publication"]["instant"])
        require(
            row["issuer_ref"] in ("SYN-A", "SYN-B")
            and row["reference_month"] == "2026-12"
            and row["unit"] == "NTD_thousands",
            "FOUNDATION_SUBJECT",
        )
        p = f"/input_spec/revenue_events/{i}"
        prov = Provenance(
            row["source_ref"],
            row["version_ref"],
            row["event_ref"],
            stamp,
            SOURCE_PINS[0][0],
            p + "/amount",
            p + "/publication/instant/source_text",
            sha256(research_bytes(row)).hexdigest(),
        )
        events.append(
            InputEvent(
                "foundation_a_december"
                if row["issuer_ref"] == "SYN-A"
                else "foundation_b_december",
                prov,
                row["state"],
                row.get("amount"),
                row["unit"],
                row["issuer_ref"] + ":" + row["reference_month"],
                "amount",
                row["supersedes_ref"],
            )
        )
    return events


def _extract_notices(pack: dict[str, Any]) -> list[InputEvent]:
    result = []
    predecessors: dict[str, str] = {}
    notices = []
    for i, source in enumerate(pack["sources"]):
        raw = source["raw"]["utf8"].encode("utf-8")
        require(
            len(raw) == source["raw"]["byte_length"]
            and sha256(raw).hexdigest() == source["raw"]["sha256"],
            "RAW_NOTICE_PIN",
        )
        notice = decode(raw)
        request = source["source"]["request"]
        supplied = request["attempts"][0]["supplied"]
        proof = supplied["proof_candidate"]
        statement = notice["statements"][0]
        stamp = _timestamp(proof["timestamp"])
        descriptor = dict(proof["raw_descriptor"])
        require(
            len(descriptor) == len(proof["raw_descriptor"])
            and descriptor["timestamp"] == stamp
            and descriptor["proof_kind"] == "exact"
            and proof["proof_kind"] == "exact"
            and descriptor["target_id"] == proof["target_ref"] == statement["assertion_id"]
            and descriptor["content_version_id"]
            == proof["content_version_ref"]
            == notice["content_version_id"]
            == supplied["event"]["content_version_ref"]
            and descriptor["fragment_selector"] == proof["fragment_selector"] == "/statements/0"
            and supplied["event"]["event_kind"] == "issuer_publication"
            and notice["issuer_id"] == "SYN-A"
            and notice["schema"] == "synthetic-notice-v1",
            "NOTICE_PUBLICATION_LINK",
        )
        require(
            proof["timestamp"]["origin"]["input_digest"]["value"] == source["raw"]["sha256"],
            "NOTICE_ORIGIN_DIGEST",
        )
        require(
            request["content"]["raw_bytes"]["bytes_hex"] == raw.hex()
            and request["assertion"]["source_amount"]["value"] == statement["value"],
            "NOTICE_FRAGMENT_LINK",
        )
        metric = statement["metric"]
        relation = None
        if metric.startswith("B02_DIRECT_RELATION:"):
            # Original metric contains an actual JSON array, not a computed Native outcome.
            relation = decode(metric.split(":", 1)[1].encode())
            require(
                relation[1] == "CORRECTS"
                and relation[7] == statement["assertion_id"]
                and relation[9] == ["FIELD", [relation[2]], relation[4], relation[6]],
                "UNSUPPORTED_RELATION",
            )
            require(relation[6] not in predecessors, "DUPLICATE_REVISION_NOTICE")
            predecessors[relation[6]] = relation[4]
        else:
            require(metric == "net_operating_revenue", "UNSUPPORTED_NOTICE_FIELD")
        notices.append((i, notice, statement, stamp, request, relation))
    monthly = {n["content_version_id"]: (s, t) for _, n, s, t, _, rel in notices if rel is None}
    for i, notice, statement, stamp, request, relation in notices:
        if relation is not None:
            require(relation[4] in monthly and relation[6] in monthly, "MISSING_RELATION_ENDPOINT")
            before, after = monthly[relation[4]], monthly[relation[6]]
            require(
                before[0]["assertion_id"] == relation[3]
                and after[0]["assertion_id"] == relation[5]
                and before[0]["subject_id"] == after[0]["subject_id"] == relation[2]
                and after[1] == stamp,
                "RELATION_ENDPOINT_OR_TIME",
            )
            # Two bounded, original relation subjects; opaque relation payload is not public.
            key = {"PREP01-SUB-N12": "correction_1", "PREP01-SUB-N23": "correction_2"}[
                statement["subject_id"]
            ]
        else:
            key = {
                "PREP01-SUB-2026-10": "october",
                "PREP01-SUB-2026-11": "november",
                "PREP01-SUB-2026-12": "december",
            }[statement["subject_id"]]
        p = f"/sources/{i}"
        prov = Provenance(
            request["content"]["source_ref"]["value"],
            notice["content_version_id"],
            statement["assertion_id"],
            stamp,
            SOURCE_PINS[1][0],
            p + "/raw/utf8#/statements/0/value",
            p + "/source/request/attempts/0/supplied/proof_candidate/timestamp/source_text",
            pack["sources"][i]["raw"]["sha256"],
        )
        result.append(
            InputEvent(
                key,
                prov,
                "KNOWN",
                statement["value"],
                statement["unit"],
                statement["subject_id"],
                "value",
                predecessors.get(notice["content_version_id"]),
            )
        )
        if key == "october":
            provider = request["content"]["provider_ref"]
            require(
                provider["type"] == "Unknown" and provider["source_text"] is None,
                "PROVIDER_NOT_EXPLICIT_UNKNOWN",
            )
            pp = Provenance(
                prov.source,
                prov.version,
                prov.record,
                prov.publication,
                prov.fixture,
                p + "/source/request/content/provider_ref/type",
                prov.publication_pointer,
                prov.content_sha256,
            )
            result.append(
                InputEvent(
                    "provider", pp, "UNKNOWN", None, "NONE", notice["issuer_id"], "provider_ref"
                )
            )
    return result


def load_pinned_synthetic_events() -> EventLedger:
    """Read only the two fixed original files. No caller-supplied replacement pin."""
    bodies = tuple(regular_bytes(checkout_root() / p) for p, _, _ in SOURCE_PINS)
    for body, pin in zip(bodies, SOURCE_PINS, strict=True):
        verify_pin(body, pin)
    events = _extract_foundation(decode(bodies[0])) + _extract_notices(decode(bodies[1]))
    return EventLedger(tuple(events))
