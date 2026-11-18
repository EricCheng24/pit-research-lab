"""Stable research bytes and identity scoped to inputs, code, tests, config and runtime."""

import platform
import sys
from dataclasses import asdict
from hashlib import sha256
from typing import Any

from . import VERSION
from .agents import EligibleFeatureRule, NoDataBaseline
from .contracts import ACTIONS, AGENTS, CUTOFFS, require, research_bytes
from .environment import ResearchEnvironment
from .sources import BASELINE, SOURCE_PINS, EventLedger, checkout_root, regular_bytes

STAGE_V_IDS = (
    "RC01-T01",
    "RC01-T02",
    "RC01-T03",
    "RC02-T01",
    "RC02-T02",
    "RC02-T03",
    "RC03-T01",
    "RC03-T02",
    "RC03-T03",
    "RC04-T01",
    "RC04-T03",
    "RC05-T01",
)
STAGE_M_IDS = (
    "RC01-T04",
    "RC02-T04",
    "RC04-T02",
    "RC05-T02",
    "RC05-T03",
    "RC06-T01",
    "RC06-T02",
    "RC06-T03",
)
CODE_FILES = (
    "__init__.py",
    "contracts.py",
    "sources.py",
    "asof.py",
    "environment.py",
    "agents.py",
    "replay.py",
    "cli.py",
)
TEST_FILES = ("conftest.py", "test_sources.py", "test_environment.py", "test_replay.py")


def _file_pins(paths: tuple[str, ...]) -> list[dict[str, object]]:
    result = []
    for path in paths:
        body = regular_bytes(checkout_root() / path)
        result.append({"path": path, "sha256": sha256(body).hexdigest(), "size": len(body)})
    return result


def execution_spec(seed: int, threshold: int = 105) -> dict[str, Any]:
    require(type(seed) is int and 0 <= seed < 2**63, "INVALID_SEED")
    EligibleFeatureRule(threshold)
    return {
        "format": "RESEARCH_EXECUTION_MANIFEST_V0.1",
        "package": VERSION,
        "authority_baseline": BASELINE,
        "trace_format": "RESEARCH_TRACE_V0.1",
        "identity_scope": "Exact source bytes, research code/test bytes, config, seed, runtime",
        "source_pins": [{"path": p, "sha256": h, "size": n} for p, h, n in SOURCE_PINS],
        "code_pins": _file_pins(
            tuple("src/pit_research_lab/mvp/research_vslice/" + n for n in CODE_FILES)
        ),
        "test_pins": _file_pins(tuple("tests/unit/mvp_research_vslice/" + n for n in TEST_FILES)),
        "tests": {
            "required_stage_v_ids": list(STAGE_V_IDS),
            "execution_attestation": "NOT_ATTESTED_BY_RUNTIME",
            "deferred_stage_m": [
                {"id": i, "execution": "NOT_RUN", "result": "NOT_VERIFIED"} for i in STAGE_M_IDS
            ],
        },
        "runtime": {"python": sys.version, "implementation": platform.python_implementation()},
        "seed": seed,
        "agent_ids": list(AGENTS),
        "config": {
            "profile": "BOUNDED_SYN_A_FIXED_FOUR",
            "cutoffs": list(CUTOFFS),
            "publication_rule": "STRICT_ORIGINAL_PUBLICATION_LT_CUTOFF",
            "revision_order": "validated_chain_depth,publication,source,version,record",
            "rule_threshold": threshold,
            "actions": list(ACTIONS),
            "native_invocation": "NOT_RUN",
            "if03": False,
            "annotations": [{"iso_week": "2027-W03", "kind": "NO_SESSION_WEEK"}],
        },
    }


def run_episode(
    ledger: EventLedger, seed: int, agent_id: str, threshold: int = 105
) -> dict[str, Any]:
    require(agent_id in AGENTS, "UNKNOWN_AGENT")
    agent = NoDataBaseline(seed) if agent_id == AGENTS[0] else EligibleFeatureRule(threshold)
    env = ResearchEnvironment(ledger)
    observation = env.reset(seed, agent_id)
    rows = []
    while True:
        public = asdict(observation)
        # Convert immutable tuples to JSON arrays using explicit transport conversion.
        public["features"] = [asdict(f) for f in observation.features]
        action = agent.choose(observation)
        result = env.step(action)
        rows.append(
            {
                "tick_order": observation.tick_order,
                "cutoff": observation.cutoff,
                "observation": public,
                "observation_sha256": sha256(research_bytes(public)).hexdigest(),
                "availability_mask": [list(x) for x in observation.availability_mask],
                "transition": asdict(result.transition),
            }
        )
        if result.observation is None:
            break
        observation = result.observation
    return {"agent_id": agent_id, "ticks": rows, "terminal": True}


def execute(seed: int = 17, threshold: int = 105) -> tuple[bytes, dict[str, Any]]:
    # Load/validate originals before creating any trace or manifest that claims their pins.
    from .sources import load_pinned_synthetic_events

    ledger = load_pinned_synthetic_events()
    spec = execution_spec(seed, threshold)
    identity = sha256(research_bytes(spec)).hexdigest()
    trace = research_bytes(
        {
            "format": "RESEARCH_TRACE_V0.1",
            "non_if03": True,
            "execution_identity_sha256": identity,
            "episodes": [run_episode(ledger, seed, aid, threshold) for aid in AGENTS],
        }
    )
    manifest = {
        **spec,
        "execution_identity_sha256": identity,
        "trace_sha256": sha256(trace).hexdigest(),
        "trace_size": len(trace),
    }
    return trace, manifest
