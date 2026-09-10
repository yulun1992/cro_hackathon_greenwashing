"""Build readable standalone notebook, Databricks source notebook and offline browser demo."""
import base64
import json
from pathlib import Path

from documents import parse_document
from engine import demo_analysis, load_cases, make_report, prepare
from render import STYLE, render_report

ROOT = Path(__file__).parent


def markdown(source):
    return {"cell_type": "markdown", "metadata": {}, "source": source.splitlines(keepends=True)}


def code(source):
    return {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": source.splitlines(keepends=True)}


def source(filename):
    return (ROOT / filename).read_text(encoding="utf-8")


def build():
    cases = load_cases()
    sample_regulation = source("data/demo_regulation.md")
    cells = [markdown("""# Green Claims Checker — CRO hackathon
**AI-driven comparison, testing and greenwashing screening**

Import this `.ipynb` into Databricks. Your laptop only needs a browser. The notebook includes all code and three fictional cases; no Git clone or local Python is required.

1. Attach Python compute and run all cells. The default is **Offline demo** (authored fixtures, no AI call).
2. For live analysis, configure the full Azure chat/completions URL, deployment name and Databricks secret below. Your team's approved network and model access must already work.
3. Use the last UI cell: select a case, upload a regulation, choose Live AI, click Compare & screen.
4. Quotes are checked against extracted text. Relevance and legal applicability still require review. Uploaded versions are not automatically verified as current.

**Optional PDF support:** if pypdf is missing, run `%pip install pypdf` in a separate cell if your environment permits it; otherwise use TXT/MD. The default examples and HTTP client use only the Python standard library. ipywidgets provides an optional UI; a configuration-cell fallback is included.
"""), code('''import os
from pathlib import Path

# Paste the FULL approved chat/completions URL, including api-version if required.
# Keep actual keys out of notebook source and GitHub.
API_URL = os.getenv("AZURE_OPENAI_CHAT_URL", "")
MODEL = os.getenv("AZURE_OPENAI_DEPLOYMENT", "")
SECRET_SCOPE = ""  # e.g. your existing Databricks secret scope
SECRET_KEY = ""    # key name inside that scope, NOT the API key itself
AUTH_TYPE = "api-key"  # use "bearer" if your team supplies an appropriate bearer credential
OUTPUT_LANGUAGE = "English"  # or "中文"

# If your bank already has an approved client/wrapper, replace the HTTP call
# in live_analysis with that existing client. The prompt and validator stay unchanged.
'''), markdown("## Synthetic data\nThree fictional companies, nine claims, human-authored expected findings. The demo standard below is fictional, not real law."),
             code("import json\nCASES = json.loads(" + repr(json.dumps(cases, ensure_ascii=False)) + ")\nDEMO_REGULATION = " + repr(sample_regulation) + "\n")]
    documents = source("documents.py")
    engine = source("engine.py").replace("from documents import Document, Passage, normalize, select_passages, split_text, tokens, verify_reference\n", "")
    engine = engine.replace("ROOT = Path(__file__).parent", "# CASES is defined in the data cell above")
    engine = engine.replace('return json.loads((ROOT / "data" / "cases.json").read_text(encoding="utf-8"))', "return CASES")
    client = source("ai_client.py").replace("from documents import passage_dicts\n", "").replace("from engine import validate_findings\n", "")
    for title, content in [("Document parsing and exact quotations", documents), ("Comparison and validation", engine),
                           ("Azure-compatible AI request", client), ("HTML result view", source("render.py")),
                           ("Interactive notebook front end", source("notebook_ui.py"))]:
        cells.extend([markdown("## " + title), code(content)])
    cells += [markdown("""## Fallback if interactive widgets do not render
Set `RUN_FALLBACK = True`, choose the case/mode below, and run this cell. To use your regulation, upload a file through the Databricks workspace/volume UI and paste the accessible path. `displayHTML` is the front end; no Streamlit, server or local Python is required.
"""), code('''RUN_FALLBACK = False
FALLBACK_CASE = "A"
FALLBACK_MODE = "Offline demo"  # "Live AI" after configuring the endpoint above
REGULATION_PATH = ""  # /Workspace/.../regulation.txt or /Volumes/.../regulation.pdf
REGULATION_VERSION = ""  # user-supplied version or effective date

if RUN_FALLBACK:
    selected_case = next(c for c in CASES if c["id"] == FALLBACK_CASE)
    regulation = resolve_regulation("Workspace file", REGULATION_VERSION, path=REGULATION_PATH) if REGULATION_PATH else resolve_regulation("Fictional demo standard", "")
    last_report = run_review("\\n".join(selected_case["claims"]), selected_case["disclosure"], regulation, FALLBACK_MODE)
    html_report = render_report(last_report)
    if "displayHTML" in globals():
        displayHTML(html_report)
    else:
        from IPython.display import HTML, display
        display(HTML(html_report))
'''), markdown("""## Optional export for your three-minute pitch
After a successful review, run this cell to generate standalone HTML and JSON in the Databricks driver's temporary filesystem. Change `EXPORT_DIR` to a writable workspace/volume folder if you want to download them from Databricks. Temporary files are not durable. The on-screen report also has a JSON download link (browser policy permitting).

Exported HTML opens locally in a browser without Python and clearly records whether results came from live AI or the offline demo.
"""), code('''EXPORT_RESULTS = False
EXPORT_DIR = "/tmp/green_claims_pitch"
if EXPORT_RESULTS and last_report:
    destination = Path(EXPORT_DIR)
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "review.html").write_text(render_report(last_report), encoding="utf-8")
    (destination / "review.json").write_text(json.dumps(last_report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Saved review.html and review.json in", str(destination))
''')]
    notebook = {"cells": cells, "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                                             "language_info": {"name": "python", "version": "3.10"}}, "nbformat": 4, "nbformat_minor": 5}
    for i, cell in enumerate(cells):
        cell["id"] = f"cell-{i:02d}"
    (ROOT / "Green_Claims_Databricks.ipynb").write_text(json.dumps(notebook, ensure_ascii=False, indent=1), encoding="utf-8")
    source_cells = []
    for cell in cells:
        content = "".join(cell["source"])
        if cell["cell_type"] == "markdown":
            content = "# MAGIC %md\n" + "\n".join("# MAGIC " + line for line in content.splitlines())
        source_cells.append(content)
    (ROOT / "Green_Claims_Databricks.py").write_text("# Databricks notebook source\n" + "\n\n# COMMAND ----------\n\n".join(source_cells), encoding="utf-8")
    regulation = parse_document("demo_regulation.md", sample_regulation.encode(), "DEMO 2026-09 · FICTIONAL")
    htmls, report_data = [], []
    for case in cases:
        ctx = prepare("\n".join(case["claims"]), case["disclosure"], regulation)
        findings, warnings = demo_analysis(ctx)
        report = make_report(ctx, findings, warnings, "Offline demo")
        report_data.append(report)
        htmls.append(base64.b64encode(render_report(report).encode()).decode())
    options = "".join(f'<option value="{i}">{case["name"]}</option>' for i, case in enumerate(cases))
    viewer = '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Green Claims · Offline pitch demo</title><style>' + STYLE + 'iframe{width:100%;height:1250px;border:0;background:#f5f8f6}main{padding-bottom:0}</style></head><body><main><h2>Browser-only pitch preview</h2><p>Open this file without Python or an internet connection. These are authored examples, not live AI results. Run the Databricks notebook for AI analysis and regulation uploads.</p><select id="case" aria-label="Choose a synthetic case">' + options + '</select><button id="show">Show review</button></main><iframe id="review" title="Green claims review" sandbox="allow-downloads"></iframe><script>const reports=' + json.dumps(htmls) + ';function show(){const bytes=Uint8Array.from(atob(reports[Number(document.getElementById("case").value)]),c=>c.charCodeAt(0));document.getElementById("review").srcdoc=new TextDecoder().decode(bytes)}document.getElementById("show").onclick=show;show();</script></body></html>'
    (ROOT / "demo.html").write_text(viewer, encoding="utf-8")
    (ROOT / "data" / "offline_expected_reports.json").write_text(json.dumps(report_data, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Built standalone notebook, Databricks source notebook and offline HTML demo.")


if __name__ == "__main__":
    build()
