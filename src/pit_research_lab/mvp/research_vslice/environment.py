"""Four-step research choices. Cooperative interface isolation, not a Python sandbox."""

from dataclasses import dataclass, replace

from .asof import asof_view
from .contracts import ACTIONS, AGENTS, CUTOFFS, ResearchObservation, require
from .sources import EventLedger, load_pinned_synthetic_events


@dataclass(frozen=True, slots=True)
class Transition:
    tick_order: int
    cutoff: str
    action: str | None
    disposition: str
    next_tick_order: int | None
    terminal: bool


@dataclass(frozen=True, slots=True)
class StepResult:
    observation: ResearchObservation | None
    transition: Transition


class ResearchEnvironment:
    """Adapters receive only observations. No public future accessor or ledger property."""

    __slots__ = ("__ledger", "__index", "__active", "__transitions")

    def __init__(self, ledger: EventLedger | None = None) -> None:
        self.__ledger = load_pinned_synthetic_events() if ledger is None else ledger
        require(type(self.__ledger) is EventLedger, "LEDGER_REQUIRED")
        self.__index = 0
        self.__active = False
        self.__transitions: tuple[Transition, ...] = ()

    def __repr__(self) -> str:
        return "ResearchEnvironment(RESEARCH_VSLICE_V0.1)"

    def reset(self, seed: int, agent_id: str) -> ResearchObservation:
        require(type(seed) is int and 0 <= seed < 2**63, "INVALID_SEED")
        require(type(agent_id) is str and agent_id in AGENTS, "UNKNOWN_AGENT")
        self.__index = 0
        self.__transitions = ()
        self.__active = True
        return self.observe()

    def observe(self) -> ResearchObservation:
        require(self.__active, "EPISODE_NOT_ACTIVE")
        # Rebuild a detached value; even low-level mutation of a prior public object
        # cannot change the trusted ledger or subsequent observations.
        view = asof_view(self.__ledger, CUTOFFS[self.__index])
        return replace(
            view,
            features=tuple(
                replace(f, provenance=(replace(f.provenance) if f.provenance is not None else None))
                for f in view.features
            ),
        )

    def step(self, action: object) -> StepResult:
        require(self.__active, "EPISODE_NOT_ACTIVE")
        valid = type(action) is str and action in ACTIONS
        terminal = bool(valid and self.__index == 3)
        next_index = None if terminal else self.__index + (1 if valid else 0)
        transition = Transition(
            self.__index,
            CUTOFFS[self.__index],
            str(action) if valid else None,
            "TERMINATED" if terminal else ("ADVANCED" if valid else "REFUSED_INVALID_ACTION"),
            next_index,
            terminal,
        )
        self.__transitions = (*self.__transitions, transition)
        if valid:
            if terminal:
                self.__active = False
            else:
                self.__index += 1
        return StepResult(None if terminal else self.observe(), transition)

    def transitions(self) -> tuple[Transition, ...]:
        return tuple(replace(t) for t in self.__transitions)
