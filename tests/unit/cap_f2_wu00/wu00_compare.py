"""Explicit actual/expected predicate comparison, with no selectors or source-result generation."""


def _typed_equal(actual, expected):
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        return actual.keys() == expected.keys() and all(
            _typed_equal(actual[key], value) for key, value in expected.items()
        )
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(
            _typed_equal(a, e) for a, e in zip(actual, expected, strict=True)
        )
    return actual == expected


def compare(actual, expected):
    """Normative prose requires reviewed predicate bindings; absence cannot certify semantic PASS.

    A bound contract has explicit state/value/reason, required/excluded lineage,
    forbidden-check names and tier identities. Conditional contracts supply branches
    keyed by an explicit target supplied in actual; no implicit default branch exists.
    """
    if "semantic_comparison" in expected:
        return {"verdict": "BLOCKED", "issues": ["UNSTRUCTURED_REQUIRES_REVIEW"]}
    if expected.get("binding_status") != "REVIEWED_PREDICATES":
        return {"verdict": "BLOCKED", "issues": ["predicate binding not reviewed"]}
    contract = expected
    if "branches" in expected:
        target = actual.get("target")
        if target not in expected["branches"]:
            return {"verdict": "FAIL", "issues": ["missing/unknown conditional target"]}
        contract = expected["branches"][target]
    required = {
        "system_state",
        "value",
        "reason",
        "required_lineage",
        "excluded_lineage",
        "forbidden_checks",
        "required_tiers",
    }
    if not required <= contract.keys():
        return {"verdict": "BLOCKED", "issues": ["incomplete expected predicates"]}
    issues = []
    for field in ["system_state", "value", "reason", "required_tiers"]:
        if field not in actual or not _typed_equal(actual[field], contract[field]):
            issues.append(field)
    lineage = actual.get("lineage")
    if not isinstance(lineage, list) or any(not isinstance(x, str) for x in lineage):
        issues.append("missing/invalid lineage")
    elif (
        len(lineage) != len(set(lineage))
        or not set(contract["required_lineage"]) <= set(lineage)
        or set(contract["excluded_lineage"]) & set(lineage)
    ):
        issues.append("lineage/exclusion")
    checks = actual.get("forbidden_checks")
    names = contract["forbidden_checks"]
    if not isinstance(checks, dict) or set(checks) != set(names):
        issues.append("missing/extra forbidden checks")
    elif any(checks[name] is not False for name in names):
        issues.append("forbidden behavior")
    return {"verdict": "FAIL" if issues else "PASS", "issues": issues}
