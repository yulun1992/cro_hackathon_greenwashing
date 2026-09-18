"""Optional real-widget callback smoke test; no Databricks or model credentials."""
import contextlib
import importlib.util
import io
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from green_claims.interfaces.notebook import show_review, resolve_regulation


class NotebookTests(unittest.TestCase):
    def test_upload_formats_replace_demo_source(self):
        body = b"Article 99. Environmental claims require sufficient evidence."
        values = [
            {"new.txt": {"metadata": {"name": "new.txt"}, "content": body}},
            ({"name": "new.txt", "content": memoryview(body)},),
        ]
        for value in values:
            doc = resolve_regulation("Upload regulation", "v2", value)
            self.assertEqual(doc.filename, "new.txt")
            self.assertEqual(doc.version, "v2")
            self.assertEqual(doc.passages[0].text, body.decode())
        self.assertIsNone(resolve_regulation("No regulation", ""))

    @unittest.skipUnless(importlib.util.find_spec("ipywidgets"), "Optional ipywidgets unavailable")
    def test_compare_case_switch_invalidation_and_failure(self):
        with patch("IPython.display.display"), contextlib.redirect_stdout(io.StringIO()):
            controls = show_review()
            controls["compare_button"].click()
            self.assertEqual(controls["get_report"]()["summary"]["contradicted"], 3)
            controls["case"].value = "C"
            self.assertIsNone(controls["get_report"]())
            controls["compare_button"].click()
            self.assertEqual(controls["get_report"]()["summary"]["supported"], 3)
            controls["source"].value = "Upload regulation"
            controls["compare_button"].click()
            self.assertIsNone(controls["get_report"]())
            self.assertFalse(controls["compare_button"].disabled)
