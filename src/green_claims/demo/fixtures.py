"""Explicit synthetic fixtures; never sent as expected answers to the model."""
from importlib.resources import files
import json
from green_claims.ingestion.parsers import parse_document
from green_claims.text import normalize, tokens
from green_claims.validation.findings import validate_findings

def load_cases() -> list[dict]:
    return json.loads(files("green_claims.demo").joinpath("data/cases.json").read_text(encoding="utf-8"))

def demo_regulation():
    content = files("green_claims.demo").joinpath("data/demo_regulation.md").read_bytes()
    return parse_document("demo_regulation.md", content, "DEMO 2026-09 · FICTIONAL")

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
