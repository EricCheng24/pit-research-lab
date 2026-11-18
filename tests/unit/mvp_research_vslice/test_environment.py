"""Public-object traversal and actions, with independent literal episode oracles."""

from dataclasses import FrozenInstanceError, fields, is_dataclass

import pytest

from pit_research_lab.mvp.research_vslice.agents import EligibleFeatureRule, NoDataBaseline
from pit_research_lab.mvp.research_vslice.contracts import AGENTS, CUTOFFS, ResearchError
from pit_research_lab.mvp.research_vslice.environment import ResearchEnvironment
from pit_research_lab.mvp.research_vslice.sources import load_pinned_synthetic_events


def walk_public(value):
    if is_dataclass(value):
        assert not hasattr(value, "__dict__")
        for f in fields(value):
            yield f.name
            yield from walk_public(getattr(value, f.name))
    elif type(value) is tuple:
        for child in value:
            yield from walk_public(child)
    else:
        assert value is None or type(value) in (str, int, bool)
        yield str(value)


def test_RC02_T02_no_future_reward_label_observable():
    env = ResearchEnvironment()
    observation = env.reset(17, AGENTS[0])
    for i in range(4):
        text = "|".join(walk_public(observation)) + repr(observation)
        for forbidden in [
            "payload_bytes",
            "endpoint_facts",
            "price",
            "reward",
            "label",
            "native_result",
            "attempt_token",
            "audit",
            "raw_bytes",
            "raw_descriptor",
            "historical_lead",
            "source_text_ref",
        ]:
            assert forbidden not in text
        if i < 3:
            assert "PREP01-CV-D3" not in text
            assert "PREP01-A-N23" not in text
            assert "2027-01-29T18:00:01+08:00" not in text
        if i == 0:
            assert "PREP01-CV-D2" not in text and "PREP01-A-N12" not in text
        observation = env.step("HOLD").observation


def test_RC03_T01_fixed_four_ticks_annotation_only():
    env = ResearchEnvironment()
    obs = env.reset(17, AGENTS[0])
    actual = []
    while obs is not None:
        actual.append((obs.tick_order, obs.cutoff))
        obs = env.step("HOLD").observation
    assert actual == [
        (0, "2027-01-07T18:00:00+08:00"),
        (1, "2027-01-15T18:00:00+08:00"),
        (2, "2027-01-29T18:00:00+08:00"),
        (3, "2027-02-05T18:00:00+08:00"),
    ]
    assert [t.disposition for t in env.transitions()] == ["ADVANCED"] * 3 + ["TERMINATED"]
    assert [t.terminal for t in env.transitions()] == [False, False, False, True]
    for method in [env.observe, lambda: env.step("HOLD")]:
        with pytest.raises(ResearchError, match="EPISODE_NOT_ACTIVE"):
            method()
    assert len(env.transitions()) == 4


def test_RC03_T02_no_public_future_access_or_mutation():
    env = ResearchEnvironment()
    original = env.reset(17, AGENTS[1])
    assert not hasattr(env, "__dict__")
    assert repr(env) == "ResearchEnvironment(RESEARCH_VSLICE_V0.1)"
    for name in [
        "next",
        "future",
        "ledger",
        "events",
        "payload_bytes",
        "__dict__",
        "source_payload",
    ]:
        assert not hasattr(original, name)
        with pytest.raises(AttributeError):
            getattr(original, name)
    with pytest.raises(TypeError):
        iter(original)
    with pytest.raises(TypeError):
        env.observe(CUTOFFS[3])
    with pytest.raises(FrozenInstanceError):
        original.tick_order = 3
    with pytest.raises(FrozenInstanceError):
        original.features[0].value = 999
    with pytest.raises(FrozenInstanceError):
        original.features[0].provenance.publication = CUTOFFS[3]
    with pytest.raises(TypeError):
        original.features[0] = None
    # Even explicitly bypassing frozen assignment on a public value changes no engine fact.
    corrupted = env.observe()
    object.__setattr__(corrupted.features[0], "value", 999)
    object.__setattr__(corrupted.features[0].provenance, "publication", CUTOFFS[3])
    assert env.observe() == original
    assert env.step("OBSERVE_NEXT").transition.disposition == "REFUSED_INVALID_ACTION"
    assert env.observe() == original
    next_obs = env.step("HOLD").observation
    assert next_obs.tick_order == 1
    assert original.tick_order == 0 and original.features[0].value == 100
    assert next_obs.features[0].value == 110


def test_RC03_T03_invalid_actions_independent_episodes():
    shared = load_pinned_synthetic_events()
    left, right = ResearchEnvironment(shared), ResearchEnvironment(shared)
    first = left.reset(17, AGENTS[0])
    assert right.reset(17, AGENTS[1]) == first
    for bad in ["SELL", "", "hold", "next", -1, 0, None, True, [], {}, object()]:
        refused = left.step(bad)
        assert refused.observation == first
        assert refused.transition.disposition == "REFUSED_INVALID_ACTION"
        assert refused.transition.action is None
        assert refused.transition.next_tick_order == 0
        assert not refused.transition.terminal
    left.step("HOLD")
    assert right.observe() == first
    assert right.transitions() == ()
    assert left.reset(18, AGENTS[1]) == first
    assert left.transitions() == ()
    assert first.features[0].value == 100
    for seed, agent in [(-1, AGENTS[0]), (True, AGENTS[0]), (17, "unknown")]:
        with pytest.raises(ResearchError):
            left.reset(seed, agent)


def test_RC05_T01_identical_information_two_distinct_agents():
    left, right = ResearchEnvironment(), ResearchEnvironment()
    baseline, comparator = NoDataBaseline(17), EligibleFeatureRule(105)
    a, b = left.reset(17, baseline.agent_id), right.reset(17, comparator.agent_id)
    decisions = []
    for _ in range(4):
        assert a == b and a is not b
        assert a.availability_mask == b.availability_mask
        assert a.cutoff == b.cutoff
        ac, bc = baseline.choose(a), comparator.choose(b)
        decisions.append((ac, bc))
        a, b = left.step(ac).observation, right.step(bc).observation
    assert decisions == [
        ("HOLD", "HOLD"),
        ("HOLD", "FLAG_REVIEW"),
        ("HOLD", "FLAG_REVIEW"),
        ("HOLD", "HOLD"),
    ]
    assert a is b is None
