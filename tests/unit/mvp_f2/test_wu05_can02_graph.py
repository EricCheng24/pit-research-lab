"""Exact frozen graph inputs through an explicit vocabulary-only adapter."""

import json
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from pit_research_lab.mvp.if03.canonical_codec import CodecRefusal
from pit_research_lab.mvp.if03.dependency_graph import (
    MAX_EDGES,
    MAX_GRAPH_DEPTH,
    MAX_NODES,
)
from pit_research_lab.mvp.if03.dependency_graph import (
    SymbolicEdge as Edge,
)
from pit_research_lab.mvp.if03.dependency_graph import (
    SymbolicNode as Node,
)
from pit_research_lab.mvp.if03.dependency_graph import (
    check_dependency_graph_symbolic as check,
)

ROOT = Path(__file__).resolve().parents[3]
CASES = json.loads((ROOT / "tests/fixtures/mvp_if03/wu05_oracle01_v0_1/cases.json").read_bytes())[
    "cases"
]
FROZEN_IDS = {"N-CYCLE", "N-HIDDEN-ATTEMPT", "N-DANGLING", "N-RESULT-ATTEMPT"}


def execute_frozen_case(case):
    """Translate exact ledger vocabulary/adjacency without inventing typed paths.

    SEMANTIC is an opaque symbolic intermediate, not an approved Resource Body.
    The private fields list is descriptive only; attempt kind suffices for the
    ancestry assertion. root is checked for membership; all supplied nodes run.
    No author reference-helper code is imported or executed by this adapter.
    """
    assert case["operation"] == "graph"
    inp = case["input"]
    assert set(inp) == {"nodes", "root"}
    assert inp["root"] in inp["nodes"]
    kinds = {
        "SEQUENCE": "TEMPORAL-SEQUENCE",
        "QUALIFICATION": "F2-QUALIFICATION",
        "SEMANTIC": "SEMANTIC_RESOURCE",
        "ATTEMPT": "F3-RUN-ATTEMPT",
        "RESULT": "RESULT",
        "EVIDENCE": "EVIDENCE",
    }
    nodes = []
    for name, row in inp["nodes"].items():
        assert set(row) in ({"kind", "parents"}, {"kind", "parents", "fields"})
        if "fields" in row:
            assert row["kind"] == "ATTEMPT" and row["fields"] == ["host", "clock", "token"]
        nodes.append(Node(name, kinds[row["kind"]], tuple(Edge(p) for p in row["parents"])))
    return check(tuple(nodes))


def refusal(code, nodes, category="STRUCTURALLY_INVALID"):
    with pytest.raises(CodecRefusal) as caught:
        check(nodes)
    assert (caught.value.category, caught.value.code) == (category, code)


@pytest.mark.parametrize(
    "case", [c for c in CASES if c["case_id"] in FROZEN_IDS], ids=lambda c: c["case_id"]
)
def test_exact_frozen_graph_refusals(case):
    with pytest.raises(CodecRefusal) as caught:
        execute_frozen_case(case)
    assert {"category": caught.value.category, "code": caught.value.code} == case["expected"]


def test_valid_supplied_one_way_edges_and_status():
    nodes = (
        Node("experiment", "F3-EXPERIMENT"),
        Node("result", "RESULT", (Edge("experiment", "experiment_ref"),)),
        Node(
            "attempt",
            "F3-RUN-ATTEMPT",
            (Edge("result", "result_ref.ref"), Edge("experiment", "experiment_ref")),
        ),
        Node(
            "evidence",
            "EVIDENCE",
            (Edge("result", "subject_ref"), Edge("attempt", "source_code_protocol_refs[]")),
        ),
    )
    result = check(nodes)
    assert result.structure == "STRUCTURE_VALID_SYMBOLIC_ONLY"
    assert result.node_count == 4 and result.edge_count == 5
    assert result.diagnostic_only is True and result.admission_eligible is False
    assert result.trust == "NOT_TRUSTED_PIT_EVIDENCE"
    assert result.source_authentication == "NOT_ESTABLISHED"
    assert result.disposition == "INTEGRATED_PROVISIONAL"
    assert "REAL_GRAPH_CLOSURE_NOT_SUPPLIED" in result.blockers
    with pytest.raises(FrozenInstanceError):
        result.structure = "REAL_CLOSURE"
    assert nodes[2].parents[0].target == "result"


def test_acyclic_evidence_reverse_and_indirect_reverse_refused():
    for kind in ("SOURCE-BYTES", "F2-QUALIFICATION", "RESULT", "TEMPORAL-SEQUENCE", "F5-DECISION"):
        refusal(
            "EVIDENCE_DIRECTION",
            (Node("subject", kind, (Edge("evidence"),)), Node("evidence", "EVIDENCE")),
        )
    refusal(
        "EVIDENCE_DIRECTION",
        (
            Node("subject", "RESULT", (Edge("trace"),)),
            Node("trace", "SEMANTIC_RESOURCE", (Edge("evidence"),)),
            Node("evidence", "EVIDENCE"),
        ),
    )


def test_attempt_reverse_indirect_and_provenance_cannot_launder():
    refusal(
        "ATTEMPT_ANCESTRY",
        (Node("r", "RESULT", (Edge("a", "experiment_ref"),)), Node("a", "F3-RUN-ATTEMPT")),
    )
    refusal(
        "ATTEMPT_ANCESTRY",
        (
            Node("q", "F2-QUALIFICATION", (Edge("t"),)),
            Node("t", "SEMANTIC_RESOURCE", (Edge("a"),)),
            Node("a", "F3-RUN-ATTEMPT"),
        ),
    )
    refusal(
        "FOREIGN_PARENT",
        (Node("e", "EVIDENCE", (Edge("a", "subject_ref"),)), Node("a", "F3-RUN-ATTEMPT")),
    )
    # A generic symbolic edge is explicitly not a claim of subject_ref conformance.
    assert (
        check((Node("e", "EVIDENCE", (Edge("a"),)), Node("a", "F3-RUN-ATTEMPT"))).structure
        == "STRUCTURE_VALID_SYMBOLIC_ONLY"
    )


def test_declared_typed_paths_resource_roles_and_mistaken_edges():
    valid = (
        Node("o", "F2-OBSERVATION", (Edge("q", "qualification_ref"),)),
        Node("q", "F2-QUALIFICATION"),
    )
    check(valid)
    refusal("FOREIGN_PARENT", (valid[0], Node("q", "SOURCE-BYTES")))
    refusal(
        "GRAPH_EDGE_ROLE", (Node("o", "F2-OBSERVATION", (Edge("q", "unexpected_ref"),)), valid[1])
    )
    check(
        (
            Node("x", "F3-EXPERIMENT", (Edge("p", "input_binding.single_cutoff_contract_ref"),)),
            Node("p", "RESOURCE:PROTOCOL"),
        )
    )
    refusal(
        "FOREIGN_PARENT",
        (
            Node("x", "F3-EXPERIMENT", (Edge("p", "input_binding.single_cutoff_contract_ref"),)),
            Node("p", "RESOURCE:EXPERIMENT_ASSOCIATION"),
        ),
    )
    refusal(
        "GRAPH_EDGE_ROLE",
        (
            Node("x", "F3-EXPERIMENT", (Edge("p", "association_instance_ref"),)),
            Node("p", "RESOURCE:EXPERIMENT_ASSOCIATION"),
        ),
    )
    refusal(
        "FOREIGN_PARENT",
        (Node("d", "F5-EVALUATION", (Edge("o", "outcome_refs[]"),)), Node("o", "RESOURCE:POLICY")),
    )
    refusal(
        "GRAPH_EDGE_ROLE",
        (Node("r", "RESOURCE:PROTOCOL", (Edge("b", "subject_ref"),)), Node("b", "SOURCE-BYTES")),
    )


def test_cycles_duplicate_and_dangling_even_disconnected():
    refusal("REF_CYCLE", (Node("x", "SEMANTIC_RESOURCE", (Edge("x"),)),))
    refusal(
        "REF_CYCLE",
        (
            Node("a", "RESULT"),
            Node("x", "SEMANTIC_RESOURCE", (Edge("y"),)),
            Node("y", "SEMANTIC_RESOURCE", (Edge("x"),)),
        ),
    )
    refusal("DUPLICATE_NODE", (Node("same", "RESULT"), Node("same", "RESULT")))
    refusal(
        "DANGLING_PARENT", (Node("r", "RESULT", (Edge("missing"),)),), "MISSING_REQUIRED_EVIDENCE"
    )


@pytest.mark.parametrize(
    "nodes,code",
    [
        (None, "GRAPH_NODE_BOUND"),
        ([], "GRAPH_NODE_BOUND"),
        ((), "GRAPH_NODE_BOUND"),
        (({},), "GRAPH_NODE_TYPE"),
        ((Node("x", "UNKNOWN"),), "GRAPH_NODE_KIND"),
        ((Node("x", "RESOURCE:UNKNOWN"),), "GRAPH_NODE_KIND"),
        ((Node("x", "RESULT", []),), "GRAPH_DEGREE_BOUND"),
        ((Node("x", "RESULT", ("wrong",)),), "GRAPH_EDGE_TYPE"),
        ((Node("x", "RESULT", (Edge([], "dependency"),)),), "TEXT_TYPE"),
        ((Node([], "RESULT"),), "TEXT_TYPE"),
        ((Node("x", []),), "TEXT_TYPE"),
    ],
)
def test_malformed_inputs_are_controlled_diagnostics(nodes, code):
    category = "UNSUPPORTED_SCHEMA" if code == "GRAPH_NODE_KIND" else "STRUCTURALLY_INVALID"
    refusal(code, nodes, category)


def test_wide_deep_and_high_degree_budget():
    refusal(
        "GRAPH_NODE_BOUND", tuple(Node(str(i), "SEMANTIC_RESOURCE") for i in range(MAX_NODES + 1))
    )
    refusal("GRAPH_DEGREE_BOUND", (Node("x", "RESULT", (Edge("x"),) * 4097),))
    refusal(
        "GRAPH_EDGE_BOUND",
        tuple(
            Node(str(i), "SEMANTIC_RESOURCE", (Edge("0"),) * 4096)
            for i in range(MAX_EDGES // 4096 + 1)
        ),
    )
    chain = tuple(
        Node(str(i), "SEMANTIC_RESOURCE", (Edge(str(i + 1)),) if i < MAX_GRAPH_DEPTH else ())
        for i in range(MAX_GRAPH_DEPTH + 1)
    )
    refusal("GRAPH_DEPTH_BOUND", chain)
    # Reverse input order still checks longest path, not just active DFS depth.
    refusal("GRAPH_DEPTH_BOUND", chain[::-1])
    shallow = tuple(Node(str(i), "SEMANTIC_RESOURCE") for i in range(MAX_NODES))
    assert check(shallow).node_count == MAX_NODES


def test_conflicting_singular_experiment_union_branches():
    refusal(
        "GRAPH_UNION_BRANCH",
        (
            Node(
                "x",
                "F3-EXPERIMENT",
                (
                    Edge("s", "input_binding.temporal_binding_set_ref"),
                    Edge("o", "input_binding.observation_ref"),
                ),
            ),
            Node("s", "TEMPORAL-SEQUENCE"),
            Node("o", "F2-OBSERVATION"),
        ),
    )
