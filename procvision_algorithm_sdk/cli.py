import argparse
import importlib
import json
import os
import sys
import zipfile
from typing import Any, Dict, List, Optional

from .base import BaseAlgorithm
from .session import Session


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


def validate(project: Optional[str], manifest: Optional[str], zip_path: Optional[str]) -> Dict[str, Any]:
    checks: List[Dict[str, Any]] = []

    def add(name: str, ok: bool, message: str = "") -> None:
        checks.append({"name": name, "result": "PASS" if ok else "FAIL", "message": message})

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
        add("manifest_exists", False, "manifest.json not found")
        summary = {"status": "FAIL", "passed": 0, "failed": 1}
        return {"summary": summary, "checks": checks}

    try:
        mf = _load_manifest(manifest_path)
        add("manifest_load", True, "loaded")
    except Exception as e:
        add("manifest_load", False, str(e))
        summary = {"status": "FAIL", "passed": 1, "failed": 1}
        return {"summary": summary, "checks": checks}

    required = ["name", "version", "entry_point", "supported_pids"]
    missing = [k for k in required if k not in mf]
    add("manifest_fields", len(missing) == 0, ",".join(missing))

    entry_point = mf.get("entry_point", "")
    try:
        cls = _import_entry(entry_point, project_sys_path)
        ok = issubclass(cls, BaseAlgorithm)
        add("entry_import", ok, "imported")
    except Exception as e:
        add("entry_import", False, str(e))

    smoke_ok = False
    try:
        pid = mf.get("pid", "demo")
        alg = cls(pid)
        info = alg.get_info()
        step_schema_ok = isinstance(info, dict) and isinstance(info.get("steps", []), list)
        add("step_schema", step_schema_ok, "steps present")
        _ = alg.pre_execute(0, Session("session-demo"), "shared", {"width": 8, "height": 8, "channels": 3}, {})
        result = alg.execute(0, Session("session-demo"), "shared", {"width": 8, "height": 8, "channels": 3}, {})
        smoke_ok = isinstance(result, dict)
        add("smoke_execute", smoke_ok, "done")
        status = result.get("status")
        suggest = result.get("suggest_action")
        err_type = result.get("error_type")
        status_ok = status in {"OK", "NG", "ERROR"}
        suggest_ok = suggest in {None, "retry", "skip", "abort"}
        err_ok = err_type in {None, "recoverable", "fatal"}
        add("io_contract_status", status_ok, str(status))
        add("io_contract_suggest", suggest_ok, str(suggest))
        add("io_contract_error_type", err_ok, str(err_type))
    except Exception as e:
        add("smoke_execute", False, str(e))

    if zip_path:
        try:
            with zipfile.ZipFile(zip_path, "r") as z:
                names = set(z.namelist())
                m1 = any(n.endswith("manifest.json") for n in names)
                m2 = any(n.endswith("requirements.txt") for n in names)
                m3 = any(n.endswith("/wheels/") or "/wheels/" in n for n in names)
                add("zip_manifest", m1, "manifest")
                add("zip_requirements", m2, "requirements")
                add("zip_wheels", m3, "wheels")
        except Exception as e:
            add("zip_open", False, str(e))

    passed = sum(1 for c in checks if c["result"] == "PASS")
    failed = sum(1 for c in checks if c["result"] == "FAIL")
    status = "PASS" if failed == 0 else "FAIL"
    return {"summary": {"status": status, "passed": passed, "failed": failed}, "checks": checks}


def main() -> None:
    parser = argparse.ArgumentParser(prog="procvision-sdk")
    sub = parser.add_subparsers(dest="command")
    v = sub.add_parser("validate")
    v.add_argument("--project", type=str, default=None)
    v.add_argument("--manifest", type=str, default=None)
    v.add_argument("--zip", type=str, default=None)
    args = parser.parse_args()
    if args.command == "validate":
        report = validate(args.project, args.manifest, args.zip)
        print(json.dumps(report, ensure_ascii=False))
        ok = report["summary"]["status"] == "PASS"
        sys.exit(0 if ok else 1)
    parser.print_help()