import argparse
import importlib
import json
import os
import sys
import time
import zipfile
import subprocess
import shutil
import uuid
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base import BaseAlgorithm
from .session import Session
from .shared_memory import dev_write_image_to_shared_memory


def _load_manifest(manifest_path: str) -> Dict[str, Any]:
    with open(manifest_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _import_entry(entry_point: str, sys_path: Optional[str]) -> Any:
    if sys_path and sys_path not in sys.path:
        sys.path.insert(0, sys_path)
    module_name, class_name = entry_point.split(":", 1)
    module = importlib.import_module(module_name)
    cls = getattr(module, class_name)
    return cls


def _add(checks: List[Dict[str, Any]], name: str, ok: bool, message: str = "") -> None:
    checks.append({"name": name, "result": "PASS" if ok else "FAIL", "message": message})


def validate(project: Optional[str], manifest: Optional[str], zip_path: Optional[str]) -> Dict[str, Any]:
    checks: List[Dict[str, Any]] = []

    manifest_path = manifest or (os.path.join(project, "manifest.json") if project else None)
    project_sys_path = project
    if (not manifest_path or not os.path.exists(manifest_path)) and project:
        base_dir = os.path.dirname(__file__)
        root = os.path.abspath(os.path.join(base_dir, os.pardir))
        alt_manifest = os.path.join(os.path.join(root, project), "manifest.json")
        if os.path.exists(alt_manifest):
            manifest_path = alt_manifest
            project_sys_path = os.path.join(root, project)
    if not manifest_path or not os.path.exists(manifest_path):
        _add(checks, "manifest_exists", False, "manifest.json not found")
        summary = {"status": "FAIL", "passed": 0, "failed": 1}
        return {"summary": summary, "checks": checks}

    try:
        mf = _load_manifest(manifest_path)
        _add(checks, "manifest_load", True, "loaded")
    except Exception as e:
        _add(checks, "manifest_load", False, str(e))
        summary = {"status": "FAIL", "passed": 1, "failed": 1}
        return {"summary": summary, "checks": checks}

    required = ["name", "version", "entry_point", "supported_pids"]
    missing = [k for k in required if k not in mf]
    _add(checks, "manifest_fields", len(missing) == 0, ",".join(missing))

    entry_point = mf.get("entry_point", "")
    try:
        cls = _import_entry(entry_point, project_sys_path)
        ok = issubclass(cls, BaseAlgorithm)
        _add(checks, "entry_import", ok, "imported")
    except Exception as e:
        _add(checks, "entry_import", False, str(e))
        cls = None

    if cls:
        try:
            alg = cls()
            try:
                alg.setup()
            except Exception:
                pass
            info = alg.get_info()
            steps_ok = isinstance(info, dict) and isinstance(info.get("steps", []), list)
            _add(checks, "get_info", isinstance(info, dict), "dict returned")
            _add(checks, "step_schema", steps_ok, "steps present")

            mf_pids = mf.get("supported_pids", [])
            info_pids = info.get("supported_pids", [])
            _add(checks, "supported_pids_match", mf_pids == info_pids, f"manifest={mf_pids} info={info_pids}")

            pid = (mf_pids or ["A01"])[0]
            session = Session("session-demo", {"product_code": pid, "operator": "dev", "trace_id": "trace-demo"})
            image_meta = {"width": 640, "height": 480, "timestamp_ms": int(time.time() * 1000), "camera_id": "cam-dev"}
            try:
                alg.on_step_start(1, session, {"pid": pid, "trace_id": session.context.get("trace_id")})
            except Exception:
                pass
            pre = alg.pre_execute(1, pid, session, {}, f"dev-shm:{session.id}", image_meta)
            _add(checks, "pre_execute_return_dict", isinstance(pre, dict), "dict")
            pre_status = pre.get("status")
            _add(checks, "pre_status_valid", pre_status in {"OK", "ERROR"}, str(pre_status))
            _add(checks, "pre_message_present", bool(pre.get("message")), str(pre.get("message")))

            exe = alg.execute(1, pid, session, {}, f"dev-shm:{session.id}", image_meta)
            _add(checks, "execute_return_dict", isinstance(exe, dict), "dict")
            exe_status = exe.get("status")
            _add(checks, "execute_status_valid", exe_status in {"OK", "ERROR"}, str(exe_status))
            if exe_status == "OK":
                data = exe.get("data", {})
                rs = data.get("result_status")
                _add(checks, "execute_result_status_valid", rs in {"OK", "NG", None}, str(rs))
                if rs == "NG":
                    ng_reason_ok = "ng_reason" in data and bool(data.get("ng_reason"))
                    _add(checks, "ng_reason_present", ng_reason_ok, str(data.get("ng_reason")))
                    dr = data.get("defect_rects", [])
                    _add(checks, "defect_rects_type", isinstance(dr, list), f"len={len(dr)}")
                    _add(checks, "defect_rects_count_limit", len(dr) <= 20, f"len={len(dr)}")
            try:
                alg.on_step_finish(1, session, exe if isinstance(exe, dict) else {})
            except Exception:
                pass
            try:
                alg.teardown()
            except Exception:
                pass
        except Exception as e:
            _add(checks, "smoke_execute", False, str(e))

    if zip_path:
        try:
            with zipfile.ZipFile(zip_path, "r") as z:
                names = set(z.namelist())
                m1 = any(n.endswith("manifest.json") for n in names)
                m2 = any(n.endswith("requirements.txt") for n in names)
                m3 = any(n.endswith("/wheels/") or "/wheels/" in n for n in names)
                _add(checks, "zip_manifest", m1, "manifest")
                _add(checks, "zip_requirements", m2, "requirements")
                _add(checks, "zip_wheels", m3, "wheels")
        except Exception as e:
            _add(checks, "zip_open", False, str(e))

    passed = sum(1 for c in checks if c["result"] == "PASS")
    failed = sum(1 for c in checks if c["result"] == "FAIL")
    status = "PASS" if failed == 0 else "FAIL"
    return {"summary": {"status": status, "passed": passed, "failed": failed}, "checks": checks}


def _print_validate_human(report: Dict[str, Any]) -> None:
    summary = report.get("summary", {})
    checks = report.get("checks", [])
    status = summary.get("status", "FAIL")
    print(f"校验结果: {status} | 通过: {summary.get('passed', 0)} | 失败: {summary.get('failed', 0)}")
    for c in checks:
        r = c.get("result")
        name = c.get("name")
        msg = c.get("message")
        marker = "✅" if r == "PASS" else "❌"
        if msg:
            print(f"{marker} {name}: {msg}")
        else:
            print(f"{marker} {name}")


def run(project: str, pid: str, image_path: str, params_json: Optional[str], step_index: Optional[int] = None) -> Dict[str, Any]:
    manifest_path = os.path.join(project, "manifest.json")
    mf = _load_manifest(manifest_path)
    cls = _import_entry(mf["entry_point"], project)
    alg = cls()
    session = Session(
        f"session-{int(time.time()*1000)}",
        {"product_code": pid, "operator": "dev", "trace_id": f"trace-{int(time.time()*1000)}"},
    )
    shared_mem_id = f"dev-shm:{session.id}"
    try:
        with open(image_path, "rb") as f:
            data = f.read()
        dev_write_image_to_shared_memory(shared_mem_id, data)
    except Exception:
        pass

    try:
        import PIL.Image as Image  # type: ignore
        img = Image.open(image_path)
        width, height = img.size
    except Exception:
        width, height = 640, 480

    image_meta = {"width": int(width), "height": int(height), "timestamp_ms": int(time.time() * 1000), "camera_id": "cam-dev"}
    try:
        user_params = json.loads(params_json) if params_json else {}
    except Exception:
        user_params = {}

    sidx = int(step_index) if step_index is not None else 1
    try:
        alg.setup()
    except Exception:
        pass
    try:
        alg.on_step_start(sidx, session, {"pid": pid, "trace_id": session.context.get("trace_id")})
    except Exception:
        pass
    pre = alg.pre_execute(sidx, pid, session, user_params, shared_mem_id, image_meta)
    exe = alg.execute(sidx, pid, session, user_params, shared_mem_id, image_meta)
    try:
        alg.on_step_finish(sidx, session, exe if isinstance(exe, dict) else {})
    except Exception:
        pass
    try:
        alg.teardown()
    except Exception:
        pass
    return {"pre_execute": pre, "execute": exe}


def _print_run_human(result: Dict[str, Any]) -> None:
    pre = result.get("pre_execute", {})
    exe = result.get("execute", {})
    print("预执行:")
    print(f"  status: {pre.get('status')} | message: {pre.get('message')}")
    data = exe.get("data", {})
    print("执行:")
    print(f"  status: {exe.get('status')} | result_status: {data.get('result_status')}")
    if data.get("result_status") == "NG":
        print(f"  ng_reason: {data.get('ng_reason')}")
        dr = data.get("defect_rects", [])
        print(f"  defect_rects: {len(dr)}")


def package(
    project: str,
    output: Optional[str],
    requirements: Optional[str],
    auto_freeze: bool,
    wheels_platform: Optional[str],
    python_version: Optional[str],
    implementation: Optional[str],
    abi: Optional[str],
    skip_download: bool,
    embed_python: bool,
    python_runtime: Optional[str],
    runtime_python_version: Optional[str],
    runtime_abi: Optional[str],
) -> Dict[str, Any]:
    manifest_path = os.path.join(project, "manifest.json")
    mf = _load_manifest(manifest_path)
    name = mf.get("name", "algorithm")
    version = mf.get("version", "0.0.0")
    zip_name = output or f"{name}-v{version}-offline.zip"
    req_path = requirements or os.path.join(project, "requirements.txt")
    # 读取项目环境配置（用于 wheels 与运行时）
    cfg: Dict[str, Any] = {}
    cfg_path = os.path.join(project, ".procvision_env.json")
    if os.path.isfile(cfg_path):
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception:
            cfg = {}
    if not os.path.isfile(req_path):
        if auto_freeze:
            try:
                text = subprocess.check_output([sys.executable, "-m", "pip", "freeze"], text=True)
                with open(req_path, "w", encoding="utf-8") as f:
                    f.write(text)
            except Exception as e:
                return {"status": "ERROR", "message": str(e)}
        else:
            return {"status": "ERROR", "message": "requirements.txt 不存在，请提供 --requirements 或使用 --auto-freeze"}
    sanitized_req = os.path.join(project, "requirements.sanitized.txt")
    try:
        with open(req_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        sanitized_lines: List[str] = []
        for line in lines:
            s = line.strip()
            if not s:
                continue
            s = s.split("#sha256=")[0].strip()
            parts = s.split()
            parts = [p for p in parts if not p.startswith("--hash=")]
            s = " ".join(parts)
            sanitized_lines.append(s + "\n")
        with open(sanitized_req, "w", encoding="utf-8") as f:
            f.writelines(sanitized_lines)
        req_path = sanitized_req
    except Exception:
        pass
    wheels_dir = os.path.join(project, "wheels")
    os.makedirs(wheels_dir, exist_ok=True)
    if not skip_download:
        cmd = [
            sys.executable,
            "-m",
            "pip",
            "download",
            "-r",
            req_path,
            "-d",
            wheels_dir,
        ]
        wp = wheels_platform or cfg.get("wheels_platform") or "win_amd64"
        pv = python_version or cfg.get("python_version") or "3.10"
        impl = implementation or cfg.get("implementation") or "cp"
        ab = abi or cfg.get("abi") or "cp310"
        cmd += ["--platform", wp, "--python-version", pv, "--implementation", impl, "--abi", ab]
        cmd += ["--only-binary=:all:"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            output = (res.stderr or "") + ("\n" + res.stdout if res.stdout else "")
            hint = ""
            if "No matching distribution found" in output:
                hint = "\n提示: 请确保 requirements 版本在目标环境 (python=" + pv + ", abi=" + ab + ") 有可用的 wheel；建议在目标 Python 版本的虚拟环境中执行 pip freeze 生成 requirements.txt。"
            return {"status": "ERROR", "message": (output.strip() or "pip download 失败") + hint}
    base = os.path.abspath(project)
    zip_path = os.path.abspath(zip_name)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for root, dirs, files in os.walk(base):
            rel_root = os.path.relpath(root, base)
            if rel_root.startswith(".venv"):
                continue
            if rel_root.startswith("wheels"):
                continue
            for f in files:
                p = os.path.join(root, f)
                arc = os.path.join(os.path.basename(base), rel_root, f)
                z.write(p, arcname=arc)
        for root, dirs, files in os.walk(wheels_dir):
            for f in files:
                p = os.path.join(root, f)
                rel = os.path.relpath(p, base)
                z.write(p, arcname=rel)
        # 运行时参数默认化与自动发现
        def _discover_python_runtime_dir(project_dir: str, cfg_obj: Dict[str, Any], explicit: Optional[str]) -> Optional[str]:
            if explicit and os.path.isdir(explicit):
                return explicit
            env_dir = os.environ.get("PROC_PYTHON_RUNTIME")
            if env_dir and os.path.isdir(env_dir):
                return env_dir
            cfg_dir = cfg_obj.get("python_runtime")
            if cfg_dir and os.path.isdir(cfg_dir):
                return cfg_dir
            candidates: List[str] = []
            # common relative locations
            for rel in ["python_runtime", "runtime/python", "runtime/python_runtime", "py_runtime", "python"]:
                p = os.path.join(project_dir, rel)
                if os.path.isdir(p):
                    candidates.append(p)
            # also check in parent directory (workspace-level .venv or runtime)
            parent_dir = os.path.dirname(project_dir)
            if parent_dir and os.path.isdir(parent_dir):
                for rel in [".venv", "python_runtime", "runtime/python"]:
                    p = os.path.join(parent_dir, rel)
                    if os.path.isdir(p):
                        candidates.append(p)
            # scan project subdirs for python.exe (Windows embeddable)
            for root, dirs, files in os.walk(project_dir):
                rel_root = os.path.relpath(root, project_dir)
                if "python.exe" in files:
                    # prefer venv root when python.exe is under .venv\Scripts
                    if os.path.basename(root).lower() == "scripts" and ".venv" in root.replace("/", "\\"):
                        venv_root = os.path.dirname(root)
                        candidates.append(venv_root)
                    else:
                        candidates.append(root)
            # scan parent top-level dirs for python.exe (avoid deep recursion for performance)
            try:
                for entry in os.listdir(parent_dir):
                    p = os.path.join(parent_dir, entry)
                    if not os.path.isdir(p):
                        continue
                    # common venv or runtime locations
                    if os.path.isfile(os.path.join(p, "python.exe")) or os.path.isfile(os.path.join(p, "Scripts", "python.exe")):
                        # .venv root preferred
                        if os.path.basename(p).lower() == ".venv":
                            candidates.append(p)
                        else:
                            candidates.append(p)
            except Exception:
                pass
            for c in candidates:
                if (
                    os.path.isfile(os.path.join(c, "python.exe"))  # embeddable/runtime root (Windows)
                    or os.path.isfile(os.path.join(c, "Scripts", "python.exe"))  # venv (Windows)
                    or os.path.isfile(os.path.join(c, "bin", "python"))  # venv (Linux/Mac)
                ):
                    return c
            return None

        runtime_dir = _discover_python_runtime_dir(base, cfg, python_runtime)
        runtime_pyver = runtime_python_version or cfg.get("python_version") or python_version or f"{sys.version_info.major}.{sys.version_info.minor}"
        runtime_pyabi = runtime_abi or cfg.get("abi") or abi or f"cp{sys.version_info.major}{sys.version_info.minor}"
        bootstrap = {
            "has_embedded_python": bool(embed_python and runtime_dir),
            "python_version": runtime_pyver,
            "abi": runtime_pyabi,
            "implementation": implementation or "",
        }
        z.writestr(os.path.join(os.path.basename(base), "deploy_bootstrap.json"), json.dumps(bootstrap, ensure_ascii=False, indent=2))
        if embed_python:
            if not runtime_dir:
                return {
                    "status": "ERROR",
                    "message": "未找到 Python 运行时目录。建议：在当前项目及子目录放置包含 python.exe 的运行时目录，或使用 --python-runtime 指定，或设置环境变量 PROC_PYTHON_RUNTIME，或在 .procvision_env.json 配置 python_runtime",
                }
            if not os.path.isdir(runtime_dir):
                return {"status": "ERROR", "message": f"python_runtime 目录不存在: {runtime_dir}"}
            for root, dirs, files in os.walk(runtime_dir):
                rel_root = os.path.relpath(root, runtime_dir)
                for f in files:
                    p = os.path.join(root, f)
                    arc = os.path.join(os.path.basename(base), "python_runtime", rel_root, f) if rel_root != "." else os.path.join(os.path.basename(base), "python_runtime", f)
                    z.write(p, arcname=arc)
    return {"status": "OK", "zip": zip_path}


def _sanitize_module_name(name: str) -> str:
    import re
    s = name.strip().lower()
    s = re.sub(r"[^a-z0-9_]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s or "algorithm"


def _class_name_from(name: str) -> str:
    import re
    parts = re.split(r"[^a-zA-Z0-9]+", name)
    title = "".join(p.capitalize() for p in parts if p)
    return (title or "Algorithm") + "Algorithm"


def init_project(name: str, target_dir: Optional[str], pids_csv: Optional[str], version: str, description: Optional[str]) -> Dict[str, Any]:
    safe_mod = _sanitize_module_name(name)
    class_name = _class_name_from(name)
    pids = [p.strip() for p in (pids_csv or "").split(",") if p.strip()]
    if not pids:
        pids = ["PID_TO_FILL"]
    base = os.path.abspath(target_dir or f"{safe_mod}")
    pkg_dir = os.path.join(base, safe_mod)
    os.makedirs(pkg_dir, exist_ok=True)

    manifest = {
        "name": name,
        "version": version,
        "entry_point": f"{safe_mod}.main:{class_name}",
        "description": description or f"{name} 算法包",
        "supported_pids": pids,
        "steps": [
            {
                "index": 0,
                "name": "示例步骤",
                "params": [
                    {"key": "threshold", "type": "float", "default": 0.5, "min": 0.0, "max": 1.0}
                ],
            }
        ],
    }

    with open(os.path.join(base, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    with open(os.path.join(pkg_dir, "__init__.py"), "w", encoding="utf-8") as f:
        f.write(f"__all__ = [\"{class_name}\"]\n")

    main_py = f"""
from typing import Any, Dict

from procvision_algorithm_sdk import BaseAlgorithm, Session, read_image_from_shared_memory


class {class_name}(BaseAlgorithm):
    def __init__(self) -> None:
        super().__init__()
        self._supported_pids = {pids}

    def get_info(self) -> Dict[str, Any]:
        return {{
            "name": "{name}",
            "version": "{version}",
            "description": "{description or name + ' 算法包'}",
            "supported_pids": self._supported_pids,
            "steps": [
                {{
                    "index": 0,
                    "name": "示例步骤",
                    "params": [
                        {{"key": "threshold", "type": "float", "default": 0.5, "min": 0.0, "max": 1.0}}
                    ],
                }}
            ],
        }}

    def pre_execute(
        self,
        step_index: int,
        pid: str,
        session: Session,
        user_params: Dict[str, Any],
        shared_mem_id: str,
        image_meta: Dict[str, Any],
    ) -> Dict[str, Any]:
        if pid not in self._supported_pids:
            return {{"status": "ERROR", "message": f"不支持的产品型号: {{pid}}", "error_code": "1001"}}
        img = read_image_from_shared_memory(shared_mem_id, image_meta)
        if img is None:
            return {{"status": "ERROR", "message": "图像数据为空", "error_code": "1002"}}
        w = int(image_meta.get("width", 640))
        h = int(image_meta.get("height", 480))
        return {{"status": "OK", "message": "准备就绪", "debug": {{"width": w, "height": h, "latency_ms": 0.0}}}}

    def execute(
        self,
        step_index: int,
        pid: str,
        session: Session,
        user_params: Dict[str, Any],
        shared_mem_id: str,
        image_meta: Dict[str, Any],
    ) -> Dict[str, Any]:
        img = read_image_from_shared_memory(shared_mem_id, image_meta)
        if img is None:
            return {{"status": "ERROR", "message": "图像数据为空", "error_code": "1002"}}
        th = float(user_params.get("threshold", 0.5))
        result_status = "OK" if th >= 0.5 else "NG"
        data = {{"result_status": result_status, "defect_rects": [], "debug": {{"latency_ms": 0.0}}}}
        if result_status == "NG":
            data.update({{"ng_reason": "threshold too low"}})
        return {{"status": "OK", "data": data}}
"""
    with open(os.path.join(pkg_dir, "main.py"), "w", encoding="utf-8") as f:
        f.write(main_py)

    try:
        impl = "cp"
        abi = f"cp{sys.version_info.major}{sys.version_info.minor}"
        plat = "win_amd64" if os.name == "nt" else None
        env_cfg = {
            "python_version": f"{sys.version_info.major}.{sys.version_info.minor}",
            "implementation": impl,
            "abi": abi,
            "wheels_platform": plat,
            "auto_freeze": True,
        }
        with open(os.path.join(base, ".procvision_env.json"), "w", encoding="utf-8") as f:
            json.dump(env_cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

    return {"status": "OK", "path": base}


def _write_frame(fp, obj: Dict[str, Any]) -> None:
    data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    ln = len(data).to_bytes(4, byteorder="big")
    fp.write(ln + data)
    fp.flush()


def _read_exact(fp, n: int) -> Optional[bytes]:
    b = b""
    while len(b) < n:
        chunk = fp.read(n - len(b))
        if not chunk:
            return None
        b += chunk
    return b


def _read_frame(fp) -> Optional[Dict[str, Any]]:
    h = _read_exact(fp, 4)
    if h is None:
        return None
    ln = int.from_bytes(h, byteorder="big")
    if ln <= 0:
        return None
    body = _read_exact(fp, ln)
    if body is None:
        return None
    try:
        return json.loads(body.decode("utf-8"))
    except Exception:
        return None


def _stderr_printer(pipe) -> None:
    try:
        while True:
            line = pipe.readline()
            if not line:
                break
            try:
                s = line.decode("utf-8", errors="ignore").rstrip()
            except Exception:
                s = str(line)
            if not s:
                continue
            try:
                obj = json.loads(s)
                print(json.dumps(obj, ensure_ascii=False))
            except Exception:
                print(s)
    except Exception:
        pass


def run_adapter(project: str, pid: str, image_path: str, params_json: Optional[str], step_index: Optional[int] = None, entry: Optional[str] = None, tail_logs: bool = False) -> Dict[str, Any]:
    manifest_path = os.path.join(project, "manifest.json")
    if not os.path.isfile(manifest_path):
        return {"pre_execute": {"status": "ERROR", "message": "未找到 manifest.json"}, "execute": {"status": "ERROR", "message": "未找到 manifest.json"}}
    if not os.path.isfile(image_path):
        return {"pre_execute": {"status": "ERROR", "message": "图片文件不存在"}, "execute": {"status": "ERROR", "message": "图片文件不存在"}}
    try:
        params = json.loads(params_json) if params_json else {}
    except Exception:
        params = {}
    with open(manifest_path, "r", encoding="utf-8") as f:
        mf = json.load(f)
    if pid not in (mf.get("supported_pids") or [pid]):
        pass
    cmd = [sys.executable, "-m", "procvision_algorithm_sdk.adapter"]
    if entry:
        cmd += ["--entry", entry]
    env = os.environ.copy()
    env["PROC_ALGO_ROOT"] = os.path.abspath(project)
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=project, env=env)
    if proc.stdout is None or proc.stdin is None:
        return {"pre_execute": {"status": "ERROR", "message": "子进程启动失败"}, "execute": {"status": "ERROR", "message": "子进程启动失败"}}
    log_thread = None
    if tail_logs and proc.stderr is not None:
        log_thread = threading.Thread(target=_stderr_printer, args=(proc.stderr,), daemon=True)
        log_thread.start()
    hello = _read_frame(proc.stdout)
    if hello is None:
        try:
            proc.terminate()
        except Exception:
            pass
        return {"pre_execute": {"status": "ERROR", "message": "adapter hello missing"}, "execute": {"status": "ERROR", "message": "adapter hello missing"}}
    _write_frame(proc.stdin, {"type": "hello", "runner_version": "dev", "heartbeat_interval_ms": 5000, "heartbeat_grace_ms": 2000})
    try:
        with open(image_path, "rb") as f:
            data = f.read()
    except Exception:
        data = b""
    try:
        import PIL.Image as Image  # type: ignore
        img = Image.open(image_path)
        width, height = img.size
    except Exception:
        width, height = 640, 480
    sidx = int(step_index) if step_index is not None else 1
    session = {"id": f"session-{int(time.time()*1000)}", "context": {"product_code": pid, "trace_id": f"trace-{int(time.time()*1000)}"}}
    shared_mem_id = f"dev-shm:{session['id']}"
    image_meta = {"width": int(width), "height": int(height), "timestamp_ms": int(time.time() * 1000), "camera_id": "cam-dev", "color_space": "RGB"}
    try:
        dev_write_image_to_shared_memory(shared_mem_id, data)
    except Exception:
        pass
    rid_pre = str(uuid.uuid4())
    call_pre = {"type": "call", "request_id": rid_pre, "data": {"phase": "pre", "step_index": sidx, "pid": pid, "session": session, "user_params": params, "shared_mem_id": shared_mem_id, "image_meta": image_meta}}
    _write_frame(proc.stdin, call_pre)
    pre = _read_frame(proc.stdout) or {"status": "ERROR", "message": "pre 超时"}
    rid_exe = str(uuid.uuid4())
    call_exe = {"type": "call", "request_id": rid_exe, "data": {"phase": "execute", "step_index": sidx, "pid": pid, "session": session, "user_params": params, "shared_mem_id": shared_mem_id, "image_meta": image_meta}}
    _write_frame(proc.stdin, call_exe)
    exe = _read_frame(proc.stdout) or {"status": "ERROR", "message": "execute 超时"}
    _write_frame(proc.stdin, {"type": "shutdown"})
    _read_frame(proc.stdout)
    try:
        proc.terminate()
    except Exception:
        pass
    try:
        if log_thread is not None:
            log_thread.join(timeout=0.5)
    except Exception:
        pass
    return {"pre_execute": pre or {}, "execute": exe or {}}

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="procvision-cli",
        description=(
            "ProcVision 算法开发 Dev Runner CLI\n"
            "- 验证/运行算法包（默认适配器子进程模式，可跟随日志）\n"
            "- 使用本地图片写入共享内存并调用 pre/execute\n"
            "- 构建离线交付包（默认包含 Python 运行时）"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
        epilog=(
            "示例:\n"
            "  验证项目(适配器模式+日志): procvision-cli validate ./algorithm-example --full --tail-logs\n"
            "  验证压缩包(JSON输出): procvision-cli validate --zip ./algo.zip --json\n"
            "  本地运行(适配器模式+日志): procvision-cli run ./algorithm-example --pid p001 --image ./test.jpg --tail-logs --json\n"
            "  构建离线包(默认嵌入运行时): procvision-cli package ./algorithm-example --python-runtime <path_to_embeddable> --runtime-python-version 3.10 --runtime-abi cp310\n"
            "  构建离线包(不嵌入运行时): procvision-cli package ./algorithm-example --no-embed-python\n"
        ),
    )
    sub = parser.add_subparsers(dest="command")

    v = sub.add_parser(
        "validate",
        help="校验算法包结构与入口实现",
        description="校验 manifest/入口类/supported_pids/返回结构；支持 --full 适配器子进程完整校验与 --tail-logs 日志输出",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    v.add_argument("project", nargs="?", default=".", help="算法项目根目录，默认当前目录")
    v.add_argument("--manifest", type=str, default=None, help="指定 manifest.json 路径（可替代 --project）")
    v.add_argument("--zip", type=str, default=None, help="离线交付 zip 包路径（检查 wheels/ 与必需文件）")
    v.add_argument("--json", action="store_true", help="以 JSON 输出结果")
    v.add_argument("--full", action="store_true", help="使用适配器子进程执行完整握手与 pre/execute 校验")
    v.add_argument("--entry", type=str, default=None, help="显式指定入口 <module:Class>，用于 --full 模式")
    v.add_argument("--legacy-validate", action="store_true", help="使用旧的本地导入校验路径")
    v.add_argument("--tail-logs", action="store_true", help="在 --full 模式下实时输出子进程日志")

    r = sub.add_parser(
        "run",
        help="本地模拟运行算法",
        description=(
            "默认适配器子进程模式，使用本地图片写入共享内存并调用 pre/execute；支持 --entry 指定入口与 --tail-logs 跟随日志。\n"
            "注意: pid 必须在 manifest 的 supported_pids 中。"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    r.add_argument("project", type=str, help="算法项目根目录，包含 manifest.json 与源码")
    r.add_argument("--pid", type=str, required=True, help="产品型号编码（必须在 supported_pids 中）")
    r.add_argument("--image", type=str, required=True, help="本地图片路径（JPEG/PNG），将写入共享内存")
    r.add_argument("--step", type=int, default=1, help="步骤索引（平台从 1 开始；默认 1）")
    r.add_argument(
        "--params",
        type=str,
        default=None,
        help="JSON 字符串形式的用户参数，例如 '{\"threshold\":0.8}'",
    )
    r.add_argument("--entry", type=str, default=None, help="显式指定入口 <module:Class>，否则由适配器自动发现")
    r.add_argument("--legacy-run", action="store_true", help="使用旧的本地直接导入执行路径")
    r.add_argument("--tail-logs", action="store_true", help="在适配器模式下实时输出子进程日志")
    r.add_argument("--json", action="store_true", help="以 JSON 输出结果")

    p = sub.add_parser(
        "package",
        help="构建离线交付 zip 包",
        description="下载 wheels 并打包源码/manifest/requirements/assets；默认包含 Python 运行时（可用 --no-embed-python 关闭）",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    p.add_argument("project", type=str, help="算法项目根目录")
    p.add_argument("-o", "--output", type=str, default=None, help="输出 zip 文件路径，默认按 name/version 生成")
    p.add_argument("-r", "--requirements", type=str, default=None, help="requirements.txt 路径，默认使用项目内文件或自动生成")
    p.add_argument("-a", "--auto-freeze", action="store_true", default=True, help="缺少 requirements.txt 时自动生成 (pip freeze)")
    p.add_argument("-w", "--wheels-platform", type=str, default=None, help="wheels 目标平台，默认读取缓存或使用 win_amd64")
    p.add_argument("-p", "--python-version", type=str, default=None, help="目标 Python 版本，默认读取缓存或使用 3.10")
    p.add_argument("-i", "--implementation", type=str, default=None, help="Python 实现 (如 cp、pp)，默认读取缓存或使用 cp")
    p.add_argument("-b", "--abi", type=str, default=None, help="ABI (如 cp310)，默认读取缓存或使用 cp310")
    p.add_argument("-s", "--skip-download", action="store_true", help="跳过依赖下载，仅打包现有内容")
    p.add_argument("--embed-python", action="store_true", default=True, help="将 Python 运行时一并打包（默认开启）")
    p.add_argument("--no-embed-python", action="store_false", dest="embed_python", help="不打包 Python 运行时")
    p.add_argument("--python-runtime", type=str, default=None, help="Python 运行时目录（如 Windows embeddable 包解压目录）")
    p.add_argument("--runtime-python-version", type=str, default=None, help="运行时 Python 版本（如 3.10）")
    p.add_argument("--runtime-abi", type=str, default=None, help="运行时 ABI（如 cp310）")

    i = sub.add_parser(
        "init",
        help="初始化算法包脚手架",
        description=(
            "根据算法名称初始化脚手架，生成 manifest.json 与包源码目录。\n"
            "生成后请按注释修改 PID 列表、步骤 schema 与检测逻辑"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    i.add_argument("name", type=str, help="算法名称（用于 manifest 与入口类名）")
    i.add_argument("-d", "--dir", type=str, default=None, help="目标目录，默认在当前目录下以算法名生成")
    i.add_argument("--pids", type=str, default="", help="支持的 PID 列表，逗号分隔，留空则生成占位 PID_TO_FILL")
    i.add_argument("-v", "--version", type=str, default="1.0.0", help="算法版本，默认 1.0.0")
    i.add_argument("-e", "--desc", type=str, default=None, help="算法描述，可选")

    args = parser.parse_args()

    if args.command == "validate":
        proj = args.project
        if args.full and not args.legacy_validate and os.path.isdir(proj):
            report = validate_adapter(proj, args.entry, args.tail_logs)
        else:
            report = validate(proj, args.manifest, args.zip)
        if args.json:
            print(json.dumps(report, ensure_ascii=False))
        else:
            _print_validate_human(report)
        ok = report["summary"]["status"] == "PASS"
        sys.exit(0 if ok else 1)

    if args.command == "run":
        if not os.path.isdir(args.project):
            print(f"错误: 项目目录不存在: {args.project}")
            print("示例: procvision-cli run ./algorithm-example --pid p001 --image ./test.jpg")
            sys.exit(2)
        manifest_path = os.path.join(args.project, "manifest.json")
        if not os.path.isfile(manifest_path):
            print(f"错误: 未找到 manifest.json: {manifest_path}")
            print("请确认项目根目录包含 manifest.json")
            sys.exit(2)
        if not os.path.isfile(args.image):
            print(f"错误: 图片文件不存在: {args.image}")
            print("示例: --image ./test.jpg")
            sys.exit(2)
        if args.params:
            try:
                json.loads(args.params)
            except Exception:
                print("错误: --params 必须是 JSON 字符串。示例: '{\"threshold\":0.8}'")
                sys.exit(2)
        if args.legacy_run:
            result = run(args.project, args.pid, args.image, args.params, args.step)
        else:
            result = run_adapter(args.project, args.pid, args.image, args.params, args.step, args.entry, args.tail_logs)
        if args.json:
            print(json.dumps(result, ensure_ascii=False))
        else:
            _print_run_human(result)
        status = result.get("execute", {}).get("status")
        sys.exit(0 if status == "OK" else 1)

    if args.command == "package":
        res = package(
            args.project,
            args.output,
            args.requirements,
            args.auto_freeze,
            args.wheels_platform,
            args.python_version,
            args.implementation,
            args.abi,
            args.skip_download,
            args.embed_python,
            args.python_runtime,
            args.runtime_python_version,
            args.runtime_abi,
        )
        if res.get("status") == "OK":
            print(f"打包成功: {res.get('zip')}")
            sys.exit(0)
        print(f"打包失败: {res.get('message')}")
        sys.exit(1)

    if args.command == "init":
        res = init_project(args.name, args.dir, args.pids, args.version, args.desc)
        if res.get("status") == "OK":
            print(f"初始化成功: {res.get('path')}")
            print("下一步: 请修改生成的 main.py 注释指示的内容，并确保 manifest.json 与 get_info 一致")
            sys.exit(0)
        print(f"初始化失败: {res.get('message')}")
        sys.exit(1)

    parser.print_help()
def validate_adapter(project: str, entry: Optional[str], tail_logs: bool = False) -> Dict[str, Any]:
    checks: List[Dict[str, Any]] = []
    manifest_path = os.path.join(project, "manifest.json")
    if not os.path.isfile(manifest_path):
        return {"summary": {"status": "FAIL", "passed": 0, "failed": 1}, "checks": [{"name": "manifest_exists", "result": "FAIL", "message": "manifest.json not found"}]}
    with open(manifest_path, "r", encoding="utf-8") as f:
        mf = json.load(f)
    pid_list = mf.get("supported_pids", [])
    pid = (pid_list or ["A01"])[0]
    env = os.environ.copy()
    env["PROC_ALGO_ROOT"] = os.path.abspath(project)
    cmd = [sys.executable, "-m", "procvision_algorithm_sdk.adapter"]
    if entry:
        cmd += ["--entry", entry]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=project, env=env)
    if proc.stdout is None or proc.stdin is None:
        return {"summary": {"status": "FAIL", "passed": 0, "failed": 1}, "checks": [{"name": "adapter_start", "result": "FAIL", "message": "start failed"}]}
    log_thread = None
    if tail_logs and proc.stderr is not None:
        log_thread = threading.Thread(target=_stderr_printer, args=(proc.stderr,), daemon=True)
        log_thread.start()
    hello = _read_frame(proc.stdout)
    ok_hello = isinstance(hello, dict) and hello.get("type") == "hello"
    checks.append({"name": "adapter_hello", "result": "PASS" if ok_hello else "FAIL", "message": "hello" if ok_hello else "missing"})
    if not ok_hello:
        try:
            proc.terminate()
        except Exception:
            pass
        return {"summary": {"status": "FAIL", "passed": 0, "failed": 1}, "checks": checks}
    _write_frame(proc.stdin, {"type": "hello", "runner_version": "dev", "heartbeat_interval_ms": 5000, "heartbeat_grace_ms": 2000})
    rid_info = str(uuid.uuid4())
    _write_frame(proc.stdin, {"type": "call", "request_id": rid_info, "data": {"phase": "info"}})
    info_res = _read_frame(proc.stdout)
    ok_info = isinstance(info_res, dict) and info_res.get("type") == "result" and info_res.get("data", {}).get("phase") == "info"
    checks.append({"name": "get_info_result", "result": "PASS" if ok_info else "FAIL", "message": "received" if ok_info else "invalid"})
    session = {"id": f"session-{int(time.time()*1000)}", "context": {"product_code": pid, "trace_id": f"trace-{int(time.time()*1000)}"}}
    shared_mem_id = f"dev-shm:{session['id']}"
    try:
        dev_write_image_to_shared_memory(shared_mem_id, b"")
    except Exception:
        pass
    image_meta = {"width": 640, "height": 480, "timestamp_ms": int(time.time()*1000), "camera_id": "cam-dev", "color_space": "RGB"}
    rid_pre = str(uuid.uuid4())
    _write_frame(proc.stdin, {"type": "call", "request_id": rid_pre, "data": {"phase": "pre", "step_index": 1, "pid": pid, "session": session, "user_params": {}, "shared_mem_id": shared_mem_id, "image_meta": image_meta}})
    pre = _read_frame(proc.stdout)
    ok_pre = isinstance(pre, dict) and pre.get("type") == "result" and (pre.get("status") in {"OK", "ERROR"})
    checks.append({"name": "pre_result", "result": "PASS" if ok_pre else "FAIL", "message": "received" if ok_pre else "invalid"})
    rid_exe = str(uuid.uuid4())
    _write_frame(proc.stdin, {"type": "call", "request_id": rid_exe, "data": {"phase": "execute", "step_index": 1, "pid": pid, "session": session, "user_params": {}, "shared_mem_id": shared_mem_id, "image_meta": image_meta}})
    exe = _read_frame(proc.stdout)
    ok_exe = isinstance(exe, dict) and exe.get("type") == "result" and (exe.get("status") in {"OK", "ERROR"})
    checks.append({"name": "execute_result", "result": "PASS" if ok_exe else "FAIL", "message": "received" if ok_exe else "invalid"})
    if ok_exe and exe.get("status") == "OK":
        data = exe.get("data", {})
        rs = data.get("result_status")
        checks.append({"name": "execute_result_status", "result": "PASS" if rs in {"OK", "NG"} else "FAIL", "message": str(rs)})
        if rs == "NG":
            dr = data.get("defect_rects", [])
            checks.append({"name": "defect_rects_limit", "result": "PASS" if isinstance(dr, list) and len(dr) <= 20 else "FAIL", "message": f"len={len(dr) if isinstance(dr, list) else 'n/a'}"})
    _write_frame(proc.stdin, {"type": "shutdown"})
    _read_frame(proc.stdout)
    try:
        proc.terminate()
    except Exception:
        pass
    try:
        if log_thread is not None:
            log_thread.join(timeout=0.5)
    except Exception:
        pass
    passed = sum(1 for c in checks if c["result"] == "PASS")
    failed = sum(1 for c in checks if c["result"] == "FAIL")
    status = "PASS" if failed == 0 else "FAIL"
    return {"summary": {"status": status, "passed": passed, "failed": failed}, "checks": checks}
