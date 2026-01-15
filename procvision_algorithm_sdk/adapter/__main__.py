import argparse
import importlib
import json
import os
import sys
import time
import re
import threading
from typing import Any, Dict, Optional

from ..logger import StructuredLogger
from ..base import BaseAlgorithm
from ..shared_memory import read_image_from_shared_memory

_PROTO_OUT = None


def _now_ms() -> int:
    return int(time.time() * 1000)


def _write_frame(payload: Dict[str, Any]) -> None:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    length = len(data).to_bytes(4, byteorder="big")
    out = _PROTO_OUT or sys.stdout.buffer
    out.write(length + data)
    out.flush()


def _read_exact(n: int) -> Optional[bytes]:
    buf = b""
    while len(buf) < n:
        chunk = sys.stdin.buffer.read(n - len(buf))
        if not chunk:
            return None
        buf += chunk
    return buf


def _read_frame() -> Optional[Dict[str, Any]]:
    h = _read_exact(4)
    if h is None:
        return None
    ln = int.from_bytes(h, byteorder="big")
    if ln <= 0:
        return None
    body = _read_exact(ln)
    if body is None:
        return None
    try:
        return json.loads(body.decode("utf-8"))
    except Exception:
        return None


def _get_sdk_version() -> str:
    try:
        import importlib.metadata as md  # type: ignore
        return md.version("procvision_algorithm_sdk")
    except Exception:
        return "unknown"


def _discover_entry(cli_entry: Optional[str]) -> Optional[str]:
    if cli_entry:
        return cli_entry
    env_ep = os.environ.get("PROC_ENTRY_POINT")
    if env_ep:
        return env_ep
    roots = [os.getcwd(), os.environ.get("PROC_ALGO_ROOT") or os.getcwd()]
    for root in roots:
        if not root:
            continue
        mj = os.path.join(root, "manifest.json")
        if os.path.isfile(mj):
            try:
                with open(mj, "r", encoding="utf-8") as f:
                    mf = json.load(f)
                ep = mf.get("entry_point")
                if isinstance(ep, str) and ":" in ep:
                    return ep
            except Exception:
                pass
        my = os.path.join(root, "manifest.yaml")
        if os.path.isfile(my):
            try:
                with open(my, "r", encoding="utf-8") as f:
                    text = f.read()
                m = re.search(r"entry_point\s*:\s*([\w\.]+:[\w\.]+)", text)
                if m:
                    return m.group(1)
            except Exception:
                pass
        pt = os.path.join(root, "pyproject.toml")
        if os.path.isfile(pt):
            try:
                with open(pt, "r", encoding="utf-8") as f:
                    lines = f.read().splitlines()
                idx = None
                for i, line in enumerate(lines):
                    if line.strip().startswith("[tool.procvision.algorithm]"):
                        idx = i
                        break
                if idx is not None:
                    for j in range(idx + 1, len(lines)):
                        s = lines[j].strip()
                        if s.startswith("["):
                            break
                        if s.startswith("entry_point") and "=" in s:
                            val = s.split("=", 1)[1].strip().strip("\"'")
                            if ":" in val:
                                return val
            except Exception:
                pass
    default_mod = "algorithm.main:Algorithm"
    try:
        mname, cname = default_mod.split(":", 1)
        importlib.import_module(mname)
        return default_mod
    except Exception:
        return None


def _import_entry(ep: str) -> BaseAlgorithm:
    m, c = ep.split(":", 1)
    mod = importlib.import_module(m)
    cls = getattr(mod, c)
    inst = cls()
    return inst


def _send_hello() -> None:
    _write_frame({
        "type": "hello",
        "sdk_version": _get_sdk_version(),
        "timestamp_ms": _now_ms(),
        "capabilities": [
            "ping",
            "call",
            "shutdown",
            "shared_memory:v1",
            "execute"
        ]
    })


def _send_pong(req: Dict[str, Any]) -> None:
    rid = req.get("request_id")
    _write_frame({"type": "pong", "request_id": rid, "timestamp_ms": _now_ms(), "status": "OK"})


def _send_error(message: str, code: str, rid: Optional[str]) -> None:
    _write_frame({"type": "error", "request_id": rid, "timestamp_ms": _now_ms(), "status": "ERROR", "message": message, "error_code": code})


def _send_shutdown_ack() -> None:
    _write_frame({"type": "shutdown", "timestamp_ms": _now_ms(), "status": "OK"})


def _result_from(status: str, message: str, rid: str, step_index: int, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return {"type": "result", "request_id": rid, "timestamp_ms": _now_ms(), "status": status, "message": message, "data": {"step_index": step_index, **(data or {})}}


def main() -> None:
    parser = argparse.ArgumentParser(prog="procvision-adapter")
    parser.add_argument("--entry", type=str, default=None)
    parser.add_argument("--log-level", type=str, default=os.environ.get("PROC_LOG_LEVEL", "info"))
    parser.add_argument("--heartbeat-interval-ms", type=int, default=int(os.environ.get("PROC_HEARTBEAT_INTERVAL_MS", "5000")))
    parser.add_argument("--heartbeat-grace-ms", type=int, default=int(os.environ.get("PROC_HEARTBEAT_GRACE_MS", "2000")))
    args = parser.parse_args()

    logger = StructuredLogger()
    global _PROTO_OUT
    _PROTO_OUT = os.fdopen(os.dup(1), "wb", closefd=True)
    strict_stdio = str(os.environ.get("PROC_STRICT_STDIO") or "").strip().lower() in {"1", "true", "yes", "on"}
    stdout_guard = {"active": False, "bytes": 0, "preview": b""}
    guard_lock = threading.Lock()
    guard_thread = None

    if strict_stdio:
        r_fd, w_fd = os.pipe()
        try:
            os.dup2(w_fd, 1)
        finally:
            try:
                os.close(w_fd)
            except Exception:
                pass
        try:
            sys.stdout.reconfigure(line_buffering=True, write_through=True)
        except Exception:
            pass

        def _stdout_reader() -> None:
            while True:
                try:
                    chunk = os.read(r_fd, 4096)
                except Exception:
                    break
                if not chunk:
                    break
                try:
                    os.write(2, chunk)
                except Exception:
                    pass
                with guard_lock:
                    if stdout_guard["active"]:
                        stdout_guard["bytes"] += len(chunk)
                        if len(stdout_guard["preview"]) < 4096:
                            remain = 4096 - len(stdout_guard["preview"])
                            stdout_guard["preview"] += chunk[:remain]

        guard_thread = threading.Thread(target=_stdout_reader, daemon=True)
        guard_thread.start()
    else:
        try:
            os.dup2(2, 1)
        except Exception:
            pass

    _send_hello()

    ep = _discover_entry(args.entry)
    if not ep:
        _send_error("entry_point not found", "1004", None)
        return
    try:
        alg = _import_entry(ep)
    except Exception as e:
        _send_error(str(e), "1000", None)
        return

    running = False
    try:
        while True:
            msg = _read_frame()
            if msg is None:
                break
            t = msg.get("type")
            if t == "ping":
                _send_pong(msg)
                continue
            if t == "hello":
                continue
            if t == "shutdown":
                _send_shutdown_ack()
                break
            if t == "call":
                if running:
                    _send_error("busy", "1000", msg.get("request_id"))
                    continue
                running = True
                try:
                    rid = msg.get("request_id") or ""
                    d = msg.get("data", {})
                    step_index = int(d.get("step_index") or msg.get("step_index") or 1)
                    step_desc = str(d.get("step_desc") or msg.get("step_desc") or "")
                    guide_info = d.get("guide_info") if "guide_info" in d else msg.get("guide_info")
                    if guide_info is None:
                        guide_info = []
                    cur_image_shm_id = str(d.get("cur_image_shm_id") or msg.get("cur_image_shm_id") or "")
                    cur_image_meta = d.get("cur_image_meta") or msg.get("cur_image_meta") or {}
                    guide_image_shm_id = str(d.get("guide_image_shm_id") or msg.get("guide_image_shm_id") or "")
                    guide_image_meta = d.get("guide_image_meta") or msg.get("guide_image_meta") or {}
                    if not cur_image_shm_id or not guide_image_shm_id:
                        _send_error("missing cur_image_shm_id/guide_image_shm_id", "1000", rid)
                        continue
                    cur_image = read_image_from_shared_memory(cur_image_shm_id, cur_image_meta)
                    guide_image = read_image_from_shared_memory(guide_image_shm_id, guide_image_meta)
                    if strict_stdio:
                        with guard_lock:
                            stdout_guard["active"] = True
                            stdout_guard["bytes"] = 0
                            stdout_guard["preview"] = b""
                    res = alg.execute(step_index, step_desc, cur_image, guide_image, guide_info)
                    out_bytes = 0
                    out_preview = b""
                    if strict_stdio:
                        try:
                            sys.stdout.flush()
                        except Exception:
                            pass
                        time.sleep(0.02)
                        with guard_lock:
                            out_bytes = int(stdout_guard["bytes"])
                            out_preview = bytes(stdout_guard["preview"])
                            stdout_guard["active"] = False
                    if strict_stdio and out_bytes > 0:
                        sample = ""
                        try:
                            sample = out_preview.decode("utf-8", errors="replace")
                        except Exception:
                            sample = ""
                        logger.error("stdout_contaminated", stdout_bytes=out_bytes, sample=sample)
                        _send_error("stdout 污染：禁止向 stdout 输出，请改用 stderr/StructuredLogger", "1010", rid)
                        continue
                    if isinstance(res, dict):
                        st = res.get("status") or "OK"
                        msg_text = res.get("message") or ""
                        data = res.get("data") or {}
                        _write_frame(_result_from(st, msg_text, rid, step_index, data))
                    else:
                        _send_error("invalid execute return", "1000", rid)
                except Exception as e:
                    _send_error(str(e), "1009", msg.get("request_id"))
                finally:
                    running = False
                continue
    except KeyboardInterrupt:
        pass
    try:
        if strict_stdio:
            try:
                os.close(r_fd)
            except Exception:
                pass
        if guard_thread is not None:
            guard_thread.join(timeout=0.2)
    except Exception:
        pass


if __name__ == "__main__":
    main()
