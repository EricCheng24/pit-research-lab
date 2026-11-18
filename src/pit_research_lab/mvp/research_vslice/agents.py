"""Two deterministic research adapters; no trades, trained model, prices or outcomes."""

from dataclasses import dataclass

from .contracts import ResearchObservation, require


@dataclass(frozen=True, slots=True)
class NoDataBaseline:
    seed: int
    agent_id: str = "no_data_baseline_v1"

    def choose(self, observation: ResearchObservation) -> str:
        require(type(observation) is ResearchObservation, "OBSERVATION_REQUIRED")
        return "HOLD" if self.seed % 2 else "ABSTAIN"


@dataclass(frozen=True, slots=True)
class EligibleFeatureRule:
    threshold: int = 105
    agent_id: str = "eligible_rule_v1"

    def __post_init__(self) -> None:
        require(type(self.threshold) is int and 0 <= self.threshold < 2**63, "INVALID_THRESHOLD")

    def choose(self, observation: ResearchObservation) -> str:
        require(type(observation) is ResearchObservation, "OBSERVATION_REQUIRED")
        feature = next(f for f in observation.features if f.key == "december")
        if feature.state != "KNOWN" or feature.value is None:
            return "ABSTAIN"
        return "FLAG_REVIEW" if feature.value >= self.threshold else "HOLD"
