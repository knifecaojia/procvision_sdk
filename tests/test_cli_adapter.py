import json
import os
import tempfile
import unittest
from pathlib import Path
from procvision_algorithm_sdk.cli import init_project, run_adapter, validate_adapter


class TestCliAdapter(unittest.TestCase):
    def _make_project(self):
        td = tempfile.TemporaryDirectory()
        base = Path(td.name)
        init_project("demo_algo", str(base), "D01", "1.0.0", "demo")
        img = base / "test.bin"
        with open(img, "wb") as f:
            f.write(b"\x00\x01demo")
        return td, str(base), str(img)

    def test_validate_full(self):
        td, project, image = self._make_project()
        try:
            report = validate_adapter(project, None)
            self.assertIn(report["summary"]["status"], {"PASS", "FAIL"})
            self.assertIn("checks", report)
        finally:
            td.cleanup()

    def test_run_adapter(self):
        td, project, image = self._make_project()
        try:
            res = run_adapter(project, "D01", image, json.dumps({"threshold": 0.8}), 1, None)
            self.assertIsInstance(res.get("pre_execute"), dict)
            self.assertIsInstance(res.get("execute"), dict)
        finally:
            td.cleanup()


if __name__ == "__main__":
    unittest.main()
