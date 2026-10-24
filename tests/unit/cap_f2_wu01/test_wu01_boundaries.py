"""ENGINEERING_TEST: physical imports, resource denial, source integrity and immutability."""

import ast
import hashlib
import json
import subprocess
import sys
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest
from wu01_actual import ActualInputAssociation, observe_actual, project
from wu01_inputs import CALLER, NA, AdaptedS1Input, InvocationSelector, adapt, materialize

from pit_research_lab.domain.contracts import (
    SCHEMA,
    BlockingFailure,
    CandidateProfile,
    CodePin,
    ContentInventoryRequest,
    ContractError,
    Known,
    SubjectComparisonRequest,
    Unknown,
    UnknownCause,
    Visibility,
)
from pit_research_lab.domain.information import assess_evidence, compare_subjects, inventory_content

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).parent
A, U = Visibility.ACTIVE, Visibility.AUXILIARY
DRIVERS = (
    (
        "A01-C01",
        InvocationSelector("COMPARE_SUBJECTS", ("A-APR-NTD-A01-C01", "SUB-A-APR"), NA, (A,)),
    ),
    (
        "A01-C02",
        InvocationSelector(
            "COMPARE_SUBJECTS", ("A-H1-A01-C02", "A-Q2-REPORTED-A01-C02"), NA, (A, U)
        ),
    ),
    ("A01-C03", InvocationSelector("COMPARE_SUBJECTS", ("A-JUN-01", "A-JUN-PEER"), NA, (A, U))),
    (
        "A01-C04",
        InvocationSelector("COMPARE_SUBJECTS", ("A-JUN-01", "A-JUN-SCOPE-A01-C04"), NA, (A, U)),
    ),
    ("A02-C01", InvocationSelector("CHECK_BINDING", ("A-JUN-01",), "SUP-JUN1-PUB", (A,))),
    ("A02-C02", InvocationSelector("CHECK_BINDING", ("A-JUN-02",), "SUP-JUN1-PUB", (A, U))),
    ("A02-C03", InvocationSelector("INVENTORY_CONTENT", ("A-JUN-01", "CV-JUN-01"), NA, (A,))),
    ("A02-C04", InvocationSelector("CHECK_BINDING", ("OBS-P-X-A02-C04",), NA, (A, U))),
)


def profile():
    paths = (
        "src/pit_research_lab/domain/contracts.py",
        "src/pit_research_lab/domain/information.py",
        "tests/unit/cap_f2_wu01/wu01_actual.py",
    )
    pins = tuple(CodePin(p, hashlib.sha256((ROOT / p).read_bytes()).hexdigest()) for p in paths)
    return CandidateProfile(
        SCHEMA,
        "wu01-unit-v0.1-CANDIDATE",
        "wu01-reasons-v0.1-CANDIDATE",
        "s1-information-v0.1-CANDIDATE",
        pins,
        CALLER,
    )


def run(bundle):
    if isinstance(bundle.request, SubjectComparisonRequest):
        return compare_subjects(bundle.context, bundle.request)
    if isinstance(bundle.request, ContentInventoryRequest):
        return inventory_content(bundle.context, bundle.request)
    return assess_evidence(bundle.context, bundle.request)


def association(bundle):
    c = bundle.context
    return ActualInputAssociation(
        bundle.selector.operation,
        c.context_ref,
        c.target_ref,
        bundle.selector.concrete_targets,
        c.mode,
        c.information_cutoff.source_text,
        bundle.request,
        bundle.source_members,
        bundle.source_captures,
        bundle.source_events,
        bundle.source_assertion_refs,
        bundle.source_attempt_refs,
    )


@pytest.mark.parametrize("case,selector", DRIVERS)
def test_boundary_each_adaptation_is_immutable_repeatable_and_source_preserving(case, selector):
    envelope = materialize(case)
    before = json.dumps(envelope, sort_keys=True)
    bundle = adapt(envelope, selector, profile())
    assert isinstance(bundle, AdaptedS1Input), bundle
    actual = run(bundle)
    assert not isinstance(actual, BlockingFailure), actual
    assert run(bundle) == actual
    assert adapt(envelope, selector, profile()) == bundle
    assert json.dumps(envelope, sort_keys=True) == before
    with pytest.raises(FrozenInstanceError):
        bundle.context.mode = "altered"
    with pytest.raises(ContractError):
        replace(bundle.request.scope, input_members=list(bundle.source_members))
    envelope["request"]["mode"] = "altered"
    assert bundle.context.mode == "public" and run(bundle) == actual
    a = association(bundle)
    projected = project(actual, a, (observe_actual(actual, a),))
    assert projected.system_outcome == actual
    with pytest.raises(ContractError, match="MISSING_PROBE_COVERAGE"):
        project(actual, a, ())


@pytest.mark.parametrize(
    "fault",
    ["hash", "same_id_new_bytes", "bool_amount", "outer_key", "unknown_schema", "duplicate_member"],
)
def test_boundary_structural_integrity_faults_are_blocking(fault):
    case, selector = DRIVERS[4]
    envelope = materialize(case)
    view = envelope["active_discovery_membership"]["facts"]
    raw = view["raw_assets"]["REP-RAW-CV-JUN-01"]
    if fault == "hash":
        raw["sha256"] = "0" * 64
    elif fault == "same_id_new_bytes":
        raw["payload"] = raw["payload"].replace('"value":300', '"value":310')
        raw["sha256"] = hashlib.sha256(raw["payload"].encode()).hexdigest()
    elif fault == "bool_amount":
        view["assertions"]["A-JUN-01"]["value"] = True
    elif fault == "outer_key":
        del envelope["request"]
    elif fault == "unknown_schema":
        envelope["unexpected"] = True
    else:
        envelope["active_discovery_membership"]["receipts"].append(
            envelope["active_discovery_membership"]["receipts"][0]
        )
    actual = adapt(envelope, selector, profile())
    assert isinstance(actual, BlockingFailure) and actual.category == "CONTRACT_VIOLATION"


def test_boundary_missing_origin_and_mixed_unknown_precedence_are_not_hidden():
    case, selector = DRIVERS[3]
    bundle = adapt(materialize(case), selector, profile())
    assert isinstance(bundle.request.right.subject.reporting_scope, Unknown)
    with pytest.raises(ContractError):
        Known("value", None)
    with pytest.raises(ContractError):
        Unknown(UnknownCause.ABSENT_SOURCE_FIELD, None, None)
    with pytest.raises(ContractError, match="MISSING_ORIGIN"):
        replace(bundle.request.right.subject, origin=None)
    with pytest.raises(ContractError, match="UNSUPPORTED_PROFILE"):
        replace(profile(), evaluator_ref="invented-approved-evaluator")
    r = bundle.request
    right = replace(r.right, subject=replace(r.right.subject, metric=Known("OTHER", CALLER)))
    actual = compare_subjects(bundle.context, replace(r, right=right))
    assert isinstance(actual, BlockingFailure) and actual.code == "UNSUPPORTED_SEMANTIC_COMBINATION"


def test_boundary_import_graph_and_no_case_driven_semantics():
    domain = ROOT / "src/pit_research_lab/domain"
    paths = (
        domain / "contracts.py",
        domain / "information.py",
        HERE / "wu01_actual.py",
        HERE / "wu01_inputs.py",
    )
    for path in paths:
        tree = ast.parse(path.read_text())
        imports = [n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
        imports += [a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names]
        assert not any(
            any(
                bad in name
                for bad in (
                    "wu00_oracle",
                    "wu00_compare",
                    "wu00_evidence",
                    "wu01_bindings",
                    "wu01_acceptance",
                    "sqlalchemy",
                    "psycopg",
                    "socket",
                    "requests",
                    "urllib",
                )
            )
            for name in imports
        )
        if path.parent == domain or path.name == "wu01_actual.py":
            assert not any("wu00_inputs" in name or "wu01_inputs" in name for name in imports)
            assert not any(name in {"pathlib", "os", "subprocess", "importlib"} for name in imports)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                assert node.func.attr not in {"now", "today", "load_catalogue", "_read", "_view"}
            if isinstance(node, (ast.If, ast.IfExp, ast.Match)):
                decision = node.subject if isinstance(node, ast.Match) else node.test
                assert not any(
                    isinstance(n, ast.Name) and n.id == "case_id" for n in ast.walk(decision)
                )
    assert (domain / "__init__.py").read_bytes() == b""
    assert not (HERE / "__init__.py").exists()
    # Phase A now authorizes the S2 owner; all S1/Oracle/purity checks above remain.
    assert (domain / "temporal.py").is_file()


def test_boundary_real_s1_and_actual_with_prohibited_resources_unavailable():
    script = r"""
import sys, importlib.util, hashlib, json
from pathlib import Path
root = Path(sys.argv[1])
denied = []
opened_inputs = []
def audit(event, args):
    if event.startswith('socket.'):
        raise PermissionError('network denied')
    if event == 'import' and any(word in str(args[0]) for word in (
        'wu00_oracle', 'wu00_compare', 'wu00_evidence', 'wu01_bindings', 'wu01_acceptance')):
        denied.append('import')
        raise PermissionError('prohibited import')
    if event == 'open' and isinstance(args[0], (str, bytes)):
        name = str(args[0])
        if any(word in name for word in ('data/oracle', 'data/sources', 'wu01_bindings',
                                         'wu01_acceptance', 'approval-root', 'wu00_oracle')):
            denied.append('resource')
            raise PermissionError('prohibited resource')
        if 'data/inputs/' in name:
            opened_inputs.append(Path(name).name)
sys.addaudithook(audit)
for name in ('wu01_inputs', 'wu01_actual'):
    spec = importlib.util.spec_from_file_location(name, root/'tests/unit/cap_f2_wu01'/f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
from wu01_inputs import CALLER, NA, InvocationSelector, materialize_input
from wu01_actual import ActualInputAssociation, observe_actual, project
from pit_research_lab.domain.contracts import SCHEMA, CandidateProfile, CodePin, Visibility
from pit_research_lab.domain.information import compare_subjects, assess_evidence
pins = tuple(CodePin(p, hashlib.sha256((root/p).read_bytes()).hexdigest()) for p in (
    'src/pit_research_lab/domain/contracts.py', 'src/pit_research_lab/domain/information.py',
    'tests/unit/cap_f2_wu01/wu01_actual.py'))
profile = CandidateProfile(SCHEMA, 'wu01-unit-v0.1-CANDIDATE', 'wu01-reasons-v0.1-CANDIDATE',
                           's1-information-v0.1-CANDIDATE', pins, CALLER)
selector = InvocationSelector('COMPARE_SUBJECTS', ('A-APR-NTD-A01-C01','SUB-A-APR'), NA,
                              (Visibility.ACTIVE,))
b = materialize_input('A01-C01', selector, profile)
out = compare_subjects(b.context, b.request)
c = b.context
a = ActualInputAssociation(selector.operation, c.context_ref, c.target_ref, selector.concrete_targets,
    c.mode, c.information_cutoff.source_text, b.request, b.source_members, b.source_captures,
    b.source_events, b.source_assertion_refs, b.source_attempt_refs)
projected = project(out, a, (observe_actual(out, a),))
assert projected.system_outcome.canonical_amount.value == 100
assert out.state == 'SAME'
provider_selector = InvocationSelector('CHECK_BINDING', ('OBS-P-X-A02-C04',), NA,
                                       (Visibility.ACTIVE, Visibility.AUXILIARY))
pb = materialize_input('A02-C04', provider_selector, profile)
provider = assess_evidence(pb.context, pb.request)
pc = pb.context
pa = ActualInputAssociation(provider_selector.operation, pc.context_ref, pc.target_ref,
    provider_selector.concrete_targets, pc.mode, pc.information_cutoff.source_text,
    pb.request, pb.source_members, pb.source_captures, pb.source_events,
    pb.source_assertion_refs, pb.source_attempt_refs)
assert project(provider, pa, (observe_actual(provider, pa),)).system_outcome == provider
assert provider.reason == 'ATTRIBUTION_UNRESOLVED'
assert len(provider.provenance.accepted_paths) == 1
assert provider.provenance.accepted_paths[0].path_role == 'CAPTURE_ONLY'
for p in (root/'tests/unit/cap_f2_wu00/data/oracle/cases.json', root/'approval-root'):
    try: p.read_bytes()
    except PermissionError: pass
    else: raise AssertionError('resource guard inactive')
try: __import__('wu01_bindings')
except PermissionError: pass
else: raise AssertionError('import guard inactive')
assert len(denied) == 3
assert set(opened_inputs) == {'base.json','contexts.json','deltas.json'}
assert all(name not in sys.modules for name in ('wu01_bindings','wu01_acceptance','wu00_oracle'))
print(json.dumps({'real_s1':'SAME','canonical_int':100,'projected':True,'provider_projected':True,'denial_controls':len(denied),
                  'input_resources':sorted(set(opened_inputs))}))
"""
    result = subprocess.run(
        [sys.executable, "-I", "-B", "-c", script, str(ROOT)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    receipt = json.loads(result.stdout)
    assert receipt["denial_controls"] == 3 and receipt["projected"] is True
    assert receipt["provider_projected"] is True
    assert receipt["real_s1"] == "SAME" and receipt["canonical_int"] == 100


@pytest.mark.parametrize("fault", ["erase_all", "omit_one", "duplicate", "path_role"])
def test_ir04_identity_projection_requires_source_path_multiset(fault):
    case, selector = DRIVERS[2]
    bundle = adapt(materialize(case), selector, profile())
    actual = run(bundle)
    paths = actual.provenance.accepted_paths
    if fault == "erase_all":
        paths = ()
    elif fault == "omit_one":
        paths = paths[:1]
    elif fault == "duplicate":
        paths = (*paths, paths[0])
    else:
        paths = (replace(paths[0], path_role="CAPTURE_ONLY"), *paths[1:])
    # Make exclusion accounting internally consistent and generate a fresh probe.
    # Neither is proof that required source-owned identity paths are present.
    used = set()
    for path in paths:
        pairs = (
            ("assertions", path.target.target_ref),
            ("content_versions", path.target.content_version_ref),
            ("raw_assets", path.target.representation_ref),
            ("supports", path.support_ref),
            ("evidence", path.evidence_ref),
            ("publication_events", path.event_ref),
            ("time_proofs", path.time_proof_ref),
            *(("subjects", ref) for ref in path.target.subject_scope_refs),
        )
        used.update(
            (path.visibility.value, role, ref) for role, ref in pairs if isinstance(ref, str)
        )
    provenance = replace(
        actual.provenance,
        accepted_paths=paths,
        excluded_uses=tuple(m for m in bundle.source_members if m.key not in used),
    )
    changed = replace(actual, provenance=provenance)
    a = association(bundle)
    probe = observe_actual(changed, a)
    assert probe.accepted_paths == paths
    with pytest.raises(ContractError, match="IDENTITY_PATH_COVERAGE_MISMATCH"):
        project(changed, a, (probe,))


@pytest.mark.parametrize("selector", [None, "CHECK_BINDING", object()])
def test_ir05_invalid_selector_returns_typed_contract_failure(selector):
    result = adapt(materialize("A02-C01"), selector, profile())
    assert isinstance(result, BlockingFailure)
    assert (result.category, result.code, result.attempted_operation) == (
        "CONTRACT_VIOLATION",
        "UNSUPPORTED_SELECTOR",
        "ADAPT_INPUT",
    )


def test_ir05_valid_selector_preserves_source_failure_operation():
    case, selector = DRIVERS[4]
    envelope = materialize(case)
    del envelope["request"]
    result = adapt(envelope, selector, profile())
    assert isinstance(result, BlockingFailure)
    assert (result.category, result.code, result.attempted_operation) == (
        "CONTRACT_VIOLATION",
        "MATERIALIZED_OUTER_SCHEMA",
        "CHECK_BINDING",
    )


@pytest.mark.parametrize("role", ["assertions", "subjects", "content_versions"])
def test_r2_ir04_actual_projection_cannot_accept_undeclared_members(role):
    case, selector = DRIVERS[4]
    bundle = adapt(materialize(case), selector, profile())
    actual = run(bundle)
    r = bundle.request
    ref = {
        "assertions": r.requested.target_ref,
        "subjects": r.requested.subject_scope_refs[0],
        "content_versions": r.requested.content_version_ref,
    }[role]
    members = tuple(m for m in bundle.source_members if m.key != (A, role, ref))
    request = replace(r, scope=replace(r.scope, input_members=members))
    a = replace(association(bundle), input_request=request, input_members=members)
    projected_input = replace(
        actual,
        provenance=replace(
            actual.provenance,
            input_members=members,
            excluded_uses=tuple(m for m in actual.provenance.excluded_uses if m in members),
        ),
    )
    probe = observe_actual(projected_input, a)
    with pytest.raises(ContractError, match="UNOBSERVED_ACCEPTED_PATH"):
        project(projected_input, a, (probe,))


@pytest.mark.parametrize("nested", ["event", "proof"])
def test_r2_inv3_actual_only_boundary_checks_nested_origin(nested):
    case, selector = DRIVERS[4]
    bundle = adapt(materialize(case), selector, profile())
    actual = run(bundle)
    r = bundle.request
    binding = r.attempts[0].supplied
    value = binding.event if nested == "event" else binding.proof_candidate
    changed_value = replace(value, origin=replace(value.origin, visibility=Visibility.DEPENDENCY))
    changed = replace(
        binding, **{"event" if nested == "event" else "proof_candidate": changed_value}
    )
    request = replace(r, attempts=(replace(r.attempts[0], supplied=changed),))
    a = replace(association(bundle), input_request=request)
    outcome = replace(
        actual,
        supplied_bindings=(changed,),
        assessments=(replace(actual.assessments[0], supplied=changed),),
    )
    if nested == "event":
        events = tuple(
            changed_value if e.event_ref == value.event_ref else e for e in a.source_events
        )
        a = replace(a, source_events=events)
        outcome = replace(outcome, publication_event_facts=(changed_value,))
    with pytest.raises(ContractError, match="UNOBSERVED_ACCEPTED_PATH"):
        project(outcome, a, (observe_actual(outcome, a),))


def test_r2_inv4_duplicate_scope_member_is_not_silently_deduplicated():
    case, selector = DRIVERS[4]
    bundle = adapt(materialize(case), selector, profile())
    scope = bundle.request.scope
    with pytest.raises(ContractError, match="DUPLICATE_MEMBER_IDENTITY"):
        replace(
            scope,
            input_members=tuple(
                sorted((*scope.input_members, scope.input_members[0]), key=lambda m: m.key)
            ),
        )


@pytest.mark.parametrize(
    "fault",
    [
        "erase",
        "duplicate",
        "target",
        "edge",
        "visibility",
        "role",
        "origin_pointer",
        "scope",
        "fragment",
        "raw",
        "surplus",
    ],
)
def test_r3_ir04_provider_source_path_cannot_disappear_or_be_substituted(fault):
    case, selector = DRIVERS[7]
    bundle = adapt(materialize(case), selector, profile())
    actual = run(bundle)
    path = actual.provenance.accepted_paths[0]
    if fault == "erase":
        paths = ()
    elif fault == "duplicate":
        paths = (path, path)
    elif fault == "target":
        # Existing ACTIVE June observation; it cannot replace the AUXILIARY provider capture.
        paths = (replace(path, target=replace(path.target, target_ref="OBS-JUN1-LATE")),)
    elif fault == "edge":
        from pit_research_lab.domain.contracts import OriginKnownValue

        paths = (replace(path, origin=replace(path.origin, object_id=OriginKnownValue("OTHER"))),)
    elif fault == "visibility":
        paths = (replace(path, visibility=A),)
    elif fault == "role":
        paths = (replace(path, path_role="ISSUER_BINDING"),)
    elif fault == "origin_pointer":
        paths = (replace(path, origin=replace(path.origin, envelope_pointer="/other")),)
    elif fault == "scope":
        paths = (replace(path, target=replace(path.target, subject_scope_refs=("OTHER",))),)
    elif fault == "fragment":
        paths = (replace(path, target=replace(path.target, fragment_selector="/statements/0")),)
    elif fault == "raw":
        paths = (replace(path, target=replace(path.target, representation_ref="OTHER")),)
    else:
        paths = (path, replace(path, path_role="ISSUER_BINDING"))
    # Fresh probes and internally balanced exclusions must not authorize missing source paths.
    from wu01_actual import _used_paths

    used = _used_paths(paths)
    changed = replace(
        actual,
        provenance=replace(
            actual.provenance,
            accepted_paths=paths,
            excluded_uses=tuple(m for m in bundle.source_members if m.key not in used),
        ),
    )
    a = association(bundle)
    with pytest.raises(ContractError):
        project(changed, a, (observe_actual(changed, a),))
