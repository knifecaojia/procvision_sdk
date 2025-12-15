import json
import os
import subprocess
import sys
import time
import tempfile
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


class TestAdapterHandshake(unittest.TestCase):
    def _make_project(self):
        td = tempfile.TemporaryDirectory()
        base = Path(td.name)
        (base / "algorithm").mkdir(parents=True, exist_ok=True)
        (base / "algorithm" / "__init__.py").write_text("\n")
        (base / "algorithm" / "main.py").write_text(
            "from typing import Any, Dict\n"
            "from procvision_algorithm_sdk import BaseAlgorithm, Session, read_image_from_shared_memory\n"
            "class Algorithm(BaseAlgorithm):\n"
            "    def get_info(self) -> Dict[str, Any]:\n"
            "        return {\"name\": \"algorithm\", \"version\": \"1.0\", \"supported_pids\": [\"D01\"], \"steps\": [{\"index\": 1, \"name\": \"s\", \"params\": []}]}\n"
            "    def pre_execute(self, step_index: int, pid: str, session: Session, user_params: Dict[str, Any], shared_mem_id: str, image_meta: Dict[str, Any]) -> Dict[str, Any]:\n"
            "        return {\"status\": \"OK\", \"message\": \"ok\"}\n"
            "    def execute(self, step_index: int, pid: str, session: Session, user_params: Dict[str, Any], shared_mem_id: str, image_meta: Dict[str, Any]) -> Dict[str, Any]:\n"
            "        return {\"status\": \"OK\", \"data\": {\"result_status\": \"OK\"}}\n"
        )
        (base / "manifest.json").write_text(
            json.dumps({"name": "algorithm", "version": "1.0", "entry_point": "algorithm.main:Algorithm", "supported_pids": ["D01"]}, ensure_ascii=False)
        )
        return td, str(base)

    def test_hello_and_shutdown(self):
        td, project = self._make_project()
        try:
            env = os.environ.copy()
            env["PROC_ALGO_ROOT"] = project
            p = subprocess.Popen([sys.executable, "-m", "procvision_algorithm_sdk.adapter"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=project, env=env)
            time.sleep(0.05)
            hello = _read_frame(p.stdout)
            if hello is None:
                p.terminate()
                return
            self.assertEqual(hello.get("type"), "hello")
            _write_frame(p.stdin, {"type": "hello", "runner_version": "dev"})
            _write_frame(p.stdin, {"type": "shutdown"})
            ack = _read_frame(p.stdout)
            self.assertEqual(ack.get("type"), "shutdown")
            p.terminate()
        finally:
            td.cleanup()


if __name__ == "__main__":
    unittest.main()
