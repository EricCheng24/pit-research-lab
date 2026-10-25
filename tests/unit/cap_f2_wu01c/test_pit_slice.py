"""Offline ENGINEERING_TEST only. No Golden Oracle, receipt or acceptance import.

Reproduce the example: run this module's test_example_and_replay with pytest -s.
"""

import ast
import json
import socket
import subprocess
from dataclasses import asdict, replace
from hashlib import sha256
from pathlib import Path

import pytest
from wu01_inputs import (
    CALLER,
    NA,
    AdaptedS1Input,
    InvocationSelector,
    materialize_input,
    synthetic_proof,
    synthetic_scope,
)

from pit_research_lab.domain.contracts import (
    SCHEMA,
    BlockingFailure,
    CandidateProfile,
    Known,
    NotEvaluated,
    OriginKnownValue,
    TimeProof,
    Unknown,
    UnknownCause,
    Visibility,
)
from pit_research_lab.domain.information import assess_evidence
from pit_research_lab.domain.pit_slice import CODE_PATHS, evaluate_slice, observe_code
from pit_research_lab.domain.temporal import qualify_temporal

ROOT = Path(__file__).resolve().parents[3]
A, U = Visibility.ACTIVE, Visibility.AUXILIARY
SELECTORS = {
    "A02-C01": InvocationSelector("CHECK_BINDING", ("A-JUN-01",), "SUP-JUN1-PUB", (A,)),
    "A02-C02": InvocationSelector("CHECK_BINDING", ("A-JUN-02",), "SUP-JUN1-PUB", (A, U)),
    "A02-C03": InvocationSelector("INVENTORY_CONTENT", ("A-JUN-01", "CV-JUN-01"), NA, (A,)),
    "A02-C04": InvocationSelector("CHECK_BINDING", ("OBS-P-X-A02-C04",), NA, (A, U)),
}


@pytest.fixture(scope="module")
def code():
    return observe_code(ROOT)


def inputs(code, case="A02-C01"):
    profile = CandidateProfile(
        SCHEMA,
        "wu01-unit-v0.1-CANDIDATE",
        "wu01-reasons-v0.1-CANDIDATE",
        "s1-information-v0.1-CANDIDATE",
        code.observed_working_files,
        CALLER,
    )
    bundle = materialize_input(case, SELECTORS[case], profile)
    assert isinstance(bundle, AdaptedS1Input), bundle
    return bundle


def exact_request(request, text, zone="Asia/Taipei"):
    """Typed synthetic variation, not a modification of any WU-00 source."""
    binding = request.attempts[0].supplied
    proof = binding.proof_candidate
    assert isinstance(proof, TimeProof)
    stamp = replace(proof.timestamp, source_text=text, offset=text[-6:], timezone_name=zone)
    raw = dict(proof.raw_descriptor)
    raw.update(timestamp=text, offset=text[-6:], timezone=zone)
    proof = replace(proof, timestamp=stamp, raw_descriptor=tuple(sorted(raw.items())))
    return synthetic_proof(request, proof)


def assert_isolated(result):
    assert result.disposition == "INTEGRATED_PROVISIONAL"
    assert result.trust == "NOT_TRUSTED_PIT_EVIDENCE"
    assert result.admission_eligible is False and result.diagnostic_only is True
    assert result.source_authentication == "NOT_ESTABLISHED"
    assert asdict(result)["trust"] == "NOT_TRUSTED_PIT_EVIDENCE"


@pytest.mark.parametrize(
    "case,state",
    [
        ("A02-C01", "SUPPORTED"),
        ("A02-C02", "UNRESOLVED"),
        ("A02-C03", "SUPPORTED"),
        ("A02-C04", "UNRESOLVED"),
    ],
)
def test_materialized_vertical_paths(code, case, state):
    bundle = inputs(code, case)
    result = evaluate_slice(bundle.context, bundle.request, code)
    assert result.s2.state == state
    assert result.request is bundle.request and result.context is bundle.context
    assert result.s2.context is bundle.context
    if case == "A02-C02":
        assert result.s1.state == "UNRESOLVED"
        assert result.s2.reason == "CONTENT_BINDING_INSUFFICIENT"
        assert result.s2.provenance.rejected_attempts == result.s1.provenance.rejected_attempts
        assert isinstance(result.s2.evaluated_evidence, NotEvaluated)
    assert_isolated(result)


@pytest.mark.parametrize(
    "text,zone,state",
    [
        ("2025-07-06T23:59:59+08:00", "Asia/Taipei", "SUPPORTED"),
        ("2025-07-07T00:00:00+08:00", "Asia/Taipei", "NOT_ADMISSIBLE"),
        ("2025-07-07T00:00:01+08:00", "Asia/Taipei", "NOT_ADMISSIBLE"),
        ("2025-07-06T15:59:59+00:00", "UTC", "SUPPORTED"),
        ("2025-07-06T16:00:00+00:00", "UTC", "NOT_ADMISSIBLE"),
    ],
)
def test_exact_strict_cutoff_and_offset_normalization(code, text, zone, state):
    b = inputs(code)
    result = evaluate_slice(b.context, exact_request(b.request, text, zone), code)
    assert result.s2.state == state
    assert result.s2.reason == ("NONE" if state == "SUPPORTED" else "PUBLICATION_NOT_PRE_CUTOFF")
    assert_isolated(result)


@pytest.mark.parametrize("kind", ["upper_bound", "date_with_upper_bound", "unparsed_source_time"])
@pytest.mark.parametrize("closure", ["OPEN", "CLOSED"])
def test_unsupported_variants_are_unevaluated_even_at_cutoff(code, kind, closure):
    b = inputs(code)
    r = exact_request(b.request, b.context.information_cutoff.source_text)
    binding = r.attempts[0].supplied
    proof = binding.proof_candidate
    raw = dict(proof.raw_descriptor)
    raw.update(proof_kind=kind, bound=closure)
    proof = replace(proof, proof_kind=kind, raw_descriptor=tuple(sorted(raw.items())))
    r = synthetic_proof(r, proof)
    result = evaluate_slice(b.context, r, code)
    assert result.s2.state == "UNRESOLVED"
    assert result.s2.reason == "TEMPORAL_BOUND_INSUFFICIENT"
    assert isinstance(result.s2.evaluated_evidence, NotEvaluated)
    assert result.s2.diagnostics == ("UNSUPPORTED_PROOF_VARIANT:" + kind,)
    assert_isolated(result)


@pytest.mark.parametrize("mutation", ["target_ref", "content_version_ref", "fragment_selector"])
def test_foreign_proof_not_borrowed(code, mutation):
    b = inputs(code)
    binding = b.request.attempts[0].supplied
    proof = replace(binding.proof_candidate, **{mutation: "FOREIGN"})
    request = replace(
        b.request,
        attempts=(
            replace(b.request.attempts[0], supplied=replace(binding, proof_candidate=proof)),
        ),
    )
    result = evaluate_slice(b.context, request, code)
    assert isinstance(result.s1, BlockingFailure)
    assert result.s1.code == "SOURCE_BINDING_MISMATCH"
    assert result.s2.state == "UNRESOLVED"
    assert isinstance(result.s2.evaluated_evidence, NotEvaluated)
    assert_isolated(result)


def test_no_adequate_proof_and_blocking_s1_preserve_reason(code):
    b = inputs(code)
    unbound = evaluate_slice(b.context, replace(b.request, attempts=()), code)
    assert unbound.s2.reason == "CONTENT_BINDING_INSUFFICIENT"
    broken = replace(b.request, requested=replace(b.request.requested, representation_ref="OTHER"))
    result = evaluate_slice(b.context, broken, code)
    assert isinstance(result.s1, BlockingFailure)
    assert result.s1.code == "REQUEST_CONTENT_MISMATCH"
    assert result.s2.diagnostics == ("S1_BLOCKED:REQUEST_CONTENT_MISMATCH",)
    assert_isolated(result)


@pytest.mark.parametrize("mode", ["public", "prospective_observed"])
@pytest.mark.parametrize(
    "text,state",
    [
        ("2025-07-06T23:59:59+08:00", "SUPPORTED"),
        ("2025-07-07T00:00:00+08:00", "NOT_ADMISSIBLE"),
        ("2025-07-07T00:00:01+08:00", "NOT_ADMISSIBLE"),
    ],
)
def test_provider_capture_mode_separation_and_diagnostic_only(code, mode, text, state):
    b = inputs(code, "A02-C04")
    capture = b.request.capture
    stamp = replace(capture.completion.value, source_text=text)
    capture = replace(capture, completion=Known(stamp, capture.completion.origin))
    result = evaluate_slice(
        replace(b.context, mode=mode),
        replace(
            b.request, capture=capture, scope=synthetic_scope(b.request.scope, captures=(capture,))
        ),
        code,
    )
    assert result.s1.state == "UNRESOLVED" and result.s1.reason == "ATTRIBUTION_UNRESOLVED"
    assert result.s2.state == (state if mode == "prospective_observed" else "UNRESOLVED")
    assert isinstance(result.request.content.issuer_ref, Unknown)
    assert_isolated(result)


@pytest.mark.parametrize("fault", ["unknown", "absent", "multiple", "hash", "precision"])
def test_incomplete_or_conflicting_observations(code, fault):
    b = inputs(code)
    r = b.request
    captures = tuple(c for c in r.captures if c.representation_ref == r.content.representation_ref)
    c = captures[0]
    if fault == "unknown":
        c = replace(c, completion=Unknown(UnknownCause.ABSENT_SOURCE_FIELD, None, c.origin))
        captures = (c,)
    elif fault == "absent":
        captures = ()
    elif fault == "multiple":
        captures = (c, replace(c, observation_ref="SECOND"))
    elif fault == "hash":
        captures = (replace(c, captured_sha256="0" * 64),)
    else:
        captures = (replace(c, precision=Known("DAY", c.origin)),)
    result = evaluate_slice(
        replace(b.context, mode="prospective_observed"), replace(r, captures=captures), code
    )
    assert result.s2.state == "UNRESOLVED"
    assert_isolated(result)


def test_publication_and_observation_and_wall_clocks_are_distinct(code):
    b = inputs(code)
    public = evaluate_slice(b.context, b.request, code)
    observed = evaluate_slice(replace(b.context, mode="prospective_observed"), b.request, code)
    assert public.s2.state == "SUPPORTED"
    assert (observed.s2.state, observed.s2.reason) == ("NOT_ADMISSIBLE", "OBSERVATION_AFTER_CUTOFF")
    changed = replace(
        b.context,
        decision_wall_times=("2099-01-01T08:00:00+08:00",),
        computation_attempt_time=Known("2099-01-01T07:30:00+08:00", CALLER),
    )
    assert evaluate_slice(changed, b.request, code).s2.state == public.s2.state
    assert b.request.assertion.reference_period[1].isoformat() == "2025-06-30"


def test_sc01_apparent_bound_stays_untrusted(code):
    b = inputs(code)
    binding = b.request.attempts[0].supplied
    origin = replace(binding.target.origin, object_id=OriginKnownValue("EVID-ORD1-TIME"))
    binding = replace(
        binding, evidence_ref="EVID-ORD1-TIME", target=replace(binding.target, origin=origin)
    )
    r = replace(b.request, attempts=(replace(b.request.attempts[0], supplied=binding),))
    result = evaluate_slice(b.context, r, code)
    assert isinstance(result.s1, BlockingFailure)
    assert result.s1.code == "SOURCE_BINDING_MISMATCH"
    assert result.s2.state == "UNRESOLVED"
    assert result.s2.source_authentication == "NOT_ESTABLISHED"
    assert_isolated(result)


@pytest.mark.parametrize("fault", ["descriptor", "zone", "duplicate", "mixed"])
def test_contradictory_time_facts_block(code, fault):
    b = inputs(code)
    binding = b.request.attempts[0].supplied
    proof = binding.proof_candidate
    if fault == "zone":
        proof = replace(proof, timestamp=replace(proof.timestamp, timezone_name="UTC"))
        raw = dict(proof.raw_descriptor)
        raw["timezone"] = "UTC"
        proof = replace(proof, raw_descriptor=tuple(sorted(raw.items())))
    elif fault == "duplicate":
        proof = replace(proof, raw_descriptor=proof.raw_descriptor + (proof.raw_descriptor[0],))
    else:
        raw = dict(proof.raw_descriptor)
        raw["timestamp" if fault == "descriptor" else "upper_bound"] = "2099-01-01T00:00:00+08:00"
        proof = replace(proof, raw_descriptor=tuple(sorted(raw.items())))
    r = synthetic_proof(b.request, proof)
    result = evaluate_slice(b.context, r, code)
    assert isinstance(result.s2, BlockingFailure)
    assert result.s2.category == "CONTRACT_VIOLATION"
    assert_isolated(result)


def test_context_and_accepted_assessment_cannot_be_swapped(code):
    b = inputs(code)
    s1 = assess_evidence(b.context, b.request)
    result = qualify_temporal(replace(b.context, context_ref="FOREIGN"), b.request, s1)
    assert result.state == "UNRESOLVED" and result.diagnostics == ("INVOCATION_MISMATCH",)
    other = inputs(code, "A02-C02")
    result = qualify_temporal(
        other.context, other.request, replace(s1, requested_tuple=other.request.requested)
    )
    assert result.state == "UNRESOLVED"


def test_example_and_replay(code):
    b = inputs(code)
    first = evaluate_slice(b.context, b.request, code)
    assert evaluate_slice(b.context, b.request, code) == first
    assert observe_code(ROOT) == code
    assert first.declared_s1_pins == b.context.profile.code_pins
    assert code.head == subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    for pin, length in zip(code.observed_working_files, code.byte_lengths, strict=True):
        body = (ROOT / pin.path).read_bytes()
        assert sha256(body).hexdigest() == pin.sha256 and len(body) == length
    summary = {
        "requested": asdict(first.request.requested),
        "cutoff": b.context.information_cutoff.source_text,
        "context": b.context.context_ref,
        "mode": b.context.mode,
        "evidence_set": b.context.evidence_set_ref,
        "s1": [first.s1.state, first.s1.reason],
        "s2": [first.s2.state, first.s2.reason],
        "proof": first.s2.evaluated_evidence.proof_ref,
        "support": first.s2.accepted_binding_refs,
        "trust": first.trust,
        "disposition": first.disposition,
        "code": asdict(code),
    }
    print(json.dumps(summary, sort_keys=True, indent=2))
    assert_isolated(first)


def test_pure_composition_has_no_resource_or_oracle_dependency(code, monkeypatch):
    b = inputs(code)

    def deny(*args, **kwargs):
        raise AssertionError("resource access during pure composition")

    with monkeypatch.context() as m:
        m.setattr(Path, "read_bytes", deny)
        m.setattr(Path, "read_text", deny)
        m.setattr(subprocess, "check_output", deny)
        m.setattr(socket, "socket", deny)
        assert evaluate_slice(b.context, b.request, code).s2.state == "SUPPORTED"
    for name in CODE_PATHS[-2:]:
        tree = ast.parse((ROOT / name).read_text())
        imports = [n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
        assert not any(
            "wu0" in module or "oracle" in module or "acceptance" in module for module in imports
        )


def test_trust_flags_cannot_be_set_by_constructor_or_replace(code):
    b = inputs(code)
    result = evaluate_slice(b.context, b.request, code)
    with pytest.raises(ValueError, match="init=False"):
        replace(result, admission_eligible=True)
