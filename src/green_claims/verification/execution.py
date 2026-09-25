"""Optional review stages. Their evidence is recorded separately from the primary finding."""
from green_claims.verification.facts import check_facts
from green_claims.verification.judge import validate_judgments

MODES = {"none", "facts", "facts_and_judge"}


def require_stages(generator, mode):
    if mode not in MODES:
        raise ValueError("Verification must be none, facts or facts_and_judge.")
    if mode != "none" and not callable(getattr(generator, "extract_facts", None)):
        raise ValueError("This generator does not support fact extraction.")
    if mode == "facts_and_judge" and not callable(getattr(generator, "judge", None)):
        raise ValueError("This generator does not support the judge stage.")


def verify(context, findings, generator, mode, language):
    """Model failures leave primary results intact, with explicit unavailable stages."""
    by_id = {claim["id"]: {"claim_id": claim["id"]} for claim in context["claims"]}
    stages = {"fact_extraction": "unavailable", "judge": "not_requested"}
    warnings = []
    try:
        checks = check_facts(generator.extract_facts(context, language), context)
        stages["fact_extraction"] = "completed"
        for check in checks:
            by_id[check["claim_id"]]["facts"] = check
    except Exception:
        stages["fact_extraction"] = "failed"
        warnings.append("Fact extraction or validation failed; no arithmetic was verified. Review the source manually.")
    if mode == "facts_and_judge":
        try:
            judgments = validate_judgments(generator.judge(
                context, findings, [row.get("facts") for row in by_id.values()], language), context)
            stages["judge"] = "completed"
            for opinion in judgments:
                by_id[opinion["claim_id"]]["judge"] = opinion
        except Exception:
            stages["judge"] = "failed"
            warnings.append("Judge call or citation validation failed; no second-pass opinion is available.")
    for finding in findings:
        row = by_id[finding["claim_id"]]
        facts, opinion = row.get("facts"), row.get("judge")
        reasons = []
        if facts is None:
            reasons.append("Fact extraction unavailable")
        else:
            if facts["status"] != "aligned":
                reasons.append("Fact dimensions " + facts["status"].replace("_", " "))
            arithmetic = facts["arithmetic"]["status"]
            if arithmetic == "not_computed":
                reasons.append("Arithmetic not computed")
            if arithmetic == "mismatch" and finding["status"] == "supported":
                reasons.append("Arithmetic conflicts with primary supported finding")
            if arithmetic == "match" and finding["status"] == "contradicted":
                reasons.append("Arithmetic matches one focal comparison despite primary contradiction")
            if arithmetic == "mismatch":
                reasons.append("Numeric mismatch requires review of extracted premises")
        if mode == "facts_and_judge":
            if opinion is None:
                reasons.append("Judge unavailable")
            elif opinion["status"] != "agree":
                reasons.append("Judge " + opinion["status"].replace("_", " "))
        row["human_review_required"] = bool(reasons)
        row["review_reasons"] = reasons
        finding["verification"] = row
    return {"mode": mode, "stages": stages, "claims": list(by_id.values()),
            "expected_model_calls": 2 if mode == "facts" else 3,
            "limitations": ["The model extracts source meaning; exact quotations do not validate that meaning.",
                            "Arithmetic checks one explicit focal quantity, subject to extracted scope, units and dates.",
                            "The judge is a model opinion, not independent ground truth or a legal decision."]}, warnings
