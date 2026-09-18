"""Regression oracle is the untouched MVP, executed in a separate process."""
import copy
from dataclasses import asdict
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from green_claims.config import Settings
from green_claims.demo.fixtures import load_cases, demo_regulation, demo_analysis
from green_claims.generation.client import ChatCompletionsClient
from green_claims.generation.context import build_messages
from green_claims.ingestion.parsers import parse_document
from green_claims.pipeline import prepare, run_review
from green_claims.reporting.html import render_report
from green_claims.retrieval.lexical import LexicalRetriever


class ParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        script = '''
import json
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch
from io import BytesIO
from documents import parse_document
from engine import load_cases, prepare, demo_analysis, make_report, fingerprint
from ai_client import live_analysis
reg = parse_document("demo_regulation.md", Path("data/demo_regulation.md").read_bytes(), "DEMO 2026-09 · FICTIONAL")
output = []
for case in load_cases():
    claims = "\\n".join(case["claims"])
    context = prepare(claims, case["disclosure"], reg)
    findings, warnings = demo_analysis(context)
    report = make_report(context, findings, warnings, "Offline demo")
    report["input_fingerprint"] = fingerprint(claims, case["disclosure"], reg, "Offline demo")
    report.pop("generated_at_utc")
    captured = {}
    class Opener:
        def open(self, req, timeout):
            captured.update(json.loads(req.data))
            return BytesIO(json.dumps({"choices":[{"message":{"content":json.dumps({"findings": findings})}, "finish_reason":"stop"}]}).encode())
    with patch("ai_client.build_opener", return_value=Opener()):
        live_analysis(context, "https://example.invalid/chat/completions", "test-model")
    output.append({"report": report, "messages":captured["messages"]})
print(json.dumps(output))
'''
        cls.baseline = json.loads(subprocess.check_output([sys.executable, "-c", script], cwd=ROOT / "mvp_demo", text=True))

    def test_all_reports_and_prompts_equal_archived_mvp(self):
        for case, baseline in zip(load_cases(), self.baseline):
            with self.subTest(case=case["id"]):
                claims = "\n".join(case["claims"])
                report = run_review(claims, case["disclosure"], demo_regulation())
                report.pop("generated_at_utc")
                self.assertEqual(report, baseline["report"])
                self.assertEqual(render_report(report), render_report(baseline["report"]))
                context = prepare(claims, case["disclosure"], demo_regulation())
                self.assertEqual(build_messages(context), baseline["messages"])

    def test_long_document_chunks_and_selection_equal_archived_mvp(self):
        text = "\n\n".join(f"Article {i}. " + "emissions intensity baseline " * 90 for i in range(35))
        script = '''
import json, sys
from dataclasses import asdict
from documents import parse_document, select_passages
text = sys.stdin.read()
doc = parse_document("long.md", text.encode(), "v1")
print(json.dumps({"chunks": [asdict(p) for p in doc.passages], "selected": [asdict(p) for p in select_passages(doc, [{"id":"C1", "text":"Our emissions fell."}])]}))
'''
        old = json.loads(subprocess.check_output([sys.executable, "-c", script], cwd=ROOT / "mvp_demo", input=text, text=True))
        doc = parse_document("long.md", text.encode(), "v1")
        selected = LexicalRetriever().retrieve(doc, [{"id": "C1", "text": "Our emissions fell."}])
        self.assertEqual([asdict(p) for p in doc.passages], old["chunks"])
        self.assertEqual([asdict(p) for p in selected], old["selected"])

    def test_modular_notebook_runs_without_widgets(self):
        notebook = json.loads((ROOT / "notebooks/Green_Claims_RAG.ipynb").read_text())
        namespace = {"__name__": "__main__"}
        for cell in notebook["cells"]:
            if cell["cell_type"] == "code":
                self.assertEqual(cell["outputs"], [])
                exec(compile("".join(cell["source"]), "modular_notebook", "exec"), namespace)
        report = copy.deepcopy(namespace["report"])
        report.pop("generated_at_utc")
        self.assertEqual(report, self.baseline[0]["report"])

    def test_pipeline_validates_injected_generator_and_never_falls_back(self):
        case = load_cases()[0]
        claims = "\n".join(case["claims"])
        ctx = prepare(claims, case["disclosure"], demo_regulation())
        findings, _ = demo_analysis(ctx)
        findings[0]["evidence"][0]["quote"] = "This invented quotation must be rejected."
        class Fake:
            def generate(self, context, language):
                return {"findings": findings}
        report = run_review(claims, case["disclosure"], demo_regulation(), "Live AI", generator=Fake(), model="fake")
        self.assertEqual(report["findings"][0]["status"], "insufficient_evidence")
        class Failed:
            def generate(self, context, language):
                raise ValueError("Endpoint unavailable")
        with self.assertRaisesRegex(ValueError, "Endpoint unavailable"):
            run_review(claims, case["disclosure"], None, "Live AI", generator=Failed())
        with self.assertRaisesRegex(ValueError, "configured generator"):
            run_review(claims, case["disclosure"], None, "Live AI")
        with self.assertRaisesRegex(ValueError, "Mode must"):
            run_review(claims, case["disclosure"], None, "typo")

    def test_injected_retrieval_controls_prompt_and_citation_scope(self):
        case = load_cases()[0]
        claims = "\n".join(case["claims"])
        class EmptyRetriever:
            def retrieve(self, document, claims):
                return []
        context = prepare(claims, case["disclosure"], demo_regulation(), EmptyRetriever())
        payload = json.loads(build_messages(context)[1]["content"])
        self.assertEqual(payload["regulation_passages"], [])
        findings, _ = demo_analysis(context)
        findings[0].update(regulation_status="potential_issue", regulation_references=[{"id": "R0001", "quote": demo_regulation().passages[0].text}])
        class Fake:
            def generate(self, context, language):
                return {"findings": findings}
        report = run_review(claims, case["disclosure"], demo_regulation(), "Live AI", generator=Fake(), retriever=EmptyRetriever())
        self.assertEqual(report["regulation_passages_sent"], 0)
        self.assertEqual(report["findings"][0]["regulation_status"], "not_assessed")
        self.assertTrue(any("shortlist" in w for w in report["warnings"]))

    def test_credentials_resolve_lazily_and_are_not_in_repr(self):
        with patch.dict(os.environ, {"AZURE_OPENAI_API_KEY": "test-only-secret"}):
            client = Settings(api_url="https://example.invalid", model="test").make_client()
            self.assertEqual(client.api_key, "test-only-secret")
            self.assertNotIn("test-only-secret", repr(client))
        with self.assertRaisesRegex(ValueError, "both secret"):
            Settings(secret_scope="scope-only").make_client()
        class Secrets:
            def get(self, *, scope, key):
                self.args = (scope, key)
                return "databricks-test-secret"
        class DBUtils:
            secrets = Secrets()
        utils = DBUtils()
        client = Settings(secret_scope="scope", secret_key="entry").make_client(utils)
        self.assertEqual(utils.secrets.args, ("scope", "entry"))
        self.assertNotIn("databricks-test-secret", repr(client))

    def test_cli_all_cases_and_invalid_custom_inputs(self):
        with tempfile.TemporaryDirectory() as folder:
            for case, baseline in zip(load_cases(), self.baseline):
                out = Path(folder) / case["id"]
                subprocess.run([sys.executable, "-m", "green_claims", "--case", case["id"], "--output-dir", str(out)], check=True, capture_output=True)
                report = json.loads((out / "review.json").read_text())
                report.pop("generated_at_utc")
                self.assertEqual(report, baseline["report"])
                self.assertIn("OFFLINE DEMO", (out / "review.html").read_text())
            result = subprocess.run([sys.executable, "-m", "green_claims", "--claims", "missing.txt"], capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertIn("must be supplied together", result.stderr)


if __name__ == "__main__":
    unittest.main()
