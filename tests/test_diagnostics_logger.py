import io
import json
import unittest
from procvision_algorithm_sdk.diagnostics import Diagnostics
from procvision_algorithm_sdk.logger import StructuredLogger


class TestDiagnosticsLogger(unittest.TestCase):
    def test_diagnostics_publish_get(self):
        d = Diagnostics()
        d.publish("k", 1)
        d.publish("m", {"a": 2})
        g = d.get()
        self.assertEqual(g.get("k"), 1)
        self.assertEqual(g.get("m").get("a"), 2)

    def test_structured_logger_json_line(self):
        buf = io.StringIO()
        log = StructuredLogger(sink=buf)
        log.info("hello", step_index=1)
        text = buf.getvalue().strip()
        obj = json.loads(text)
        self.assertEqual(obj.get("message"), "hello")
        self.assertEqual(obj.get("level"), "info")
        self.assertEqual(obj.get("step_index"), 1)
        self.assertIsInstance(obj.get("timestamp_ms"), int)


if __name__ == "__main__":
    unittest.main()
