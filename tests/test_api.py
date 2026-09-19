"""API adapter integration checks; no company endpoint or credentials required."""
import copy
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
WEB_AVAILABLE = all(importlib.util.find_spec(name) for name in ["fastapi", "httpx", "multipart"])
if WEB_AVAILABLE:
    from fastapi.testclient import TestClient
    from green_claims.config import Settings
    from green_claims.demo.fixtures import load_cases, demo_regulation, demo_analysis
    from green_claims.ingestion.parsers import MAX_FILE_BYTES
    from green_claims.interfaces.api import create_app
    from green_claims.pipeline import prepare, run_review


@unittest.skipUnless(WEB_AVAILABLE, "Install .[web,test-web] for API tests")
class ApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(create_app(Settings()))
        self.case = load_cases()[0]
        self.data = {"claims": "\n".join(self.case["claims"]), "disclosure": self.case["disclosure"],
                     "mode": "Offline demo", "regulation_source": "demo"}

    def test_all_case_reports_equal_pipeline_with_inspectable_citations(self):
        for case in load_cases():
            data = {**self.data, "claims": "\n".join(case["claims"]), "disclosure": case["disclosure"]}
            response = self.client.post("/api/reviews", data=data)
            self.assertEqual(response.status_code, 200, response.text)
            body = response.json()
            report = body["report"]
            baseline = run_review(data["claims"], data["disclosure"], demo_regulation())
            report.pop("generated_at_utc"); baseline.pop("generated_at_utc")
            self.assertEqual(report, baseline)
            sources = {p["id"]: p for p in body["sources"]["disclosure"]}
            for finding in report["findings"]:
                for ref in finding["evidence"]:
                    self.assertIn(ref["quote"], sources[ref["id"]]["text"])
            self.assertEqual(response.headers["cache-control"], "no-store")

    def test_configuration_and_cases_do_not_expose_credentials_or_expected_answers(self):
        with patch.dict(os.environ, {"AZURE_OPENAI_API_KEY": "never-return-this-secret"}):
            client = TestClient(create_app(Settings(api_url="https://private.invalid", model="internal-model")))
            result = client.get("/api/config")
            self.assertTrue(result.json()["live_available"])
            for sensitive in ["never-return-this-secret", "private.invalid", "internal-model"]:
                self.assertNotIn(sensitive, result.text)
            cases = client.get("/api/cases").json()
            self.assertEqual(len(cases), 3)
            self.assertTrue(all(set(c) == {"id", "name", "claims", "disclosure"} for c in cases))

    def test_upload_replaces_demo_and_none_removes_regulation(self):
        text = b"Article 99. Environmental claims require clear emissions evidence."
        response = self.client.post("/api/reviews", data={**self.data, "regulation_source": "upload", "version": "v2"},
                                    files={"regulation_file": ("new.txt", text, "text/plain")})
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["report"]["regulation"]["filename"], "new.txt")
        self.assertEqual(body["report"]["regulation"]["version"], "v2")
        self.assertFalse(body["report"]["regulation"]["latest_version_verified"])
        self.assertEqual(body["sources"]["regulation"][0]["text"], text.decode())
        self.assertTrue(all(f["regulation_status"] == "not_assessed" for f in body["report"]["findings"]))
        response = self.client.post("/api/reviews", data={**self.data, "regulation_source": "none"})
        self.assertIsNone(response.json()["report"]["regulation"])
        self.assertEqual(response.json()["sources"]["regulation"], [])

    def test_live_unconfigured_and_edited_offline_fail_without_fallback(self):
        response = self.client.post("/api/reviews", data={**self.data, "mode": "Live AI"})
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("report", response.json())
        response = self.client.post("/api/reviews", data={**self.data, "claims": "A new claim."})
        self.assertEqual(response.status_code, 422)
        self.assertIn("Live AI", response.json()["detail"])

    def test_live_path_uses_server_generator_and_validates_citations(self):
        findings, _ = demo_analysis(prepare(self.data["claims"], self.data["disclosure"], demo_regulation()))
        raw = {"findings": copy.deepcopy(findings)}
        raw["findings"][0]["evidence"][0]["quote"] = "A fabricated quote must be rejected."
        class Generator:
            def generate(self, context, language):
                return raw
        with patch.dict(os.environ, {"AZURE_OPENAI_API_KEY": "test-key"}), patch.object(Settings, "make_client", return_value=Generator()) as factory:
            client = TestClient(create_app(Settings(api_url="https://model.invalid", model="test-model")))
            response = client.post("/api/reviews", data={**self.data, "mode": "Live AI"})
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["report"]["mode"], "Live AI")
            self.assertEqual(response.json()["report"]["findings"][0]["status"], "insufficient_evidence")
            factory.assert_called_once()

    def test_model_failure_never_exposes_provider_details(self):
        class Generator:
            def generate(self, context, language):
                raise RuntimeError("private provider payload and secret")
        with patch.dict(os.environ, {"AZURE_OPENAI_API_KEY": "test-key"}), patch.object(Settings, "make_client", return_value=Generator()):
            client = TestClient(create_app(Settings(api_url="https://model.invalid", model="test")))
            response = client.post("/api/reviews", data={**self.data, "mode": "Live AI"})
            self.assertEqual(response.status_code, 500)
            self.assertNotIn("private provider", response.text)
            self.assertNotIn("report", response.json())

    def test_credential_loading_failure_is_sanitized(self):
        with patch.dict(os.environ, {"AZURE_OPENAI_API_KEY": "test-key"}), patch.object(Settings, "make_client", side_effect=ValueError("sensitive credential detail")):
            client = TestClient(create_app(Settings(api_url="https://model.invalid", model="test")))
            response = client.post("/api/reviews", data={**self.data, "mode": "Live AI"})
            self.assertEqual(response.status_code, 503)
            self.assertNotIn("sensitive credential detail", response.text)

    def test_missing_invalid_oversized_or_unused_upload_is_rejected(self):
        self.assertEqual(self.client.post("/api/reviews", data={**self.data, "regulation_source": "upload"}).status_code, 422)
        for name, content, status in [("bad.docx", b"abc", 422), ("blank.txt", b"", 422), ("bad.txt", b"\xff", 422), ("large.txt", b"x" * (MAX_FILE_BYTES + 1), 413)]:
            response = self.client.post("/api/reviews", data={**self.data, "regulation_source": "upload"},
                                       files={"regulation_file": (name, content)})
            self.assertEqual(response.status_code, status, response.text)
        response = self.client.post("/api/reviews", data=self.data, files={"regulation_file": ("unused.txt", b"Test content")})
        self.assertEqual(response.status_code, 422)

    def test_invalid_mode_and_lengths_do_not_echo_material(self):
        for overrides in [{"mode": "invalid"}, {"claims": "\n".join(["Claim"] * 16)}, {"claims": "x" * 2001}, {"disclosure": ""}, {"disclosure": "x" * 35001}, {"version": "x" * 201}]:
            response = self.client.post("/api/reviews", data={**self.data, **overrides})
            self.assertEqual(response.status_code, 422)
            self.assertNotIn(self.data["disclosure"], response.text)

    def test_cross_origin_submission_is_rejected_and_same_origin_works(self):
        self.assertEqual(self.client.post("/api/reviews", data=self.data, headers={"Origin": "https://other.invalid"}).status_code, 403)
        self.assertEqual(self.client.post("/api/reviews", data=self.data, headers={"Origin": "http://testserver"}).status_code, 200)

    def test_built_frontend_and_api_share_one_server(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            (path / "index.html").write_text("<!doctype html><title>Local review</title>")
            client = TestClient(create_app(Settings(), static_dir=path))
            self.assertIn("Local review", client.get("/").text)
            self.assertEqual(client.get("/api/cases").status_code, 200)
            self.assertEqual(client.get("/api/missing").status_code, 404)
            self.assertEqual(client.get("/../pyproject.toml").status_code, 404)


if __name__ == "__main__":
    unittest.main()
