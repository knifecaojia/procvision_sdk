import argparse
import importlib
import json
import os
import sys
import time
import re
from typing import Any, Dict, Optional

from ..logger import StructuredLogger
from ..base import BaseAlgorithm
from ..session import Session


def _now_ms() -> int:
    return int(time.time() * 1000)


def _write_frame(payload: Dict[str, Any]) -> None:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    length = len(data).to_bytes(4, byteorder="big")
    sys.stdout.buffer.write(length + data)
    sys.stdout.buffer.flush()


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
    _write_frame({"type": "hello", "sdk_version": _get_sdk_version(), "timestamp_ms": _now_ms(), "capabilities": ["ping", "call", "shutdown", "shared_memory:v1", "info"]})


def _send_pong(req: Dict[str, Any]) -> None:
    rid = req.get("request_id")
    _write_frame({"type": "pong", "request_id": rid, "timestamp_ms": _now_ms(), "status": "OK"})


def _send_error(message: str, code: str, rid: Optional[str]) -> None:
    _write_frame({"type": "error", "request_id": rid, "timestamp_ms": _now_ms(), "status": "ERROR", "message": message, "error_code": code})


def _send_shutdown_ack() -> None:
    _write_frame({"type": "shutdown", "timestamp_ms": _now_ms(), "status": "OK"})


def _result_from(status: str, message: str, rid: str, phase: str, step_index: int, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return {"type": "result", "request_id": rid, "timestamp_ms": _now_ms(), "status": status, "message": message, "data": {"phase": phase, "step_index": step_index, **(data or {})}}


def main() -> None:
    parser = argparse.ArgumentParser(prog="procvision-adapter")
    parser.add_argument("--entry", type=str, default=None)
    parser.add_argument("--log-level", type=str, default=os.environ.get("PROC_LOG_LEVEL", "info"))
    parser.add_argument("--heartbeat-interval-ms", type=int, default=int(os.environ.get("PROC_HEARTBEAT_INTERVAL_MS", "5000")))
    parser.add_argument("--heartbeat-grace-ms", type=int, default=int(os.environ.get("PROC_HEARTBEAT_GRACE_MS", "2000")))
    args = parser.parse_args()

    logger = StructuredLogger()
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
        try:
            alg.setup()
        except Exception:
            pass
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
                try:
                    alg.teardown()
                except Exception:
                    pass
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
                    phase = d.get("phase") or msg.get("phase") or "execute"
                    step_index = int(d.get("step_index") or msg.get("step_index") or 1)
                    pid = d.get("pid") or msg.get("pid") or ""
                    session_info = d.get("session") or msg.get("session") or {}
                    session = Session(session_info.get("id", "session"), session_info.get("context", {}))
                    user_params = d.get("user_params") or msg.get("user_params") or {}
                    shared_mem_id = d.get("shared_mem_id") or msg.get("shared_mem_id") or ""
                    image_meta = d.get("image_meta") or msg.get("image_meta") or {}
                    try:
                        alg.on_step_start(step_index, session, {"pid": pid, "trace_id": session.context.get("trace_id")})
                    except Exception:
                        pass
                    if phase == "info":
                        info = alg.get_info()
                        if isinstance(info, dict):
                            _write_frame(_result_from("OK", "", rid, "info", 0, {"info": info}))
                        else:
                            _send_error("invalid get_info return", "1000", rid)
                    elif phase == "pre":
                        res = alg.pre_execute(step_index, pid, session, user_params, shared_mem_id, image_meta)
                        if isinstance(res, dict):
                            st = res.get("status") or "OK"
                            msg_text = res.get("message") or ""
                            data = res.get("data") or {}
                            _write_frame(_result_from(st, msg_text, rid, "pre", step_index, data))
                        else:
                            _send_error("invalid pre_execute return", "1000", rid)
                    else:
                        res = alg.execute(step_index, pid, session, user_params, shared_mem_id, image_meta)
                        if isinstance(res, dict):
                            st = res.get("status") or "OK"
                            msg_text = res.get("message") or ""
                            data = res.get("data") or {}
                            _write_frame(_result_from(st, msg_text, rid, "execute", step_index, data))
                        else:
                            _send_error("invalid execute return", "1000", rid)
                    try:
                        alg.on_step_finish(step_index, session, res if isinstance(res, dict) else {})
                    except Exception:
                        pass
                except Exception as e:
                    _send_error(str(e), "1009", msg.get("request_id"))
                finally:
                    running = False
                continue
        try:
            alg.teardown()
        except Exception:
            pass
    except KeyboardInterrupt:
        try:
            alg.teardown()
        except Exception:
            pass


if __name__ == "__main__":
    main()
