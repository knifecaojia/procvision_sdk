
import json
import os
import subprocess
import sys
import time
import unittest
from pathlib import Path

def _write_frame(fp, obj):
    data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    fp.write(len(data).to_bytes(4, byteorder="big") + data)
    fp.flush()

def _read_exact(fp, n):
    b = b""
    while len(b) < n:
        chunk = fp.read(n - len(b))
        if not chunk:
            return None
        b += chunk
    return b

def _read_frame(fp):
    h = _read_exact(fp, 4)
    if h is None:
        return None
    ln = int.from_bytes(h, byteorder="big")
    body = _read_exact(fp, ln)
    if body is None:
        return None
    return json.loads(body.decode("utf-8"))

class TestAdapterExecute(unittest.TestCase):
    def test_execute_ok(self):
        env = os.environ.copy()
        env["PYTHONPATH"] = os.getcwd()
        cmd = [sys.executable, "-m", "procvision_algorithm_sdk.adapter", "--entry", "tests.mock_phases_algo:ExecuteAlgo"]
        p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
        
        try:
            hello = _read_frame(p.stdout)
            self.assertIsNotNone(hello)
            self.assertEqual(hello["type"], "hello")
            caps = hello.get("capabilities", [])
            self.assertIn("execute", caps)

            _write_frame(
                p.stdin,
                {
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
                },
            )
            res = _read_frame(p.stdout)
            self.assertEqual(res["type"], "result")
            self.assertEqual(res["request_id"], "r1")
            self.assertEqual(res["status"], "OK")
            self.assertEqual(res["data"]["result_status"], "OK")

            _write_frame(p.stdin, {"type": "shutdown"})
            ack = _read_frame(p.stdout)
            self.assertEqual(ack["type"], "shutdown")

        finally:
            p.terminate()
            p.wait()
            try:
                if p.stdin:
                    p.stdin.close()
                if p.stdout:
                    p.stdout.close()
                if p.stderr:
                    p.stderr.close()
            except Exception:
                pass

    def test_execute_missing(self):
        env = os.environ.copy()
        env["PYTHONPATH"] = os.getcwd()
        cmd = [sys.executable, "-m", "procvision_algorithm_sdk.adapter", "--entry", "tests.mock_phases_algo:MissingExecuteAlgo"]
        p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
        
        try:
            hello = _read_frame(p.stdout)
            self.assertIsNotNone(hello)

            _write_frame(
                p.stdin,
                {
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
                },
            )
            res = _read_frame(p.stdout)
            self.assertEqual(res["type"], "error")
            self.assertEqual(res["request_id"], "r1")
            self.assertTrue(bool(res.get("message")))

            _write_frame(p.stdin, {"type": "shutdown"})
            _read_frame(p.stdout)

        finally:
            p.terminate()
            p.wait()
            try:
                if p.stdin:
                    p.stdin.close()
                if p.stdout:
                    p.stdout.close()
                if p.stderr:
                    p.stderr.close()
            except Exception:
                pass

if __name__ == "__main__":
    unittest.main()
