"""Self-contained HTML report: display in a notebook or open on any modern browser."""
from __future__ import annotations

import base64
from html import escape
import json

LABELS = {"supported": "Supported in supplied material", "contradicted": "Contradicted",
          "insufficient_evidence": "Insufficient evidence", "not_comparable": "Not comparable"}
STYLE = """
*{box-sizing:border-box}body{margin:0;background:#f5f8f6;color:#18392f;font:15px/1.55 system-ui,sans-serif}
main{max-width:1120px;margin:auto;padding:30px}h1{font-size:32px;margin:8px 0}h2{font-size:21px}h3{font-size:17px}
.eyebrow{letter-spacing:.12em;font-size:12px;font-weight:700;color:#347a60}.muted{color:#5b7067;font-size:13px}
.banner{background:#e3eee7;border:1px solid #bad1c2;border-radius:10px;padding:12px 16px;margin:20px 0}
.metrics{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}.metric,.card{background:white;border:1px solid #d5e1d9;border-radius:12px;padding:18px;margin:12px 0}
.metric strong{font-size:29px;display:block}.grid{display:grid;grid-template-columns:1fr 1fr;gap:22px}
.badge{display:inline-block;font-size:12px;font-weight:700;padding:4px 9px;border-radius:20px;background:#edf1ee}
.contradicted{background:#fbe3de;color:#9b3225}.insufficient_evidence,.not_comparable{background:#fff0ce;color:#775109}.supported{background:#e0f1e7;color:#216c49}
blockquote{border-left:3px solid #84ab97;padding:8px 14px;margin:10px 0;background:#f5f8f6;white-space:pre-wrap;overflow-wrap:anywhere}
details{margin:14px 0}summary{cursor:pointer;font-weight:600}.button,button{display:inline-block;background:#176b56;color:white;padding:10px 16px;border-radius:7px;border:0;text-decoration:none;cursor:pointer;font-size:14px}
select{padding:10px;border:1px solid #b0c7b8;border-radius:6px;margin-right:10px;max-width:100%}table{border-collapse:collapse;width:100%}td,th{text-align:left;padding:10px;border-bottom:1px solid #d5e1d9}
@media(max-width:700px){main{padding:16px}.metrics{grid-template-columns:1fr 1fr}.grid{grid-template-columns:1fr}h1{font-size:26px}}
"""


def text(value):
    return escape(str(value), quote=True)


def source_html(ref, source_name):
    return (f'<p class="muted">[{text(ref["id"])}] {text(source_name)} · '
            f'{text(ref["location"])} · quote verified</p><blockquote>{text(ref["quote"])}</blockquote>')


def report_body(report: dict) -> str:
    source = report.get("regulation")
    source_name = f'{source["filename"]} · {source["version"]}' if source else "No regulation supplied"
    offline = report["mode"] == "Offline demo"
    banner = ("OFFLINE DEMO · Authored example findings. No AI call or regulatory assessment was performed."
              if offline else "LIVE AI · Citations were checked against source text. Reasoning and legal applicability require human review.")
    result = f'<p class="eyebrow">CRO REVIEW WORKSPACE</p><h1>Green Claims Checker</h1><p>AI-driven comparison, testing and greenwashing screening</p><div class="banner">{banner}</div>'
    result += '<div class="metrics">'
    for status in ["contradicted", "insufficient_evidence", "not_comparable", "supported"]:
        result += f'<div class="metric"><strong>{int(report["summary"].get(status, 0))}</strong>{LABELS[status]}</div>'
    result += '</div>'
    if source:
        result += f'<p class="muted">Regulation: {text(source_name)} · SHA-256 {text(source["sha256"][:12])}… · latest version not independently verified.<br>Passages used: {report["regulation_passages_sent"]}/{report["regulation_total_passages"]}.</p>'
    for warning in report.get("warnings", []):
        result += f'<div class="banner">{text(warning)}</div>'
    for f in report["findings"]:
        result += f'<section class="card"><span class="badge {text(f["status"])}">{text(LABELS[f["status"]])}</span><h2>{text(f["claim_id"])} · {text(f["claim"])}</h2><p class="muted">Tests: {text(", ".join(f["test_types"]))}</p><p>{text(f["explanation"])}</p><div class="grid"><div><h3>Disclosure evidence</h3>'
        result += "".join(source_html(ref, "Supporting disclosure") for ref in f["evidence"]) or '<p class="muted">No validated disclosure citation.</p>'
        result += f'</div><div><h3>Regulatory assessment</h3><p><b>{text(f["regulation_status"].replace("_", " "))}</b></p><p>{text(f["regulation_explanation"])}</p>'
        result += "".join(source_html(ref, source_name) for ref in f["regulation_references"])
        for ref in f.get("candidate_regulation_passages", []):
            result += '<details><summary>Candidate passage only · not a regulatory conclusion</summary>' + source_html(ref, source_name) + '</details>'
        result += f'</div></div><p><b>Suggested follow-up:</b> {text(f["follow_up_question"])}</p></section>'
    if report.get("numeric_checks"):
        result += '<details><summary>Python arithmetic · synthetic source figures</summary>'
        for fact in report["numeric_checks"]:
            result += f'<p>{text(fact["metric"])}: {fact["baseline"]:,.0f} → {fact["current"]:,.0f} {text(fact["unit"])}; change {fact["calculated_change_pct"]:+.2f}%.</p>'
        result += '<p class="muted">Calculated from authored synthetic facts; not generic extraction from arbitrary documents.</p></details>'
    result += '<p class="muted">' + '<br>'.join(text(x) for x in report["limitations"]) + '</p>'
    data = base64.b64encode(json.dumps(report, ensure_ascii=False, indent=2).encode()).decode()
    result += f'<a class="button" download="green_claims_review.json" href="data:application/json;base64,{data}">Download review JSON</a>'
    return result


def render_report(report: dict) -> str:
    return '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Green Claims Review</title><style>' + STYLE + '</style></head><body><main>' + report_body(report) + '</main></body></html>'
