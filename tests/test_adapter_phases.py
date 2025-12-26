
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

class TestAdapterPhases(unittest.TestCase):
    def test_phases_full_algo(self):
        env = os.environ.copy()
        env["PYTHONPATH"] = os.getcwd()
        cmd = [sys.executable, "-m", "procvision_algorithm_sdk.adapter", "--entry", "tests.mock_phases_algo:FullAlgo"]
        p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
        
        try:
            # 1. Hello
            hello = _read_frame(p.stdout)
            self.assertIsNotNone(hello)
            self.assertEqual(hello["type"], "hello")
            caps = hello.get("capabilities", [])
            self.assertIn("setup", caps)
            self.assertIn("reset", caps)
            self.assertIn("on_step_start", caps)
            self.assertIn("on_step_finish", caps)
            
            # 2. Setup
            _write_frame(p.stdin, {"type": "call", "request_id": "r1", "phase": "setup"})
            res = _read_frame(p.stdout)
            self.assertEqual(res["type"], "result")
            self.assertEqual(res["request_id"], "r1")
            self.assertEqual(res["status"], "OK")
            self.assertEqual(res["data"]["phase"], "setup")

            # 3. Reset
            _write_frame(p.stdin, {"type": "call", "request_id": "r2", "phase": "reset", "session": {"id": "s1"}})
            res = _read_frame(p.stdout)
            self.assertEqual(res["status"], "OK")
            self.assertEqual(res["data"]["phase"], "reset")

            # 4. on_step_start
            _write_frame(p.stdin, {"type": "call", "request_id": "r3", "phase": "on_step_start", "step_index": 1, "session": {"id": "s1"}})
            res = _read_frame(p.stdout)
            self.assertEqual(res["status"], "OK")
            self.assertEqual(res["data"]["phase"], "on_step_start")

            # 5. on_step_finish
            _write_frame(p.stdin, {"type": "call", "request_id": "r4", "phase": "on_step_finish", "step_index": 1, "session": {"id": "s1"}})
            res = _read_frame(p.stdout)
            self.assertEqual(res["status"], "OK")
            self.assertEqual(res["data"]["phase"], "on_step_finish")

            # 6. Teardown
            _write_frame(p.stdin, {"type": "call", "request_id": "r5", "phase": "teardown"})
            res = _read_frame(p.stdout)
            self.assertEqual(res["status"], "OK")
            self.assertEqual(res["data"]["phase"], "teardown")

            # Shutdown
            _write_frame(p.stdin, {"type": "shutdown"})
            ack = _read_frame(p.stdout)
            self.assertEqual(ack["type"], "shutdown")

        finally:
            p.terminate()
            p.wait()

    def test_phases_missing_algo(self):
        env = os.environ.copy()
        env["PYTHONPATH"] = os.getcwd()
        cmd = [sys.executable, "-m", "procvision_algorithm_sdk.adapter", "--entry", "tests.mock_phases_algo:MissingAlgo"]
        p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
        
        try:
            # 1. Hello
            hello = _read_frame(p.stdout)
            self.assertIsNotNone(hello)
            
            # 2. Setup (MissingAlgo doesn't implement setup in the mock file? Wait, I wrote "pass". It HAS setup but it does nothing? No, I defined class MissingAlgo: pass. So it doesn't have setup method.)
            # Wait, I wrote: class MissingAlgo: pass.
            # But earlier I thought I wrote pass in setup.
            # Let's check mock_phases_algo content in previous tool output.
            
            # 3. Reset
            _write_frame(p.stdin, {"type": "call", "request_id": "r1", "phase": "reset", "session": {"id": "s1"}})
            res = _read_frame(p.stdout)
            self.assertEqual(res["type"], "error")
            self.assertEqual(res["request_id"], "r1")
            self.assertIn("does not implement reset", res["message"])

            # Shutdown
            _write_frame(p.stdin, {"type": "shutdown"})
            _read_frame(p.stdout)

        finally:
            p.terminate()
            p.wait()

if __name__ == "__main__":
    unittest.main()
