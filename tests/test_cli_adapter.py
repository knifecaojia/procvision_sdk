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
        init_project("demo_algo", str(base), "1.0.0", "demo")
        cur = base / "cur.bin"
        guide = base / "guide.bin"
        with open(cur, "wb") as f:
            f.write(b"\x00\x01demo")
        with open(guide, "wb") as f:
            f.write(b"\x00\x01demo2")
        return td, str(base), str(cur), str(guide)

    def test_validate_full(self):
        td, project, cur, guide = self._make_project()
        try:
            report = validate_adapter(project, None)
            self.assertIn(report["summary"]["status"], {"PASS", "FAIL"})
            self.assertIn("checks", report)
        finally:
            td.cleanup()

    def test_run_adapter(self):
        td, project, cur, guide = self._make_project()
        try:
            res = run_adapter(project, cur, guide, 1, "demo", [], None)
            self.assertIsInstance(res.get("execute"), dict)
        finally:
            td.cleanup()


if __name__ == "__main__":
    unittest.main()
