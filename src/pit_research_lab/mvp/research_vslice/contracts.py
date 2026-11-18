"""Closed, detached research values. No domain/IF03 resource semantics."""

import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

CUTOFFS = (
    "2027-01-07T18:00:00+08:00",
    "2027-01-15T18:00:00+08:00",
    "2027-01-29T18:00:00+08:00",
    "2027-02-05T18:00:00+08:00",
)
ACTIONS = ("HOLD", "FLAG_REVIEW", "ABSTAIN")
AGENTS = ("no_data_baseline_v1", "eligible_rule_v1")
SOURCE_KEYS = (
    "foundation_a_december",
    "foundation_b_december",
    "october",
    "november",
    "december",
    "correction_1",
    "correction_2",
    "provider",
)
POLICY_STATES = (
    ("restricted_fields", "WITHHELD"),
    ("evaluation", "NOT_EVALUATED"),
    ("unprovided_feature", "ABSENT"),
)
STATES = ("KNOWN", "UNKNOWN", "WITHHELD", "NOT_EVALUATED", "ABSENT")


class ResearchError(ValueError):
    """Closed research refusal code; caller text/private bodies are never echoed."""


def require(condition: bool, code: str) -> None:
    if not condition:
        raise ResearchError(code)


def instant(text: str) -> datetime:
    require(
        type(text) is str
        and re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+08:00", text) is not None,
        "INVALID_ORIGINAL_TIMESTAMP",
    )
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        raise ResearchError("INVALID_ORIGINAL_TIMESTAMP") from None


def research_bytes(value: object) -> bytes:
    """Stable research JSON, not IF03 Canonical JSON. Reject all floats/objects."""

    def check(v: object) -> None:
        if v is None or type(v) in (str, int, bool):
            return
        if type(v) is list:
            for item in v:
                check(item)
            return
        if type(v) is dict:
            for key, item in v.items():
                require(type(key) is str, "RESEARCH_JSON_KEY")
                check(item)
            return
        raise ResearchError("RESEARCH_JSON_VALUE")

    check(value)
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        require(key not in result, "DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def _nonexact(_: str) -> Any:
    raise ResearchError("NONEXACT_JSON_NUMBER")


def decode(body: bytes) -> Any:
    try:
        return json.loads(
            body, object_pairs_hook=_pairs, parse_float=_nonexact, parse_constant=_nonexact
        )
    except (UnicodeError, json.JSONDecodeError):
        raise ResearchError("INVALID_SOURCE_JSON") from None


@dataclass(frozen=True, slots=True)
class Provenance:
    source: str
    version: str
    record: str
    publication: str
    fixture: str
    value_pointer: str
    publication_pointer: str
    content_sha256: str
    evidence_class: str = "AUTHORED_SYNTHETIC_DECLARATION"

    def __post_init__(self) -> None:
        instant(self.publication)
        require(
            all(
                type(getattr(self, f)) is str and bool(getattr(self, f))
                for f in (
                    "source",
                    "version",
                    "record",
                    "fixture",
                    "value_pointer",
                    "publication_pointer",
                )
            ),
            "INVALID_PROVENANCE",
        )
        require(
            re.fullmatch("[0-9a-f]{64}", self.content_sha256) is not None, "INVALID_CONTENT_DIGEST"
        )
        require(self.evidence_class == "AUTHORED_SYNTHETIC_DECLARATION", "EVIDENCE_CLASS")


@dataclass(frozen=True, slots=True)
class InputEvent:
    """Trusted-loader snapshot; NOT supplied to adapters or included in repr of env."""

    key: str
    provenance: Provenance
    state: str
    value: int | None
    unit: str
    subject: str
    field: str
    predecessor: str | None = None

    def __post_init__(self) -> None:
        require(self.key in SOURCE_KEYS and type(self.provenance) is Provenance, "EVENT_KEY")
        require(self.state in ("KNOWN", "UNKNOWN", "WITHHELD", "NOT_EVALUATED"), "EVENT_STATE")
        require(
            (type(self.value) is int) if self.state == "KNOWN" else self.value is None,
            "STATE_VALUE_CONTAMINATION",
        )
        require(self.unit in ("NTD_thousands", "relation_declaration", "NONE"), "EVENT_UNIT")
        require(
            type(self.subject) is str
            and bool(self.subject)
            and type(self.field) is str
            and bool(self.field),
            "EVENT_SUBJECT_FIELD",
        )
        require(self.predecessor is None or type(self.predecessor) is str, "REVISION_LINK")


@dataclass(frozen=True, slots=True)
class Feature:
    key: str
    state: str
    value: int | None
    unit: str
    provenance: Provenance | None

    def __post_init__(self) -> None:
        require(self.key in (*SOURCE_KEYS, *(k for k, _ in POLICY_STATES)), "FEATURE_KEY")
        require(self.state in STATES, "FEATURE_STATE")
        require(
            (type(self.value) is int) if self.state == "KNOWN" else self.value is None,
            "STATE_VALUE_CONTAMINATION",
        )
        require(
            self.provenance is None or type(self.provenance) is Provenance, "FEATURE_PROVENANCE"
        )
        require(self.unit in ("NTD_thousands", "relation_declaration", "NONE"), "FEATURE_UNIT")
        if self.key in dict(POLICY_STATES):
            require(
                self.state == dict(POLICY_STATES)[self.key]
                and self.provenance is None
                and self.unit == "NONE",
                "POLICY_STATE_CONTAMINATION",
            )
        elif self.state == "ABSENT":
            require(self.provenance is None and self.unit == "NONE", "ABSENT_CONTAMINATION")
        else:
            require(self.provenance is not None, "MISSING_FEATURE_PROVENANCE")


@dataclass(frozen=True, slots=True)
class ResearchObservation:
    tick_order: int
    cutoff: str
    features: tuple[Feature, ...]
    schema: str = "RESEARCH_OBSERVATION_V0.1"

    def __post_init__(self) -> None:
        require(type(self.tick_order) is int and 0 <= self.tick_order < 4, "TICK_ORDER")
        require(self.cutoff == CUTOFFS[self.tick_order], "CUTOFF_NOT_IN_PROFILE")
        require(self.schema == "RESEARCH_OBSERVATION_V0.1", "OBSERVATION_SCHEMA")
        require(
            type(self.features) is tuple and all(type(f) is Feature for f in self.features),
            "IMMUTABLE_FEATURES_REQUIRED",
        )
        require(
            tuple(f.key for f in self.features) == (*SOURCE_KEYS, *(k for k, _ in POLICY_STATES)),
            "FEATURE_SET_CONTAMINATION",
        )
        require(
            all(
                f.provenance is None or instant(f.provenance.publication) < instant(self.cutoff)
                for f in self.features
            ),
            "FUTURE_FEATURE_REFUSED",
        )

    @property
    def availability_mask(self) -> tuple[tuple[str, str], ...]:
        return tuple((f.key, f.state) for f in self.features)
