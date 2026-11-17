"""Pure bounded symbolic dependency diagnostics; no real graph closure claim.

Edges point from a supplied object to its named dependency. `dependency` records
only symbolic adjacency (no declared-field conformance). Other relations must be
exact registry paths and have a provable supplied parent/resource kind. A valid
supplied graph establishes no payload, historical identity, rights or source.
"""

from dataclasses import dataclass, field
from typing import Literal

from .canonical_codec import DOMAINS, CodecRefusal, TextSchema, _text
from .domain_registry import RESOURCE_ROLES, lookup_domain
from .typed_references import DiagnosticScope

MAX_NODES = 4096
MAX_EDGES = 16384
MAX_DEGREE = 4096
MAX_GRAPH_DEPTH = 128  # local symbolic safety budget, NOT IF-03 record depth


@dataclass(frozen=True, slots=True)
class SymbolicEdge:
    target: str
    relation: str = "dependency"


@dataclass(frozen=True, slots=True)
class SymbolicNode:
    node_id: str
    kind: str  # registered domain, RESOURCE:<registered role>, or SEMANTIC_RESOURCE
    parents: tuple[SymbolicEdge, ...] = ()


@dataclass(frozen=True, slots=True)
class SymbolicGraphInspection(DiagnosticScope):
    node_count: int = 0
    edge_count: int = 0
    structure: Literal["STRUCTURE_VALID_SYMBOLIC_ONLY"] = field(
        default="STRUCTURE_VALID_SYMBOLIC_ONLY", init=False
    )
    semantics: Literal["BLOCKED_NOT_SUPPLIED"] = field(default="BLOCKED_NOT_SUPPLIED", init=False)
    blockers: tuple[str, ...] = field(
        default=("REAL_GRAPH_CLOSURE_NOT_SUPPLIED", "RESOURCE_BYTES_SCHEMA_RIGHTS_NOT_SUPPLIED"),
        init=False,
    )


def _identifier(value: object) -> str:
    return _text(value, TextSchema(min_bytes=1, max_bytes=128))


def _valid_kind(kind: str) -> bool:
    return (
        kind in DOMAINS
        or kind == "SEMANTIC_RESOURCE"
        or (kind.startswith("RESOURCE:") and kind[9:] in RESOURCE_ROLES)
    )


def check_dependency_graph_symbolic(nodes: object) -> SymbolicGraphInspection:
    """Check all supplied nodes, including disconnected components; iterative O(V+E).

    No required real-world edges are inferred from their absence. A `dependency`
    edge asserts adjacency only. Declared edges additionally check the registry's
    field path and conditional parent/resource domain alternatives. Graph safety
    depth is independent of the unresolved normative record-depth boundary.
    """
    if type(nodes) is not tuple or not 1 <= len(nodes) <= MAX_NODES:
        raise CodecRefusal("GRAPH_NODE_BOUND")
    by_id: dict[str, SymbolicNode] = {}
    edge_count = 0
    for node in nodes:
        if type(node) is not SymbolicNode:
            raise CodecRefusal("GRAPH_NODE_TYPE")
        _identifier(node.node_id)
        _identifier(node.kind)
        if not _valid_kind(node.kind):
            raise CodecRefusal("GRAPH_NODE_KIND", "UNSUPPORTED_SCHEMA")
        if node.node_id in by_id:
            raise CodecRefusal("DUPLICATE_NODE")
        if type(node.parents) is not tuple or len(node.parents) > MAX_DEGREE:
            raise CodecRefusal("GRAPH_DEGREE_BOUND")
        edge_count += len(node.parents)
        if edge_count > MAX_EDGES:
            raise CodecRefusal("GRAPH_EDGE_BOUND")
        by_id[node.node_id] = node
        for edge in node.parents:
            if type(edge) is not SymbolicEdge:
                raise CodecRefusal("GRAPH_EDGE_TYPE")
            _identifier(edge.target)
            _identifier(edge.relation)
    for node in by_id.values():
        # Singular ExperimentInput paths select mutually exclusive branches.
        # Array-member paths may select different branches for different members.
        paths = {e.relation for e in node.parents}
        if (
            node.kind == "F3-EXPERIMENT"
            and "input_binding.temporal_binding_set_ref" in paths
            and paths
            & {"input_binding.observation_ref", "input_binding.single_cutoff_contract_ref"}
        ):
            raise CodecRefusal("GRAPH_UNION_BRANCH")
        for edge in node.parents:
            if edge.target not in by_id:
                raise CodecRefusal("DANGLING_PARENT", "MISSING_REQUIRED_EVIDENCE")

    # Iterative DFS; postorder supports longest-path and ancestry DP below.
    state: dict[str, int] = {}
    order: list[str] = []
    for start in by_id:
        if start in state:
            continue
        state[start] = 1
        stack = [(start, 0)]
        while stack:
            name, index = stack[-1]
            edges = by_id[name].parents
            if index == len(edges):
                state[name] = 2
                order.append(name)
                stack.pop()
                continue
            stack[-1] = (name, index + 1)
            target = edges[index].target
            if state.get(target) == 1:
                raise CodecRefusal("REF_CYCLE")
            if target not in state:
                state[target] = 1
                stack.append((target, 0))
                if len(stack) > MAX_GRAPH_DEPTH:
                    raise CodecRefusal("GRAPH_DEPTH_BOUND")
    depths: dict[str, int] = {}
    has_attempt: dict[str, bool] = {}
    has_evidence: dict[str, bool] = {}
    for name in order:
        node = by_id[name]
        depths[name] = 1 + max((depths[e.target] for e in node.parents), default=0)
        if depths[name] > MAX_GRAPH_DEPTH:
            raise CodecRefusal("GRAPH_DEPTH_BOUND")
        has_attempt[name] = node.kind == "F3-RUN-ATTEMPT" or any(
            has_attempt[e.target] for e in node.parents
        )
        has_evidence[name] = node.kind == "EVIDENCE" or any(
            has_evidence[e.target] for e in node.parents
        )
        if node.kind in DOMAINS and node.kind not in ("F3-RUN-ATTEMPT", "EVIDENCE"):
            if has_attempt[name]:
                raise CodecRefusal("ATTEMPT_ANCESTRY")
            if has_evidence[name]:
                raise CodecRefusal("EVIDENCE_DIRECTION")
    for node in by_id.values():
        for edge in node.parents:
            if edge.relation == "dependency":
                continue
            if node.kind not in DOMAINS:
                raise CodecRefusal("GRAPH_EDGE_ROLE")
            declared = next(
                (r for r in lookup_domain(node.kind).references if r.path == edge.relation), None
            )
            if declared is None:
                raise CodecRefusal("GRAPH_EDGE_ROLE")
            target_kind = by_id[edge.target].kind
            allowed = declared.parent_domains + tuple(
                "RESOURCE:" + r for r in declared.resource_roles
            )
            if target_kind not in allowed:
                raise CodecRefusal("FOREIGN_PARENT")
    return SymbolicGraphInspection(node_count=len(by_id), edge_count=edge_count)
