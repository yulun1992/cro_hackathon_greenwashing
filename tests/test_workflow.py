import copy
from http.server import BaseHTTPRequestHandler, HTTPServer
from io import BytesIO
import json
from pathlib import Path
import sys
import threading
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ai_client import live_analysis
from documents import Passage, parse_document, select_passages, verify_reference
from engine import demo_analysis, load_cases, make_report, prepare, validate_findings
from render import render_report


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.cases = load_cases()
        self.reg = parse_document("rules.md", (ROOT / "data/demo_regulation.md").read_bytes(), "v1")
        self.case = self.cases[0]
        self.context = prepare("\n".join(self.case["claims"]), self.case["disclosure"], self.reg)
        self.findings, _ = demo_analysis(self.context)

    def raw(self):
        return {"findings": copy.deepcopy(self.findings)}

    def test_all_nine_authored_cases_and_arithmetic(self):
        for case in self.cases:
            context = prepare("\n".join(case["claims"]), case["disclosure"], self.reg)
            findings, warnings = demo_analysis(context)
            self.assertEqual([f["status"] for f in findings], [e["status"] for e in case["expected"]])
            self.assertEqual(warnings, [])
            self.assertTrue(all(f["evidence"] for f in findings))
            self.assertTrue(all(f["regulation_status"] == "not_assessed" for f in findings))
        report = make_report(self.context, self.findings, [], "Offline demo")
        self.assertEqual(report["numeric_checks"][0]["calculated_change_pct"], 8.0)

    def test_custom_text_never_returns_canned_demo(self):
        altered = prepare("Our products are sustainable.", self.case["disclosure"], self.reg)
        with self.assertRaisesRegex(ValueError, "Offline demo"):
            demo_analysis(altered)

    def test_fabricated_evidence_downgrades_finding(self):
        raw = self.raw()
        raw["findings"][0]["evidence"][0]["quote"] = "Invented sentence that is not in the source."
        result, warnings = validate_findings(raw, self.context)
        self.assertEqual(result[0]["status"], "insufficient_evidence")
        self.assertIn("could not be validated", result[0]["explanation"])
        self.assertTrue(warnings)

    def test_forged_regulatory_citation_removes_assessment(self):
        raw = self.raw()
        raw["findings"][0].update(regulation_status="potential_issue", regulation_explanation="A legal issue.",
                                  regulation_references=[{"id": "R0003", "quote": "This law proves greenwashing."}])
        result, _ = validate_findings(raw, self.context)
        self.assertEqual(result[0]["regulation_status"], "not_assessed")
        self.assertEqual(result[0]["regulation_references"], [])

    def test_valid_uploaded_regulation_citation_preserves_parser_location(self):
        doc = parse_document("new_rules.txt", b"Article 99. Emissions intensity must not be described as absolute emissions.", "2026-09-09")
        context = prepare("\n".join(self.case["claims"]), self.case["disclosure"], doc)
        raw = self.raw()
        raw["findings"][0].update(regulation_status="potential_issue", regulation_explanation="The claim confuses intensity and absolute emissions; applicability needs review.",
                                  regulation_references=[{"id": "R0001", "quote": doc.passages[0].text, "location": "invented page 900"}])
        result, _ = validate_findings(raw, context)
        self.assertEqual(result[0]["regulation_status"], "potential_issue")
        self.assertEqual(result[0]["regulation_references"][0]["location"], "paragraph 1")
        report = make_report(context, result, [], "Live AI", "test-model")
        self.assertEqual(report["regulation"]["version"], "2026-09-09")
        self.assertFalse(report["regulation"]["latest_version_verified"])

    def test_missing_regulation_cannot_produce_regulatory_clearance(self):
        context = prepare("\n".join(self.case["claims"]), self.case["disclosure"], None)
        raw = self.raw()
        raw["findings"][0].update(regulation_status="no_issue_identified", regulation_explanation="Compliant.")
        result, _ = validate_findings(raw, context)
        self.assertEqual(result[0]["regulation_status"], "not_assessed")
        self.assertNotIn("Compliant", result[0]["regulation_explanation"])

    def test_changed_document_does_not_reuse_old_quote(self):
        new = parse_document("rules.md", b"Entirely different rule without the previous language.", "v2")
        self.assertNotEqual(new.sha256, self.reg.sha256)
        ref = {"id": "R0001", "quote": self.reg.passages[0].text}
        self.assertIsNone(verify_reference(ref, {p.id: p for p in new.passages}))

    def test_missing_or_duplicate_claims_fail_closed(self):
        raw = self.raw()
        raw["findings"][1]["claim_id"] = "C1"
        with self.assertRaises(ValueError):
            validate_findings(raw, self.context)

    def test_malformed_reference_and_status(self):
        self.assertIsNone(verify_reference({"id": [], "quote": "bad shape here"}, {}))
        raw = self.raw()
        raw["findings"][0]["status"] = []
        with self.assertRaises(ValueError):
            validate_findings(raw, self.context)

    def test_text_upload_validation(self):
        for name, payload in [("rules.txt", b""), ("rules.docx", b"abc"), ("rules.txt", b"\xff\xfe")]:
            with self.assertRaises(ValueError):
                parse_document(name, payload)

    def test_long_document_has_explicit_bounded_shortlist(self):
        doc = parse_document("long.md", ("\n\n".join(f"Section {i}. " + "emissions intensity baseline " * 80 for i in range(40))).encode())
        selected = select_passages(doc, self.context["claims"], budget=4000)
        self.assertLess(len(selected), len(doc.passages))
        self.assertLessEqual(sum(len(p.text) for p in selected), 4000)

    def test_html_escapes_source_content(self):
        report = make_report(self.context, self.findings, [], "Offline demo")
        report["findings"][0]["claim"] = '<script>alert("x")</script>'
        html = render_report(report)
        self.assertIn("&lt;script&gt;", html)
        self.assertNotIn('<script>alert("x")</script>', html)

    def test_pdf_page_citation_and_blank_pdf_failure(self):
        try:
            from pypdf import PdfWriter
            from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject
        except ImportError:
            self.skipTest("Optional pypdf dependency unavailable")
        writer = PdfWriter()
        page = writer.add_blank_page(width=595, height=842)
        blank = BytesIO()
        writer.write(blank)
        with self.assertRaisesRegex(ValueError, "No readable text"):
            parse_document("scan.pdf", blank.getvalue())
        font = DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"), NameObject("/BaseFont"): NameObject("/Helvetica")})
        page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})})
        stream = DecodedStreamObject()
        stream.set_data(b"BT /F1 12 Tf 50 750 Td (Article 1. Environmental claims require evidence.) Tj ET")
        page[NameObject("/Contents")] = stream
        payload = BytesIO()
        writer.write(payload)
        doc = parse_document("rules.pdf", payload.getvalue(), "v2026")
        self.assertIn("PDF page 1", doc.passages[0].location)
        self.assertIn("Environmental claims require evidence", doc.passages[0].text)

    def test_live_transport_to_simulated_azure_compatible_endpoint(self):
        raw = self.raw()
        passage = next(p for p in self.reg.passages if "Article 2" in p.text)
        raw["findings"][0].update(regulation_status="potential_issue", regulation_explanation="Metric basis mismatch; synthetic provision.",
                                  regulation_references=[{"id": passage.id, "quote": passage.text}])
        captured = {}
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                captured["body"] = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                captured["key"] = self.headers.get("api-key")
                body = json.dumps({"choices": [{"finish_reason": "stop", "message": {"content": json.dumps(raw)}}]}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body)
            def log_message(self, *args):
                pass
        server = HTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            results, warnings = live_analysis(self.context, f"http://127.0.0.1:{server.server_port}/chat/completions", "test-model", "test-key", "api-key")
        finally:
            server.shutdown()
            server.server_close()
            thread.join()
        self.assertEqual(captured["key"], "test-key")
        self.assertEqual(captured["body"]["model"], "test-model")
        sent = json.loads(captured["body"]["messages"][1]["content"])
        self.assertEqual(len(sent["claims"]), 3)
        self.assertNotIn("expected", sent)
        self.assertEqual(results[0]["regulation_status"], "potential_issue")
        self.assertEqual(warnings, [])

    def test_notebook_self_contained_without_optional_ui(self):
        notebook = json.loads((ROOT / "Green_Claims_Databricks.ipynb").read_text())
        namespace = {"__name__": "__main__"}
        for index, cell in enumerate(notebook["cells"]):
            if cell["cell_type"] == "code":
                self.assertEqual(cell["outputs"], [])
                exec(compile("".join(cell["source"]), f"cell_{index}", "exec"), namespace)
        reg = namespace["resolve_regulation"]("Fictional demo standard", "")
        report = namespace["run_review"]("\n".join(self.case["claims"]), self.case["disclosure"], reg)
        self.assertEqual(report["summary"]["contradicted"], 3)


if __name__ == "__main__":
    unittest.main()
