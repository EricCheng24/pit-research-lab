"""Pinned, authored-public synthetic panel. No App admission, rights or IF03 IDs.

The existing S1/S2/S3 owners qualify synthetic-notice declarations. Their exact
publication witness is the modeled public delivery of that declaration; original
publication and accounting dates remain separate facts. Local seals only prevent
accidental/forged DTO substitution inside a cooperative process, not hostile Python.
"""

import calendar
import hmac
import json
import secrets
from dataclasses import asdict, dataclass, field, replace
from datetime import date, datetime, timedelta
from hashlib import sha256
from pathlib import Path
from typing import Any

from pit_research_lab.domain import contracts as d
from pit_research_lab.domain.asof_slice import AsOfRequest, evaluate_asof, observe_asof_code
from pit_research_lab.domain.pit_slice import CodeObservation, evaluate_slice
from pit_research_lab.domain.selection import (
    REQUIRED_CHECKS,
    BoundedCoverage,
    CandidateSource,
    CoverageCheck,
    DirectRelation,
    RelationSource,
    SelectionPolicy,
    relation_proposition,
)
from pit_research_lab.mvp.research_vslice.contracts import research_bytes

ROOT = Path(__file__).absolute().parents[4]
FIXTURE = "tests/fixtures/mvp_f3_l1/revenue_growth_panel_v0_1.json"
MANIFEST = "tests/fixtures/mvp_f3_l1/manifest_v0_1.json"
SOURCE_SHA256 = "8c2b03e3875e2029a3d9e0534588b76a5e470e944cea746fdd1fb7aba917927d"
MANIFEST_SHA256 = "7b0cb1bec7b4d42ea55670eeb9d8ee4b744e7c39368cadd7e0eb1298deeb3219"
SCHEMA = "F2_L1_AUTHORED_PANEL_V1"
_KEY = secrets.token_bytes(32)
_LOADER = object()
STATES = ("KNOWN", "UNKNOWN", "WITHHELD", "ABSENT", "NOT_EVALUATED", "REJECTED")


class PanelError(ValueError):
    """Safe closed reason; never echoes raw source/private graph."""


def require(condition: bool, code: str) -> None:
    if not condition:
        raise PanelError(code)


def instant(value: str) -> datetime:
    require(type(value) is str, "INVALID_TIME")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        raise PanelError("INVALID_TIME") from None
    require(
        parsed.isoformat(timespec="seconds") == value and value.endswith("+08:00"), "INVALID_TIME"
    )
    return parsed


def digest(value: object) -> str:
    return sha256(research_bytes(value)).hexdigest()


def _pairs(values: list[tuple[str, Any]]) -> dict[str, Any]:
    require(len({k for k, _ in values}) == len(values), "DUPLICATE_JSON_KEY")
    return dict(values)


def _bad_number(_: str) -> Any:
    raise PanelError("NONEXACT_NUMBER")


def decode(raw: bytes) -> Any:
    try:
        return json.loads(
            raw, object_pairs_hook=_pairs, parse_float=_bad_number, parse_constant=_bad_number
        )
    except (ValueError, UnicodeError) as exc:
        if isinstance(exc, PanelError):
            raise
        raise PanelError("INVALID_JSON") from None


def closed(value: object, keys: str) -> None:
    require(type(value) is dict and set(value) == set(keys.split()), "CLOSED_FIELDS")


@dataclass(frozen=True, slots=True)
class RevenueFact:
    month: str
    state: str
    amount: int | None
    source_ref: str | None
    publication: str | None
    available_at: str | None
    unit: str
    basis: str
    native_state: str
    reason: str
    qualification_ref: str | None
    version_ref: str | None = None


@dataclass(frozen=True, slots=True)
class PanelObservation:
    sample_id: str
    issuer: str
    tick: int
    cutoff: str
    dataset_digest: str
    calendar_id: str
    current: RevenueFact
    previous: RevenueFact
    binding_id: str
    _seal: bytes = field(repr=False, compare=False)

    def public(self) -> dict[str, Any]:
        value = asdict(self)
        del value["_seal"]
        return value


def verify_observation(value: object) -> PanelObservation:
    require(type(value) is PanelObservation, "DETACHED_OBSERVATION_REQUIRED")
    assert isinstance(value, PanelObservation)
    body = value.public()
    binding = body.pop("binding_id")
    require(binding == digest(body), "OBSERVATION_BINDING_MISMATCH")
    require(
        hmac.compare_digest(value._seal, hmac.digest(_KEY, research_bytes(body), "sha256")),
        "OBSERVATION_NOT_ISSUED",
    )
    for fact in (value.current, value.previous):
        require(fact.state in STATES, "INFORMATION_STATE")
        if fact.state == "KNOWN":
            require(
                type(fact.amount) is int
                and fact.source_ref is not None
                and fact.available_at is not None
                and fact.publication is not None,
                "QUALIFIED_VALUE_REQUIRED",
            )
            assert fact.available_at is not None and fact.publication is not None
            require(
                fact.version_ref == str(fact.source_ref) + "-VERSION", "SOURCE_VERSION_MISMATCH"
            )
            require(
                instant(fact.publication) <= instant(fact.available_at) < instant(value.cutoff),
                "FUTURE_FEATURE_REFUSED",
            )
        else:
            require(fact.amount is None, "STATE_VALUE_CONTAMINATION")
    return value


def _origin(ref: str, raw_digest: str) -> d.FieldOrigin:
    return d.FieldOrigin(
        d.Visibility.ACTIVE,
        "/f3_l1_sources/" + ref,
        d.OriginKnownValue(ref),
        d.OriginKnownValue("synthetic-notice-v1"),
        d.OriginKnownValue(raw_digest),
    )


def _aware(text: str, origin: d.FieldOrigin) -> d.AwareInstant:
    instant(text)
    return d.AwareInstant(text, "Asia/Taipei", "+08:00", "SECOND", origin)


def _notice(
    row: dict[str, Any],
    metric: str,
    period: tuple[date, date],
    subject_id: str,
    amount: int,
    unit: str,
) -> CandidateSource:
    """Translate a pinned declaration to actual S1/S2 input, not a completed result."""
    ref, issuer = row["id"], row["issuer"]
    version, rep, assertion = ref + "-VERSION", ref + "-RAW", ref + "-ASSERTION"
    source, locator = issuer + "-AUTHORED-PUBLIC", "synthetic://f3-l1/" + ref
    raw = research_bytes(
        {
            "schema": "synthetic-notice-v1",
            "content_version_id": version,
            "issuer_id": issuer,
            "source_locator": locator,
            "statements": [
                {
                    "assertion_id": assertion,
                    "subject_id": subject_id,
                    "period": [str(p) for p in period],
                    "metric": metric,
                    "unit": unit,
                    "value": amount,
                    "currency": "NTD",
                    "basis_id": row["basis"],
                    "reporting_scope": "consolidated",
                }
            ],
        }
    )
    raw_digest = sha256(raw).hexdigest()
    origin = _origin(ref, raw_digest)
    subject = d.SubjectFacts(
        subject_id,
        d.Known(issuer, origin),
        d.Known(metric, origin),
        d.Known("DURATION", origin),
        d.Known(period[0], origin),
        d.Known(period[1], origin),
        d.Known("consolidated", origin),
        d.Known(row["basis"], origin),
        "KNOWN",
        d.Known("NTD", origin),
        d.Known(unit, origin),
        origin,
    )
    content = d.ContentFacts(
        version,
        rep,
        raw,
        len(raw),
        raw_digest,
        "synthetic-notice-v1",
        d.Known(source, origin),
        d.Known(issuer, origin),
        d.Unknown(d.UnknownCause.EXPLICIT_SOURCE_UNKNOWN, None, origin),
        d.Known(locator, origin),
        (assertion,),
        (),
        origin,
    )
    requested = d.RequestedTuple(
        "ASSERTION", assertion, (subject_id,), version, rep, "/statements/0", origin
    )
    event = d.PublicationEventFacts(
        ref + "-DELIVERY",
        "issuer_publication",
        source,
        issuer,
        version,
        _origin(ref + "-DELIVERY", raw_digest),
    )
    proof_id = ref + "-TIME"
    descriptor: dict[str, str | None] = {
        "proof_id": proof_id,
        "target_kind": "assertion",
        "target_id": assertion,
        "content_version_id": version,
        "fragment_selector": "/statements/0",
        "proof_kind": "exact",
        "timestamp": row["available_at"],
        "timezone": "Asia/Taipei",
        "offset": "+08:00",
        "precision": "SECOND",
        "upper_bound": None,
        "bound": None,
        "source_date": None,
        "unparsed_source_text": None,
    }
    proof_origin = _origin(proof_id, raw_digest)
    proof = d.TimeProof(
        proof_id,
        "ASSERTION",
        assertion,
        version,
        "/statements/0",
        _aware(row["available_at"], proof_origin),
        tuple(sorted(descriptor.items())),
        proof_origin,
    )
    support = d.SupportBinding(
        ref + "-SUPPORT",
        ref + "-EVIDENCE",
        replace(requested, origin=_origin(ref + "-EVIDENCE", raw_digest)),
        "assertion_fragment",
        event,
        proof,
        _origin(ref + "-SUPPORT", raw_digest),
    )
    capture = d.CaptureFacts(
        ref + "-CAPTURE",
        rep,
        raw_digest,
        d.Known(_aware(row["available_at"], origin), origin),
        d.Known("SECOND", origin),
        "LAB_CAPTURE",
        origin,
    )
    member_pairs = [
        ("subjects", subject_id),
        ("assertions", assertion),
        ("content_versions", version),
        ("raw_assets", rep),
        ("supports", support.support_ref),
        ("evidence", support.evidence_ref),
        ("publication_events", event.event_ref),
        ("time_proofs", proof_id),
        ("observations", capture.observation_ref),
    ]
    members = tuple(
        sorted(
            (
                d.RoleRef(d.Visibility.ACTIVE, role, name, "/f3_l1_sources")
                for role, name in member_pairs
            ),
            key=lambda m: m.key,
        )
    )
    pins = (d.ContentPin(version, rep, len(raw), raw_digest),)
    scope = d.S1Scope(
        members, pins, d.SourceRecords(members, pins, (support,), (capture,), (event,), ())
    )
    assertion_fact = d.AssertionFacts(
        assertion,
        subject_id,
        d.Known(amount, origin),
        d.Known(unit, origin),
        period,
        version,
        origin,
    )
    request = d.IssuerBindingRequest(
        requested,
        content,
        assertion_fact,
        (d.RequestBindingAttempt(requested, support),),
        (capture,),
        (event,),
        scope,
    )
    return CandidateSource(subject, request, d.NotApplicable("S3", "NO_HISTORICAL_CLUE"))


def _context(cutoff: str, subject: str, dataset: str, code: CodeObservation) -> d.SemanticContext:
    origin = _origin("F2-L1-CONTEXT", dataset)
    profile = d.CandidateProfile(
        d.SCHEMA,
        "wu01-unit-v0.1-CANDIDATE",
        "wu01-reasons-v0.1-CANDIDATE",
        "s1-information-v0.1-CANDIDATE",
        code.observed_working_files,
        origin,
    )
    return d.SemanticContext(
        subject + "-" + cutoff,
        _aware(cutoff, origin),
        "public",
        "ATTRIBUTED_ASSERTION",
        dataset,
        "SYN-L1-CALENDAR-V1",
        ("L1-SELECTION", "P-OBS-1"),
        "NUM-1",
        profile,
        (),
        d.Unknown(d.UnknownCause.EXPLICIT_SOURCE_UNKNOWN, None, origin),
        "F3-L1-PROTOCOL-V1",
        (),
        d.TemporalPolicy(),
        origin,
    )


def _select(
    rows: list[dict[str, Any]],
    cutoff: str,
    dataset: str,
    code: CodeObservation,
    receipts: dict[str, dict[str, Any]] | None = None,
) -> RevenueFact:
    first = rows[0]
    month = first["month"]
    year, mon = map(int, month.split("-"))
    period = (date(year, mon, 1), date(year, mon, calendar.monthrange(year, mon)[1]))
    subject = first["issuer"] + "-REVENUE-" + month
    # State declarations qualify existence/maturity; their marker 1 is never a revenue value.
    candidates = tuple(
        _notice(
            r,
            "monthly_revenue_record_declared",
            period,
            subject,
            1,
            "declaration_flag",
        )
        for r in rows
    )
    by_id = {r["id"]: c for r, c in zip(rows, candidates, strict=True)}
    relations = []
    for row, candidate in zip(rows, candidates, strict=True):
        if row["supersedes"] is None:
            continue
        old = by_id[row["supersedes"]]
        relation = DirectRelation(
            row["id"] + "-REL",
            "CORRECTS",
            subject,
            old.request.requested.target_ref,
            old.request.content.content_version_ref,
            candidate.request.requested.target_ref,
            candidate.request.content.content_version_ref,
            row["id"] + "-NOTICE-ASSERTION",
            candidate.request.content.origin,
        )
        notice_row = {**row, "id": row["id"] + "-NOTICE"}
        notice = _notice(
            notice_row,
            relation_proposition(relation),
            period,
            subject + "-CORRECTION",
            1,
            "relation_declaration",
        )
        assert isinstance(notice.subject, d.SubjectFacts)
        relation = replace(relation, origin=notice.subject.metric.origin)
        relations.append(RelationSource(relation, notice))
    context = _context(cutoff, subject, dataset, code)
    policy = SelectionPolicy(
        "L1-SELECTION",
        "a03-policy-v0.1",
        subject,
        "public",
        "ATTRIBUTED_ASSERTION",
        first["issuer"],
        (first["issuer"] + "-AUTHORED-PUBLIC",),
        (),
        subject,
        REQUIRED_CHECKS,
    )
    refs = tuple(sorted(c.request.requested.target_ref for c in candidates))
    relrefs = tuple(sorted(r.relation.relation_ref for r in relations))
    checks = []
    for name in REQUIRED_CHECKS:
        raw = json.dumps(
            {
                "check": name,
                "scope": subject,
                "source_refs": sorted(policy.source_refs),
                "candidate_refs": list(refs),
                "relation_refs": list(relrefs),
                "context_ref": context.context_ref,
                "evidence_set_ref": dataset,
                "policy_ref": policy.policy_ref,
                "policy_version": policy.version,
                "status": "COMPLETED",
            },
            sort_keys=True,
        ).encode()
        checks.append(
            CoverageCheck(
                name, subject, "COMPLETED", (name,), raw, _origin(name, sha256(raw).hexdigest())
            )
        )
    coverage = BoundedCoverage(
        subject + "-COVERAGE",
        context.context_ref,
        dataset,
        policy.policy_ref,
        policy.version,
        subject,
        policy.source_refs,
        refs,
        relrefs,
        tuple(checks),
    )
    anchor = candidates[0].subject
    assert isinstance(anchor, d.SubjectFacts)
    actual = evaluate_asof(
        AsOfRequest(context, anchor, policy, coverage, candidates, tuple(relations)), code
    )
    selected = actual.selection
    if isinstance(selected, d.BlockingFailure):
        raise PanelError("NATIVE_" + selected.code)
    receipt: dict[str, Any] = {
        "schema": "F2_L1_QUALIFICATION_RECEIPT_V1",
        "non_if03": True,
        "dataset_digest": dataset,
        "cutoff": cutoff,
        "subject": subject,
        "state": selected.state,
        "reason": selected.reason,
        "native_invocation": "RUN",
        "selected_sources": [
            {
                "assertion": c.ref,
                "source_sha256": c.source.request.content.raw_sha256,
                "s1": getattr(c.actual.s1, "state", "FAILURE"),
                "s2": getattr(c.actual.s2, "state", "FAILURE"),
            }
            for c in actual.inputs.candidates
            if c.ref in selected.selected_assertion_refs
        ],
        "code_pins": [{"path": p.path, "sha256": p.sha256} for p in code.observed_working_files],
    }
    value_amount = None
    chosen = None
    if selected.state == "SELECTED":
        matches = [r for r in rows if r["id"] + "-ASSERTION" in selected.selected_assertion_refs]
        require(len(matches) == 1, "AMBIGUOUS_SELECTED_SOURCE")
        chosen = matches[0]
        if chosen["state"] == "KNOWN":
            value_source = _notice(
                {**chosen, "id": chosen["id"] + "-VALUE"},
                "net_operating_revenue",
                period,
                subject + "-VALUE",
                chosen["amount"],
                chosen["unit"],
            )
            qualified_value = evaluate_slice(context, value_source.request, code)
            require(
                not isinstance(qualified_value.s1, d.BlockingFailure)
                and not isinstance(qualified_value.s2, d.BlockingFailure),
                "REVENUE_VALUE_QUALIFICATION",
            )
            assert not isinstance(qualified_value.s1, d.BlockingFailure)
            assert not isinstance(qualified_value.s2, d.BlockingFailure)
            require(
                qualified_value.s1.state == "BOUND"
                and qualified_value.s2.state == "SUPPORTED"
                and isinstance(qualified_value.s1.source_amount, d.Known),
                "REVENUE_VALUE_UNAVAILABLE",
            )
            assert isinstance(qualified_value.s1.source_amount, d.Known)
            value_amount = qualified_value.s1.source_amount.value
            require(value_amount == chosen["amount"], "REVENUE_VALUE_MISMATCH")
            receipt["revenue_value"] = {
                "source_sha256": value_source.request.content.raw_sha256,
                "s1": qualified_value.s1.state,
                "s2": qualified_value.s2.state,
                "native_invocation": "RUN",
                "value": value_amount,
            }
    qualification_ref = digest(receipt)
    if receipts is not None:
        receipts[qualification_ref] = receipt
    if selected.state != "SELECTED":
        return RevenueFact(
            month,
            "ABSENT" if selected.state == "NO_QUALIFIED_CLAIM" else "REJECTED",
            None,
            None,
            None,
            None,
            first["unit"],
            first["basis"],
            selected.state,
            selected.reason,
            qualification_ref,
        )
    assert chosen is not None
    row = chosen
    return RevenueFact(
        month,
        row["state"],
        value_amount,
        row["id"],
        row["publication"],
        row["available_at"],
        row["unit"],
        row["basis"],
        selected.state,
        "NONE" if row["state"] == "KNOWN" else row["state"],
        qualification_ref,
        version_ref=row["id"] + "-VERSION",
    )


def _validate(body: dict[str, Any]) -> None:
    closed(
        body,
        "schema generator seed price_seed issuers calendar_id calendar cutoffs revenues prices "
        "outcome_release_delay_sessions limitations",
    )
    require(
        body["schema"] == SCHEMA
        and body["generator"] == "independent-streams-v1"
        and body["seed"] == 17
        and body["price_seed"] == 17001,
        "DATASET_VERSION",
    )
    require(
        body["issuers"] == [f"SYN-L1-{i}" for i in range(1, 6)]
        and body["calendar_id"] == "SYN-L1-CALENDAR-V1"
        and body["outcome_release_delay_sessions"] == 1,
        "DATASET_IDENTITY",
    )
    days, sessions = [], []
    for row in body["calendar"]:
        closed(row, "date status close")
        day = date.fromisoformat(row["date"])
        days.append(day)
        require(row["status"] in {"CLOSED", "SESSION"}, "CALENDAR_STATE")
        if row["status"] == "SESSION":
            require(
                instant(row["close"]).date() == day and row["close"][11:] < "18:00:00+08:00",
                "SESSION_CLOCK",
            )
            sessions.append(row["date"])
        else:
            require(row["close"] is None, "CLOSED_SESSION")
    require(days == [date(2024, 1, 1) + timedelta(days=i) for i in range(790)], "CALENDAR_COVERAGE")
    weekly: dict[tuple[int, int], str] = {}
    for day_text in sessions:
        if day_text >= "2024-03-04":
            weekly[date.fromisoformat(day_text).isocalendar()[:2]] = day_text + "T18:00:00+08:00"
    expected = list(weekly.values())[:96]
    require(body["cutoffs"] == expected and len(expected) == 96, "FIXED_DECISION_SCHEDULE")
    require(len([s for s in sessions if s > expected[-1][:10]]) >= 21, "INSUFFICIENT_PRICE_TAIL")
    ids = []
    for row in body["revenues"]:
        closed(
            row,
            "id issuer month period_end publication available_at effective_at state amount unit "
            "basis supersedes",
        )
        ids.append(row["id"])
        require(row["issuer"] in body["issuers"] and row["state"] in STATES, "SOURCE_IDENTITY")
        require(
            row["unit"] == "NTD_thousands" and row["basis"] == "consolidated-v1",
            "SOURCE_UNIT_BASIS",
        )
        require(
            instant(row["publication"]) <= instant(row["available_at"]),
            "DELIVERY_BEFORE_PUBLICATION",
        )
        require(
            row["period_end"][:7] == row["month"]
            and instant(row["effective_at"]).date() == date.fromisoformat(row["month"] + "-01"),
            "REVENUE_PERIOD",
        )
        require(
            (type(row["amount"]) is int and 0 < row["amount"] < 2**63)
            if row["state"] == "KNOWN"
            else row["amount"] is None,
            "REVENUE_VALUE",
        )
    require(len(ids) == len(set(ids)), "DUPLICATE_SOURCE")
    by_id = {r["id"]: r for r in body["revenues"]}
    for row in body["revenues"]:
        if row["supersedes"] is not None:
            old = by_id.get(row["supersedes"])
            require(
                old is not None
                and old["issuer"] == row["issuer"]
                and old["month"] == row["month"]
                and instant(old["available_at"]) < instant(row["available_at"]),
                "REVISION_LINEAGE",
            )
    cells = []
    closes = {r["date"]: r["close"] for r in body["calendar"] if r["status"] == "SESSION"}
    for row in body["prices"]:
        closed(row, "id issuer session value available_at unit basis")
        require(row["issuer"] in body["issuers"] and row["session"] in closes, "PRICE_IDENTITY")
        require(
            row["id"] == f"{row['issuer']}-CLOSE-{row['session']}"
            and type(row["value"]) is int
            and 0 < row["value"] < 2**63
            and row["unit"] == "NTD_price_ticks_1e4"
            and row["basis"] == "unadjusted-synthetic-v1",
            "PRICE_VALUE",
        )
        require(
            instant(row["available_at"]) > instant(closes[row["session"]]), "PRICE_AVAILABILITY"
        )
        cells.append((row["issuer"], row["session"]))
    require(
        len(cells) == len(set(cells))
        and set(cells) == {(issuer, session) for issuer in body["issuers"] for session in sessions},
        "PRICE_GRID",
    )


class ResearchPanel:
    """Trusted loader/kernel. Future-containing data is private, never a feature DTO."""

    def __init__(self, body: dict[str, Any], *, _key: object = None) -> None:
        require(_key is _LOADER, "PINNED_LOADER_REQUIRED")
        _validate(body)
        self.__body = decode(research_bytes(body))
        body = self.__body
        self.dataset_digest = digest(body)
        self.cutoffs: tuple[str, ...] = tuple(body["cutoffs"])
        self.issuers: tuple[str, ...] = tuple(body["issuers"])
        self.calendar_id: str = body["calendar_id"]
        self.__sessions = tuple(r["date"] for r in body["calendar"] if r["status"] == "SESSION")
        self.__prices = {(r["issuer"], r["session"]): r for r in body["prices"]}
        self.__revenues: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for row in body["revenues"]:
            self.__revenues.setdefault((row["issuer"], row["month"]), []).append(row)
        self.__code = observe_asof_code(ROOT)
        self.__observations: dict[tuple[str, int], PanelObservation] = {}
        self.__qualifications: dict[str, dict[str, Any]] = {}
        self.native_invocations = 0

    def observation(self, issuer: str, tick: int) -> PanelObservation:
        require(
            issuer in self.issuers and type(tick) is int and 0 <= tick < 96, "OBSERVATION_IDENTITY"
        )
        if (issuer, tick) in self.__observations:
            return verify_observation(self.__observations[issuer, tick])
        cutoff = self.cutoffs[tick]
        months = sorted(
            (m for i, m in self.__revenues if i == issuer and m <= cutoff[:7]), reverse=True
        )
        current = None
        for month in months:
            fact = _select(
                self.__revenues[issuer, month],
                cutoff,
                self.dataset_digest,
                self.__code,
                self.__qualifications,
            )
            self.native_invocations += 2 if fact.state == "KNOWN" else 1
            if fact.native_state != "NO_QUALIFIED_CLAIM":
                current = fact
                break
        require(current is not None, "NO_DECLARED_REVENUE")
        assert current is not None
        year, month_num = map(int, current.month.split("-"))
        prev_month = f"{year - (month_num == 1)}-{(month_num - 2) % 12 + 1:02}"
        rows = self.__revenues.get((issuer, prev_month))
        if rows:
            previous = _select(
                rows, cutoff, self.dataset_digest, self.__code, self.__qualifications
            )
            self.native_invocations += 2 if previous.state == "KNOWN" else 1
        else:
            previous = RevenueFact(
                prev_month,
                "ABSENT",
                None,
                None,
                None,
                None,
                "NTD_thousands",
                "consolidated-v1",
                "NO_QUALIFIED_CLAIM",
                "MISSING_PREDECESSOR",
                None,
            )
        values = dict(
            sample_id=f"{issuer}:t{tick:02}",
            issuer=issuer,
            tick=tick,
            cutoff=cutoff,
            dataset_digest=self.dataset_digest,
            calendar_id=self.calendar_id,
            current=asdict(current),
            previous=asdict(previous),
        )
        obs = PanelObservation(
            f"{issuer}:t{tick:02}",
            issuer,
            tick,
            cutoff,
            self.dataset_digest,
            self.calendar_id,
            current,
            previous,
            digest(values),
            hmac.digest(_KEY, research_bytes(values), "sha256"),
        )
        self.__observations[issuer, tick] = verify_observation(obs)
        return obs

    def target_timing(self, observation: PanelObservation) -> dict[str, str]:
        obs = verify_observation(observation)
        require(
            obs.dataset_digest == self.dataset_digest and obs.cutoff == self.cutoffs[obs.tick],
            "FOREIGN_OBSERVATION",
        )
        candidates = [
            s
            for s in self.__sessions
            if s <= obs.cutoff[:10]
            and instant(self.__prices[obs.issuer, s]["available_at"]) < instant(obs.cutoff)
        ]
        require(bool(candidates), "NO_START_MARK")
        start = candidates[-1]
        index = self.__sessions.index(start)
        require(index + 21 < len(self.__sessions), "INSUFFICIENT_PRICE_TAIL")
        end, release_session = self.__sessions[index + 20], self.__sessions[index + 21]
        release = release_session + "T18:00:00+08:00"
        available = max(
            release,
            self.__prices[obs.issuer, start]["available_at"],
            self.__prices[obs.issuer, end]["available_at"],
        )
        return {
            "start": start,
            "end": end,
            "available_at": available,
            "outcome_release": release,
            "horizon": "20_SUBSEQUENT_SESSIONS",
        }

    def outcome(self, observation: PanelObservation, asof: str) -> dict[str, Any]:
        timing = self.target_timing(observation)
        require(instant(timing["available_at"]) <= instant(asof), "IMMATURE_LABEL")
        marks = []
        for role in ("start", "end"):
            row = self.__prices[observation.issuer, timing[role]]
            day = date.fromisoformat(row["session"])
            source = _notice(
                row, "synthetic_close_price", (day, day), row["id"], row["value"], row["unit"]
            )
            # Outcome reading is inclusive at asof; S2's strict rule is unchanged.
            context = _context(
                (instant(asof) + timedelta(seconds=1)).isoformat(),
                row["id"],
                self.dataset_digest,
                self.__code,
            )
            actual = evaluate_slice(context, source.request, self.__code)
            self.native_invocations += 1
            require(
                not isinstance(actual.s1, d.BlockingFailure)
                and not isinstance(actual.s2, d.BlockingFailure),
                "PRICE_QUALIFICATION_FAILURE",
            )
            assert not isinstance(actual.s2, d.BlockingFailure)
            assert not isinstance(actual.s1, d.BlockingFailure)
            require(
                actual.s1.state == "BOUND"
                and actual.s2.state == "SUPPORTED"
                and isinstance(actual.s1.source_amount, d.Known),
                "PRICE_UNAVAILABLE",
            )
            assert isinstance(actual.s1.source_amount, d.Known)
            require(actual.s1.source_amount.value == row["value"], "PRICE_VALUE_MISMATCH")
            marks.append(
                {
                    "ref": row["id"],
                    "version_ref": row["id"] + "-VERSION",
                    "value": actual.s1.source_amount.value,
                    "available_at": row["available_at"],
                    "source_digest": sha256(source.request.content.raw_bytes).hexdigest(),
                    "native_state": actual.s2.state,
                    "native_reason": actual.s2.reason,
                }
            )
        return {
            **timing,
            "sample_id": observation.sample_id,
            "dataset_digest": self.dataset_digest,
            "marks": marks,
            "native_invocation": "RUN",
            "non_if03": True,
        }

    def source_summary(self) -> dict[str, Any]:
        return {
            "dataset_digest": self.dataset_digest,
            "calendar_id": self.calendar_id,
            "issuer_roster": list(self.issuers),
            "cutoffs": list(self.cutoffs),
            "calendar_coverage": [
                self.__body["calendar"][0]["date"],
                self.__body["calendar"][-1]["date"],
            ],
            "revenue_declarations": len(self.__body["revenues"]),
            "price_marks": len(self.__prices),
            "scope": "AUTHORED_SYNTHETIC_PUBLIC_ONLY",
            "non_if03": True,
            "admission_eligible": False,
            "source_authentication": "NOT_ESTABLISHED",
            "native_invocations": self.native_invocations,
            "invocation_count_scope": "TOP_LEVEL_ASOF_AND_EXPLICIT_S1_S2_CALLS_EXCLUDES_TRANSITIVE_REPLAY",
        }

    def qualification_receipts(self) -> dict[str, dict[str, Any]]:
        """Detached safe receipts; no raw/audit graph or future candidate identity."""
        return decode(research_bytes(self.__qualifications))  # type: ignore[no-any-return]


def load_panel() -> ResearchPanel:
    for name in (FIXTURE, MANIFEST):
        path = ROOT / name
        require(not any(p.is_symlink() for p in (path, *path.parents)), "SOURCE_SYMLINK")
    raw = (ROOT / FIXTURE).read_bytes()
    manifest_raw = (ROOT / MANIFEST).read_bytes()
    require(sha256(manifest_raw).hexdigest() == MANIFEST_SHA256, "MANIFEST_PIN_MISMATCH")
    manifest = decode(manifest_raw)
    closed(
        manifest, "schema file sha256 byte_length generator seed price_seed qualification non_if03"
    )
    require(
        sha256(raw).hexdigest() == SOURCE_SHA256 == manifest["sha256"]
        and len(raw) == manifest["byte_length"]
        and manifest["schema"] == "F2_L1_SOURCE_MANIFEST_V1"
        and manifest["non_if03"] is True
        and manifest["file"] == Path(FIXTURE).name
        and manifest["generator"] == "independent-streams-v1"
        and manifest["seed"] == 17
        and manifest["price_seed"] == 17001
        and manifest["qualification"] == "NOT_IMPLIED_BY_MANIFEST",
        "SOURCE_PIN_MISMATCH",
    )
    return ResearchPanel(decode(raw), _key=_LOADER)
