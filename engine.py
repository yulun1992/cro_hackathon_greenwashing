"""Evidence comparison, strict citation validation and a clearly labeled fixture demo."""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

from documents import Document, Passage, normalize, select_passages, split_text, tokens, verify_reference

ROOT = Path(__file__).parent
STATUSES = {"supported", "contradicted", "insufficient_evidence", "not_comparable"}
TESTS = {"numeric", "time", "scope", "metric_basis", "target_vs_actual"}
REG_STATUSES = {"potential_issue", "no_issue_identified", "insufficient_information", "not_assessed"}


def load_cases() -> list[dict]:
    return json.loads((ROOT / "data" / "cases.json").read_text(encoding="utf-8"))


def parse_claims(text: str) -> list[dict]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not 1 <= len(lines) <= 15:
        raise ValueError("Enter 1–15 claims, one claim per line.")
    if any(len(line) > 2000 for line in lines):
        raise ValueError("Keep each claim under 2,000 characters.")
    return [{"id": f"C{i}", "text": line} for i, line in enumerate(lines, 1)]


def prepare(claims_text: str, disclosure_text: str, regulation: Document | None) -> dict:
    claims = parse_claims(claims_text)
    if not disclosure_text.strip():
        raise ValueError("Add supporting disclosure text before comparing.")
    if len(disclosure_text) > 35_000:
        raise ValueError("For this MVP, keep the disclosure under 35,000 characters.")
    disclosure = split_text(disclosure_text, "D")
    selected = select_passages(regulation, claims)
    return {"claims": claims, "disclosure": disclosure, "regulation": regulation,
            "selected_regulation": selected}


def fingerprint(claims_text: str, disclosure_text: str, regulation: Document | None, mode: str, model: str = "") -> str:
    return sha256(json.dumps([claims_text, disclosure_text, regulation.metadata() if regulation else None,
                             mode, model], sort_keys=True).encode()).hexdigest()


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


def demo_analysis(context: dict) -> tuple[list[dict], list[str]]:
    """Replay authored examples only. Never pretend that arbitrary text was AI-analyzed."""
    claims = [normalize(c["text"]) for c in context["claims"]]
    disclosure = normalize(" ".join(p.text for p in context["disclosure"]))
    case = next((case for case in load_cases()
                 if [normalize(c) for c in case["claims"]] == claims
                 and normalize(case["disclosure"]) == disclosure), None)
    if not case:
        raise ValueError("Offline demo supports the three unchanged examples. Select Live AI to analyze edited or custom material.")
    findings = []
    for i, expected in enumerate(case["expected"], 1):
        refs = []
        quote = expected["evidence_quote"]
        for p in context["disclosure"]:
            if normalize(quote) in normalize(p.text):
                refs.append({"id": p.id, "quote": quote})
                break
        findings.append({"claim_id": f"C{i}", "status": expected["status"],
                         "test_types": expected["test_types"], "evidence": refs,
                         "explanation": expected["explanation"],
                         "follow_up_question": expected["follow_up_question"],
                         "regulation_references": [], "regulation_status": "not_assessed",
                         "regulation_explanation": "Offline demonstration does not assess uploaded regulation."})
    findings, warnings = validate_findings({"findings": findings}, context)
    # Show genuine source quotations as candidates, explicitly separate from regulatory conclusions.
    for finding in findings:
        query = tokens(finding["claim"] + " " + " ".join(finding["test_types"]))
        candidates = sorted(context["selected_regulation"],
                            key=lambda p: len(tokens(p.text) & query), reverse=True)
        candidates = [p for p in candidates if len(tokens(p.text) & query) >= 2][:2]
        finding["candidate_regulation_passages"] = [
            {"id": p.id, "quote": p.text, "location": p.location,
             "quote_verified": True, "candidate_only": True} for p in candidates]
    return findings, warnings


def numeric_checks(context: dict) -> list[dict]:
    """Exact known-source checks, not a generic numeric extraction engine."""
    disclosure = normalize(" ".join(p.text for p in context["disclosure"]))
    case = next((c for c in load_cases() if normalize(c["disclosure"]) == disclosure), None)
    if not case:
        return []
    return [{**fact, "calculated_change_pct": round((fact["current"] / fact["baseline"] - 1) * 100, 2),
             "method": "Python arithmetic on authored synthetic facts; not model-extracted."}
            for fact in case.get("numeric_facts", [])]


def make_report(context: dict, findings: list[dict], warnings: list[str], mode: str, model: str = "") -> dict:
    doc = context["regulation"]
    count = {s: sum(f["status"] == s for f in findings) for s in sorted(STATUSES)}
    return {"generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "mode": mode, "model": model if mode == "Live AI" else None,
            "summary": count, "findings": findings, "numeric_checks": numeric_checks(context),
            "warnings": warnings + (doc.warnings if doc else []),
            "regulation": doc.metadata() if doc else None,
            "regulation_passages_sent": len(context["selected_regulation"]),
            "regulation_total_passages": len(doc.passages) if doc else 0,
            "limitations": ["Screening signals require human review; no legal compliance determination.",
                            "Uploaded version and legal applicability are not independently verified.",
                            "Quote existence is checked; semantic relevance and reasoning are not independently verified.",
                            "Long regulations use a lexical shortlist, so relevant provisions may be missed."]}
