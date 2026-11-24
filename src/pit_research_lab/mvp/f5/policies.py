"""Three fixed observation-only rules; no importer, filesystem or evaluator capability."""

from fractions import Fraction

from .contracts import POLICIES, DecisionObservation, TargetAction, require


def choose(obs: DecisionObservation, policy: str) -> TargetAction:
    require(type(obs) is DecisionObservation and policy in POLICIES, "POLICY_INPUT")
    obs.validate()
    selected, reasons = [], []
    for item in obs.issuers:
        if not item.research_eligible:
            reason = item.eligibility_reason
        elif policy == POLICIES[0]:
            reason = "QUALIFIED_UNIVERSE_MEMBER"
            selected.append(item.issuer)
        elif policy == POLICIES[1]:
            assert item.growth is not None
            reason = "POSITIVE_GROWTH_SELECTED" if item.growth > 0 else "NONPOSITIVE_GROWTH"
            if item.growth > 0:
                selected.append(item.issuer)
        else:
            if item.forecast.state != "PREDICTED":
                reason = item.forecast.reason
            else:
                assert item.forecast.value is not None
                reason = (
                    "POSITIVE_FORECAST_SELECTED"
                    if item.forecast.value > 0
                    else "NONPOSITIVE_FORECAST"
                )
                if item.forecast.value > 0:
                    selected.append(item.issuer)
        reasons.append((item.issuer, reason))
    weight = min(Fraction(1, len(selected)), Fraction(1, 2)) if selected else Fraction()
    weights = tuple((i.issuer, weight if i.issuer in selected else Fraction()) for i in obs.issuers)
    unavailable = not any(i.research_eligible for i in obs.issuers)
    disposition = "ALLOCATE" if selected else ("ABSTAIN" if unavailable else "CASH")
    reason = "PARTIAL_INFORMATION" if any(not i.research_eligible for i in obs.issuers) else "NONE"
    if disposition == "ABSTAIN":
        reason = "NO_ELIGIBLE_SIGNAL"
    result = TargetAction(
        policy,
        obs.tick,
        obs.cutoff,
        obs.information_digest,
        disposition,
        weights,
        1 - sum((w for _, w in weights), Fraction()),
        tuple(reasons),
        reason,
    )
    result.validate(obs, policy)
    return result
