"""Registry navigation against contract literals, without positive domain claims."""

import json
import re
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from pit_research_lab.mvp.if03 import canonical_codec as codec
from pit_research_lab.mvp.if03.domain_registry import (
    DOMAIN_REGISTRY,
    RESOURCE_ROLES,
    lookup_domain,
)

ROOT = Path(__file__).resolve().parents[3]
CONTRACT = (ROOT / "docs/mvp/v1.0/shared-interface-contract-v0.1.md").read_text()
COVERAGE = json.loads(
    (ROOT / "tests/fixtures/mvp_if03/wu05_oracle01_v0_1/domain_coverage.json").read_bytes()
)
NAMES = (
    "SOURCE-BYTES",
    "F2-QUALIFICATION",
    "F2-OBSERVATION",
    "TEMPORAL-SEQUENCE",
    "F3-EXPERIMENT",
    "F3-RUN-ATTEMPT",
    "RESULT",
    "EVIDENCE",
    "F5-DECISION",
    "F5-EVALUATION",
)


@pytest.mark.parametrize("name", NAMES)
def test_exact_ratified_fields_tags_versions_and_navigation(name):
    desc = lookup_domain(name)
    row = next(d for d in COVERAGE["domains"] if d["domain"] == name)
    assert tuple(DOMAIN_REGISTRY) == tuple(codec.DOMAINS) == NAMES
    assert desc.object_schema_version == name.lower() + "-candidate-v0.1" == codec.DOMAINS[name]
    assert desc.domain_tag == f"PITLAB/ACADEMIC/{name}/candidate-v0.1"
    assert desc.canonical_profile_version == "typed-json-candidate-v0.1"
    # Parse only the contract's exact top-level table cells (no runtime fixture authority).
    cell = next(line for line in CONTRACT.splitlines() if line.startswith(f"| {name};"))
    fields = re.findall(r"(?:^|; )([a-z_][a-z_0-9]*):", cell.split(" | ")[1])
    assert desc.semantic_fields == ("canonical_profile_version", *fields)
    assert list(desc.semantic_fields) == row["semantic_fields"]
    assert set(desc.resource_navigation) == set(row["required_resource_roles"])
    assert desc.scoped_complete_positive is (name == "SOURCE-BYTES")
    assert desc.issuable is False
    assert desc.resource_semantics == "RESOURCE_SEMANTICS_NOT_SUPPLIED"
    for role in desc.references:
        assert set(role.parent_domains) <= set(NAMES)
        assert set(role.resource_roles) <= RESOURCE_ROLES


def test_roles_are_closed_immutable_and_not_primary_domains():
    line = next(
        s for s in CONTRACT.splitlines() if s.startswith("Registered ResourceRef role literals:")
    )
    assert RESOURCE_ROLES == frozenset(re.findall(r"`([A-Z_]+)`", line))
    with pytest.raises(TypeError):
        DOMAIN_REGISTRY["NEW"] = lookup_domain("RESULT")
    with pytest.raises(FrozenInstanceError):
        lookup_domain("RESULT").issuable = True
    for unknown in ("result", "RESULT ", "PROTOCOL", "RESOURCE", "", None, []):
        with pytest.raises(codec.CodecRefusal):
            lookup_domain(unknown)


def test_transitive_notes_and_conditional_union_not_narrowed():
    seq = lookup_domain("TEMPORAL-SEQUENCE")
    assert {"ORIGIN", "TIMEZONE_RULES"} <= set(seq.resource_navigation)
    evidence = next(
        r for r in lookup_domain("EVIDENCE").references if r.path == "source_code_protocol_refs[]"
    )
    assert set(evidence.parent_domains) == set(NAMES) - {"EVIDENCE"}
    assert set(evidence.resource_roles) == RESOURCE_ROLES
    assert "conditional" in evidence.condition
    experiment = lookup_domain("F3-EXPERIMENT")
    assert all("association_instance" not in r.path for r in experiment.references)


@pytest.mark.parametrize("name", NAMES[1:])
def test_registry_does_not_change_can01_positive_gate(name):
    d = lookup_domain(name)
    with pytest.raises(codec.CodecRefusal, match="NOT_SUPPLIED / UNSUPPORTED_SEMANTIC_SCHEMA"):
        codec.require_candidate_domain(d.domain_tag, d.object_schema_version)
