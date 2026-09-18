"""Fail-closed output structure and quotation checks."""
from green_claims.validation.citations import verify_reference

STATUSES = {"supported", "contradicted", "insufficient_evidence", "not_comparable"}


TESTS = {"numeric", "time", "scope", "metric_basis", "target_vs_actual"}


REG_STATUSES = {"potential_issue", "no_issue_identified", "insufficient_information", "not_assessed"}


def validate_findings(raw: dict, context: dict) -> tuple[list[dict], list[str]]:
    if not isinstance(raw, dict) or not isinstance(raw.get("findings"), list):
        raise ValueError("The model must return a JSON object containing a findings array.")
    claims = {c["id"]: c["text"] for c in context["claims"]}
    items = raw["findings"]
    if (len(items) != len(claims) or any(not isinstance(x, dict) or not isinstance(x.get("claim_id"), str) for x in items)
            or {x.get("claim_id") for x in items} != set(claims)):
        raise ValueError("The model did not return exactly one finding per claim. Retry the analysis.")
    disclosures = {p.id: p for p in context["disclosure"]}
    regulations = {p.id: p for p in context["selected_regulation"]}
    warnings, output = [], []
    for item in items:
        cid = item["claim_id"]
        if not isinstance(item.get("status"), str) or item["status"] not in STATUSES:
            raise ValueError(f"Invalid comparison status for {cid}.")
        test_types = item.get("test_types", [])
        if not isinstance(test_types, list) or not test_types or any(not isinstance(t, str) or t not in TESTS for t in test_types):
            raise ValueError(f"Invalid test categories for {cid}.")
        checked = {}
        rejected = False
        for field, sources in [("evidence", disclosures), ("regulation_references", regulations)]:
            refs = item.get(field, [])
            if not isinstance(refs, list) or len(refs) > 8:
                raise ValueError(f"Invalid references for {cid}.")
            checked[field] = []
            for reference in refs:
                verified = verify_reference(reference, sources)
                if verified:
                    checked[field].append(verified)
                else:
                    rejected = True
                    warnings.append(f"{cid}: rejected an unverified {field} citation.")
        explanation = item.get("explanation", "")
        follow_up = item.get("follow_up_question", "")
        if not isinstance(explanation, str) or not isinstance(follow_up, str):
            raise ValueError(f"Invalid explanation for {cid}.")
        status = item["status"]
        # A rejected citation can invalidate the reasoning, even if another citation passes.
        if rejected or (status in {"supported", "contradicted", "not_comparable"} and not checked["evidence"]):
            status = "insufficient_evidence"
            explanation = "The generated evidence trail could not be validated. Re-run or review the source manually."
            follow_up = "Which source passage substantiates or contradicts this claim?"
        reg_status = item.get("regulation_status", "not_assessed")
        if not isinstance(reg_status, str) or reg_status not in REG_STATUSES:
            raise ValueError(f"Invalid regulation status for {cid}.")
        reg_explanation = item.get("regulation_explanation", "")
        if not isinstance(reg_explanation, str):
            raise ValueError(f"Invalid regulation explanation for {cid}.")
        if rejected or not checked["regulation_references"]:
            reg_status = "not_assessed"
            reg_explanation = "No validated regulatory assessment. Upload relevant regulation and run live AI analysis."
        output.append({"claim_id": cid, "claim": claims[cid], "status": status,
                       "test_types": test_types, "explanation": explanation,
                       "follow_up_question": follow_up, **checked,
                       "regulation_status": reg_status, "regulation_explanation": reg_explanation})
    order = {cid: i for i, cid in enumerate(claims)}
    return sorted(output, key=lambda row: order[row["claim_id"]]), warnings
