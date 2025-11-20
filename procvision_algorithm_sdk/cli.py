import argparse
import importlib
import json
import os
import sys
import time
import zipfile
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
            pre = alg.pre_execute(0, pid, session, {}, f"dev-shm:{session.id}", image_meta)
            _add(checks, "pre_execute_return_dict", isinstance(pre, dict), "dict")
            pre_status = pre.get("status")
            _add(checks, "pre_status_valid", pre_status in {"OK", "ERROR"}, str(pre_status))
            _add(checks, "pre_message_present", bool(pre.get("message")), str(pre.get("message")))

            exe = alg.execute(0, pid, session, {}, f"dev-shm:{session.id}", image_meta)
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


def run(project: str, pid: str, image_path: str, params_json: Optional[str]) -> Dict[str, Any]:
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

    pre = alg.pre_execute(0, pid, session, user_params, shared_mem_id, image_meta)
    exe = alg.execute(0, pid, session, user_params, shared_mem_id, image_meta)
    return {"pre_execute": pre, "execute": exe}


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="procvision-cli",
        description=(
            "ProcVision 算法开发 Dev Runner CLI\n"
            "- 本地验证算法包结构与入口实现\n"
            "- 使用本地图片模拟共享内存并调用 pre_execute/execute\n"
            "- 输出 JSON 报告，便于快速自测"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
        epilog=(
            "示例:\n"
            "  验证项目: procvision-cli validate --project ./algorithm-example\n"
            "  验证压缩包: procvision-cli validate --zip ./algo.zip\n"
            "  本地运行: procvision-cli run ./algorithm-example --pid p001 --image ./test.jpg --params '{\"threshold\":0.8}'\n"
        ),
    )
    sub = parser.add_subparsers(dest="command")

    v = sub.add_parser(
        "validate",
        help="校验算法包结构与入口实现",
        description="校验 manifest、入口类、supported_pids 一致性与返回结构",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    v.add_argument("--project", type=str, default=None, help="算法项目根目录，包含 manifest.json")
    v.add_argument("--manifest", type=str, default=None, help="指定 manifest.json 路径（可替代 --project）")
    v.add_argument("--zip", type=str, default=None, help="离线交付 zip 包路径（检查 wheels/ 与必需文件）")

    r = sub.add_parser(
        "run",
        help="本地模拟运行算法",
        description=(
            "使用本地图片写入共享内存并调用 pre_execute/execute。\n"
            "注意: pid 必须在 manifest 的 supported_pids 中"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    r.add_argument("project", type=str, help="算法项目根目录，包含 manifest.json 与源码")
    r.add_argument("--pid", type=str, required=True, help="产品型号编码（必须在 supported_pids 中）")
    r.add_argument("--image", type=str, required=True, help="本地图片路径（JPEG/PNG），将写入共享内存")
    r.add_argument(
        "--params",
        type=str,
        default=None,
        help="JSON 字符串形式的用户参数，例如 '{\"threshold\":0.8}'",
    )

    args = parser.parse_args()

    if args.command == "validate":
        if not any([args.project, args.manifest, args.zip]):
            print("错误: 需要至少指定 --project 或 --manifest 或 --zip 之一")
            print("示例: procvision-cli validate --project ./algorithm-example")
            sys.exit(2)
        report = validate(args.project, args.manifest, args.zip)
        print(json.dumps(report, ensure_ascii=False))
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
        result = run(args.project, args.pid, args.image, args.params)
        print(json.dumps(result, ensure_ascii=False))
        status = result.get("execute", {}).get("status")
        sys.exit(0 if status == "OK" else 1)

    parser.print_help()