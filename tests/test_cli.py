import unittest
from procvision_algorithm_sdk.cli import validate, run


class TestCLI(unittest.TestCase):
    def test_validate_algorithm_example(self):
        report = validate("./algorithm-example", None, None)
        self.assertIn("summary", report)
        self.assertEqual(report["summary"].get("status"), "PASS")

    def test_run_algorithm_example(self):
        result = run("./algorithm-example", "./spec.md", "./spec.md", 1, "demo", [])
        self.assertIn("execute", result)
        self.assertIn(result["execute"].get("status"), {"OK", "ERROR"})


if __name__ == "__main__":
    unittest.main()
