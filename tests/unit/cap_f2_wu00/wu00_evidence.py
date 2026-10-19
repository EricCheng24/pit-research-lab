"""In-memory evidence channels; static checks cannot discharge runtime obligations."""

VERDICTS = {"NOT_EXECUTED", "BLOCKED", "PASS", "FAIL", "SPECIFICATION_ISSUE"}


def initialize(cases):
    obligations = []
    seen = set()
    for case in cases:
        for tier in case["required_tiers"]:
            identity = (case["case_id"], tier)
            if identity in seen:
                raise ValueError("duplicate obligation")
            seen.add(identity)
            obligations.append(
                {
                    "case_id": identity[0],
                    "tier": tier,
                    "verdict": "NOT_EXECUTED",
                    "runtime_evidence": None,
                }
            )
    if len(obligations) != 154:
        raise ValueError("incomplete registry")
    return {"golden_runtime": obligations, "foundation_static": []}


def record_static(envelope, check_id, verdict, receipt):
    if verdict not in VERDICTS or not receipt:
        raise ValueError("invalid static evidence")
    envelope["foundation_static"].append(
        {"check_id": check_id, "verdict": verdict, "receipt": receipt}
    )


def record_runtime(envelope, case_id, tier, verdict, receipt):
    """Future use requires a separate authorization receipt; WU-00 never calls this to claim PASS."""
    if verdict not in VERDICTS or verdict == "NOT_EXECUTED":
        raise ValueError("invalid runtime evidence update")
    required = {
        "separate_runtime_authorization",
        "execution_id",
        "actual",
        "expected_source",
        "comparison",
        "negative_assertions_checked",
        "cleanup",
    }
    if not required <= receipt.keys() or not all(receipt[k] for k in required):
        raise ValueError("missing separately authorized runtime evidence")
    if verdict == "PASS" and receipt["comparison"] != "PASS":
        raise ValueError("comparison did not PASS")
    if tier == "P" and verdict == "PASS":
        persistence = receipt.get("persistence", {})
        if (
            persistence.get("backend") != "PostgreSQL"
            or persistence.get("target") != "Test"
            or persistence.get("evidence_kind") != "REAL_GUARDED_EXECUTION"
            or not persistence.get("execution_trace")
            or not persistence.get("role_guard_receipt")
        ):
            raise ValueError("P tier requires real guarded Test PostgreSQL evidence")
    matches = [
        r for r in envelope["golden_runtime"] if (r["case_id"], r["tier"]) == (case_id, tier)
    ]
    if len(matches) != 1:
        raise ValueError("unknown obligation")
    matches[0].update(verdict=verdict, runtime_evidence=receipt.copy())


def case_rollup(envelope, case):
    rows = [r for r in envelope["golden_runtime"] if r["case_id"] == case["case_id"]]
    if sorted(r["tier"] for r in rows) != sorted(case["required_tiers"]):
        return "BLOCKED"
    statuses = {r["verdict"] for r in rows}
    for status in ["SPECIFICATION_ISSUE", "FAIL", "BLOCKED", "NOT_EXECUTED"]:
        if status in statuses:
            return status
    if case.get("semantic_comparison", {}).get("status") == "UNSTRUCTURED_REQUIRES_REVIEW":
        return "BLOCKED"
    return "PASS" if rows and all(r["runtime_evidence"] for r in rows) else "BLOCKED"
