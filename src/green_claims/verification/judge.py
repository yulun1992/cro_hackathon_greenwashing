"""Validate second-pass review opinions against sources available for that run."""
from green_claims.verification.facts import keyed_rows, references

ISSUES = {"unsupported_conclusion", "missing_condition", "wrong_scope", "wrong_period", "metric_mismatch",
          "numeric_error", "extraction_error", "regulatory_overreach", "insufficient_evidence"}


def validate_judgments(raw, context):
    rows = keyed_rows(raw, "reviews", context["claims"])
    disclosures = {p.id: p for p in context["disclosure"]}
    regulations = {p.id: p for p in context["selected_regulation"]}
    output = []
    for claim in context["claims"]:
        row = rows[claim["id"]]
        comparison, regulation = row.get("comparison_verdict"), row.get("regulation_verdict")
        if not isinstance(comparison, str) or comparison not in {"agree", "disagree", "uncertain"}:
            raise ValueError("Invalid judge comparison verdict.")
        if not isinstance(regulation, str) or regulation not in {"agree", "disagree", "uncertain", "not_assessed"}:
            raise ValueError("Invalid judge regulation verdict.")
        issues, explanation = row.get("issues"), row.get("explanation")
        if not isinstance(issues, list) or len(issues) > len(ISSUES) or any(not isinstance(i, str) or i not in ISSUES for i in issues):
            raise ValueError("Invalid judge issue labels.")
        if not isinstance(explanation, str) or not explanation.strip() or len(explanation) > 4000:
            raise ValueError("Invalid judge explanation.")
        drefs, dbad = references(row.get("disclosure_references", []), disclosures, 8)
        rrefs, rbad = references(row.get("regulation_references", []), regulations, 8)
        warnings = []
        if dbad or (comparison != "uncertain" and not drefs):
            comparison = "uncertain"
            warnings.append("Judge comparison citations could not be validated.")
        if rbad or (regulation in {"agree", "disagree"} and not rrefs):
            regulation = "uncertain"
            warnings.append("Judge regulatory citations could not be validated.")
        if not regulations:
            if row.get("regulation_verdict") != "not_assessed":
                warnings.append("No supplied regulation permits a regulatory review opinion.")
            regulation = "not_assessed"
        status = "needs_review" if "disagree" in {comparison, regulation} or issues else "uncertain" if "uncertain" in {comparison, regulation} or warnings else "agree"
        output.append({"claim_id": claim["id"], "status": status, "comparison_verdict": comparison,
                       "regulation_verdict": regulation, "issues": issues, "explanation": explanation,
                       "disclosure_references": drefs, "regulation_references": rrefs,
                       "warnings": warnings, "authoritative": False})
    return output
