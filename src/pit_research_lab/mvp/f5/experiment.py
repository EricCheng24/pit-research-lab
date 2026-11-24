"""Two-pass decision census followed by isolated, atomic common-calendar evaluation."""

import copy
import time
from collections import Counter
from collections.abc import Callable
from datetime import timedelta
from fractions import Fraction
from typing import Any

from pit_research_lab.mvp.f2.research_panel import instant
from pit_research_lab.mvp.f3_l1.contracts import fraction_read as f2_fraction

from .accounting import Book, metrics, rebalance
from .contracts import (
    COMPLETE,
    DEGRADED,
    INCOMPLETE,
    ISSUERS,
    POLICIES,
    DecisionObservation,
    DecisionSlot,
    EngineFailureDisposition,
    Protocol,
    SealedDecisions,
    TargetAction,
    digest,
    require,
    safe_reason,
    seal_slots,
    verify_barrier,
    wire,
)
from .policies import choose


class DecisionCursor:
    """Trusted scheduler only; a policy receives its current value, never this cursor."""

    def __init__(self, observations: tuple[DecisionObservation, ...]) -> None:
        self.__observations = observations
        self.__next = 48

    def release(self, tick: int) -> DecisionObservation:
        require(tick == self.__next and len(self.__observations) == 48, "SEMANTIC_CURSOR")
        obs = self.__observations[tick - 48]
        obs.validate(production=True)
        require(obs.tick == tick, "SEMANTIC_CURSOR")
        self.__next += 1
        return obs


def prepare(
    observations: tuple[DecisionObservation, ...],
    cutoffs: tuple[str, ...],
    policy: Callable[[DecisionObservation, str], TargetAction] = choose,
) -> SealedDecisions:
    require(len(cutoffs) == 96 and tuple(sorted(set(cutoffs))) == cutoffs, "DECISION_SCHEDULE")
    cursor, slots, common = DecisionCursor(observations), [], None
    for tick in range(48, 96):
        obs = None
        if common is None:
            try:
                obs = cursor.release(tick)
                require(obs.cutoff == cutoffs[tick], "DECISION_SCHEDULE")
            except Exception as error:
                common = safe_reason(error)
        for name in POLICIES:
            if common is not None:
                slots.append(
                    DecisionSlot(
                        tick,
                        cutoffs[tick],
                        name,
                        None,
                        "BLOCKED_NOT_ATTEMPTED",
                        False,
                        None,
                        None,
                        common,
                        None,
                    )
                )
                continue
            assert obs is not None
            try:
                detached = copy.deepcopy(obs)
                action = policy(detached, name)
                require(type(action) is TargetAction, "INVALID_ACTION")
                action.validate(obs, name)
                slots.append(
                    DecisionSlot(
                        tick,
                        obs.cutoff,
                        name,
                        obs.information_digest,
                        "VALID",
                        True,
                        action.action_digest,
                        action,
                        None,
                        None,
                    )
                )
            except Exception as error:
                cause = safe_reason(error)
                failure = digest(
                    {
                        "tick": tick,
                        "cutoff": obs.cutoff,
                        "policy_id": name,
                        "information_digest": obs.information_digest,
                        "failure_cause": cause,
                    }
                )
                slots.append(
                    DecisionSlot(
                        tick,
                        obs.cutoff,
                        name,
                        obs.information_digest,
                        "FAILED_POLICY",
                        True,
                        failure,
                        None,
                        cause,
                        EngineFailureDisposition(failure),
                    )
                )
    return seal_slots(tuple(slots), common)


def census(sealed: SealedDecisions) -> dict[str, Any]:
    counts = Counter(s.outcome for s in sealed.slots)
    return {
        "expected_ticks": 48,
        "expected_slots": 144,
        "sealed_slots": len(sealed.slots),
        "valid": counts["VALID"],
        "failed_policy": counts["FAILED_POLICY"],
        "blocked_not_attempted": counts["BLOCKED_NOT_ATTEMPTED"],
        "attempted": sum(s.attempted for s in sealed.slots),
        "committed_engine_fallback": sum(s.engine_disposition is not None for s in sealed.slots),
        "expected_oos_cells": 240,
        "expected_historical_bindings": 480,
        "expected_common_mark_cells": 1205,
        "expected_weekly_returns_per_book": 48,
        "expected_opportunities_per_book": 48,
        "per_policy": {
            p: dict(Counter(s.outcome for s in sealed.slots if s.policy_id == p)) for p in POLICIES
        },
    }


def evaluate(
    sealed: SealedDecisions,
    calendar: tuple[tuple[str, str], ...],
    cutoffs: tuple[str, ...],
    price_factory: Callable[[SealedDecisions], Any] | None = None,
) -> dict[str, Any]:
    verify_barrier(sealed)  # MUST precede even construction of a price provider.
    protocol = Protocol()
    protocol.validate()
    if price_factory is None:
        from .prices import EvaluationPrices

        price_factory = EvaluationPrices
    started = time.monotonic()
    sessions = tuple(
        day for day, _ in calendar if cutoffs[48][:10] <= day <= protocol.terminal[:10]
    )
    require(
        len(sessions) == 241
        and sessions[0] == cutoffs[48][:10]
        and sessions[-1] == protocol.terminal[:10],
        "EVALUATION_CALENDAR",
    )
    closes = dict(calendar)
    require(
        len(closes) == len(calendar)
        and all(instant(close).date().isoformat() == day for day, close in calendar),
        "CALENDAR_SESSION",
    )
    fills = {next((d for d in sessions if d > cutoffs[t][:10]), ""): t for t in range(48, 96)}
    require(len(fills) == 48 and "" not in fills and fills.get("2026-01-12") == 95, "FILL_SCHEDULE")
    weeks = set(c[:10] for c in cutoffs[49:96]) | {protocol.terminal[:10]}
    provider = price_factory(sealed)
    books = {(p, mirror): Book.initial(ISSUERS) for p in POLICIES for mirror in (False, True)}
    equity_paths = {key: [protocol.initial_cash] for key in books}
    costs = {key: [Fraction()] for key in books}
    weekly = {key: [protocol.initial_cash] for key in books}
    events: list[dict[str, Any]] = []
    valuations: list[dict[str, Any]] = []
    marks: list[dict[str, Any]] = []
    processed: Counter[tuple[str, bool]] = Counter()
    fallback: Counter[tuple[str, bool]] = Counter()
    stop = None
    mark_requests = returned_marks = 0
    for day in sessions:
        try:
            require(time.monotonic() - started <= 120, "EVALUATION_BUDGET")
            asof = (instant(closes[day]) + timedelta(seconds=1)).isoformat()
            staged_marks = []
            for issuer in ISSUERS:
                mark_requests += 1
                staged_marks.append(provider.read_mark(issuer, day, asof))
                returned_marks += 1
            current_marks = tuple(staged_marks)
            require(
                tuple(m.issuer for m in current_marks) == ISSUERS
                and all(
                    m.session == day
                    and m.close_time == closes[day]
                    and m.available_at == asof
                    and m.native_s1_state == "BOUND"
                    and m.native_s2_state == "SUPPORTED"
                    and type(m.value_ticks) is int
                    and 0 < m.value_ticks < 2**63
                    and m.unit == "NTD_price_ticks_1e4"
                    and m.basis == "unadjusted-synthetic-v1"
                    and m.version_id == m.source_id + "-VERSION"
                    and m.witness_kind == "PINNED_AUTHORED_DELIVERY"
                    and m.witness_time == asof
                    and m.original_publication_state == "NOT_PROVIDED_IN_PRICE_ROW"
                    and m.invocation == "RUN"
                    and m.diagnostic_only
                    and not m.admission_eligible
                    and m.source_authentication == "NOT_ESTABLISHED"
                    for m in current_marks
                ),
                "COMMON_MARK_QUALIFICATION",
            )
            prices = tuple((m.issuer, Fraction(m.value_ticks, 10000)) for m in current_marks)
            # Stage the ENTIRE common event. No book is posted until all succeed.
            next_books, staged, staged_paths, staged_costs = dict(books), [], {}, {}
            for key, book in books.items():
                p, mirror = key
                E = book.equity(prices)
                staged_paths[key], staged_costs[key] = [E], [Fraction()]
                if day in fills:
                    tick = fills[day]
                    slot = sealed.slots[(tick - 48) * 3 + POLICIES.index(p)]
                    if slot.outcome == "FAILED_POLICY":
                        staged.append(
                            {
                                "policy": p,
                                "mirror": mirror,
                                "tick": tick,
                                "reference_time": closes[day],
                                "posted_at": asof,
                                "event": "ENGINE_HOLD_EXISTING",
                                "equity": E,
                                "cash": book.cash,
                                "shares": book.shares,
                                "fee": Fraction(),
                                "slippage": Fraction(),
                            }
                        )
                    else:
                        assert slot.policy_action is not None
                        fill = rebalance(
                            book,
                            prices,
                            slot.policy_action.weights,
                            Fraction() if mirror else protocol.fee,
                            Fraction() if mirror else protocol.slippage,
                        )
                        next_books[key] = fill.after
                        staged_paths[key].append(fill.post_equity)
                        staged_costs[key].append(fill.fee + fill.slippage)
                        staged.append(
                            {
                                "policy": p,
                                "mirror": mirror,
                                "tick": tick,
                                "reference_time": closes[day],
                                "posted_at": asof,
                                "event": "TRADE" if fill.traded_notional else "NO_TRADE",
                                "fill": wire(fill),
                                "action_digest": slot.policy_action.action_digest,
                                "traded_legs": sum(q != 0 for _, q in fill.delta_shares),
                            }
                        )
            require(time.monotonic() - started <= 120, "EVALUATION_BUDGET")
            books = next_books
            marks.extend(wire(m) for m in current_marks)
            events.extend(staged)
            for key, book in books.items():
                valuations.append(
                    {
                        "policy": key[0],
                        "mirror": key[1],
                        "session": day,
                        "reference_time": closes[day],
                        "available_at": asof,
                        "pre_fill_equity": staged_paths[key][0],
                        "post_event_equity": book.equity(prices),
                        "cash": book.cash,
                        "shares": book.shares,
                    }
                )
            for event in staged:
                k = (str(event["policy"]), bool(event["mirror"]))
                processed[k] += 1
                if event["event"] == "ENGINE_HOLD_EXISTING":
                    fallback[k] += 1
            for key in books:
                equity_paths[key].extend(staged_paths[key])
                costs[key].extend(staged_costs[key])
                if day in weeks:
                    weekly[key].append(books[key].equity(prices))
        except Exception as error:
            stop = {
                "reason": safe_reason(error),
                "session": day,
                "qualification": getattr(provider, "last_qualification", {"invocation": "NOT_RUN"}),
            }
            break
    complete = (
        stop is None
        and len(marks) == 1205
        and all(len(v) == 49 for v in weekly.values())
        and all(processed[k] == 48 for k in books)
    )
    candidate_class = (
        INCOMPLETE
        if not complete
        else (DEGRADED if any(s.outcome == "FAILED_POLICY" for s in sealed.slots) else COMPLETE)
    )
    reports = {}
    for key, book in books.items():
        p, mirror = key
        name = p + ("_ZERO_COST_MIRROR" if mirror else "")
        diagnostic = metrics(tuple(equity_paths[key]), tuple(costs[key]), tuple(weekly[key]))
        book_events = [x for x in events if x["policy"] == p and x["mirror"] == mirror]
        reports[name] = {
            "trade_events": sum(x["event"] == "TRADE" for x in book_events),
            "no_trade_events": sum(x["event"] == "NO_TRADE" for x in book_events),
            "traded_legs": sum(x.get("traded_legs", 0) for x in book_events),
            "total_fee": sum(
                (f2_fraction(x["fill"]["fee"]) for x in book_events if "fill" in x), Fraction()
            ),
            "total_slippage": sum(
                (f2_fraction(x["fill"]["slippage"]) for x in book_events if "fill" in x), Fraction()
            ),
            "unapplied_fallback": sum(
                s.engine_disposition is not None and s.policy_id == p for s in sealed.slots
            )
            - fallback[key],
            "candidate_metrics": diagnostic,
            "full_period_candidate": diagnostic
            if complete
            else {"state": "NOT_COMPUTABLE", "reason": stop["reason"] if stop else "COVERAGE"},
            "terminal_book": wire(book),
            "processed_opportunities": processed[key],
            "applied_fallback": fallback[key],
            "weekly_returns_evaluated": len(weekly[key]) - 1,
        }
    return {
        "candidate_class": candidate_class,
        "common_failure": stop,
        "coverage": census(sealed)
        | {
            "qualified_common_mark_cells": len(marks),
            "committed_common_mark_cells": len(marks),
            "mark_requests": mark_requests,
            "returned_mark_records": returned_marks,
            "native_slice_attempts": getattr(provider, "native_invocations", None),
            "successful_native_qualified_reads": getattr(provider, "qualified_reads", None),
            "complete_calendar": complete,
        },
        "books": reports,
        "events": events,
        "valuations": valuations,
        "marks": marks,
        "limitations": [
            "AUTHORED_SYNTHETIC_ONLY",
            "NO_APP_OR_NATIVE_ADMISSION",
            "NO_LIVE_EXECUTION",
            "NO_IID_OR_PROFITABILITY_CLAIM",
            "COOPERATIVE_API_NOT_HOSTILE_CODE_SANDBOX",
        ],
    }
