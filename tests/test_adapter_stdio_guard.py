import os
import subprocess
import sys
import unittest

from tests.test_adapter_phases import _read_frame, _write_frame


class TestAdapterStdioGuard(unittest.TestCase):
    def _call_payload(self):
        return {
            "type": "call",
            "request_id": "r1",
            "data": {
                "step_index": 1,
                "step_desc": "step-1",
                "guide_info": [],
                "cur_image_shm_id": "dev-shm:s1:cur",
                "cur_image_meta": {"width": 1, "height": 1, "timestamp_ms": 0, "camera_id": "c"},
                "guide_image_shm_id": "dev-shm:s1:guide",
                "guide_image_meta": {"width": 1, "height": 1, "timestamp_ms": 0, "camera_id": "c"},
            },
        }

    def test_stdout_spam_not_break_protocol_default(self):
        env = os.environ.copy()
        env["PYTHONPATH"] = os.getcwd()
        cmd = [sys.executable, "-m", "procvision_algorithm_sdk.adapter", "--entry", "tests.mock_phases_algo:StdoutSpamAlgo"]
        p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
        try:
            hello = _read_frame(p.stdout)
            self.assertIsNotNone(hello)
            self.assertEqual(hello["type"], "hello")
            _write_frame(p.stdin, {"type": "hello", "runner_version": "dev", "heartbeat_interval_ms": 5000, "heartbeat_grace_ms": 2000})
            _write_frame(p.stdin, self._call_payload())
            res = _read_frame(p.stdout)
            self.assertEqual(res["type"], "result")
            self.assertEqual(res["status"], "OK")
            _write_frame(p.stdin, {"type": "shutdown"})
            _read_frame(p.stdout)
        finally:
            try:
                p.terminate()
            except Exception:
                pass
            try:
                p.wait(timeout=1.0)
            except Exception:
                pass
            try:
                if p.stdin:
                    p.stdin.close()
                if p.stdout:
                    p.stdout.close()
                if p.stderr:
                    p.stderr.close()
            except Exception:
                pass

    def test_stdout_spam_fails_in_strict_mode(self):
        env = os.environ.copy()
        env["PYTHONPATH"] = os.getcwd()
        env["PROC_STRICT_STDIO"] = "1"
        cmd = [sys.executable, "-m", "procvision_algorithm_sdk.adapter", "--entry", "tests.mock_phases_algo:StdoutSpamAlgo"]
        p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
        try:
            hello = _read_frame(p.stdout)
            self.assertIsNotNone(hello)
            _write_frame(p.stdin, {"type": "hello", "runner_version": "dev", "heartbeat_interval_ms": 5000, "heartbeat_grace_ms": 2000})
            _write_frame(p.stdin, self._call_payload())
            res = _read_frame(p.stdout)
            self.assertEqual(res["type"], "error")
            self.assertEqual(res.get("error_code"), "1010")
            _write_frame(p.stdin, {"type": "shutdown"})
            _read_frame(p.stdout)
        finally:
            try:
                p.terminate()
            except Exception:
                pass
            try:
                p.wait(timeout=1.0)
            except Exception:
                pass
            try:
                if p.stdin:
                    p.stdin.close()
                if p.stdout:
                    p.stdout.close()
                if p.stderr:
                    p.stderr.close()
            except Exception:
                pass
