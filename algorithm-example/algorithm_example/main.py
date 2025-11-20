from typing import Any, Dict

from procvision_algorithm_sdk import BaseAlgorithm, Session, read_image_from_shared_memory


class AlgorithmExample(BaseAlgorithm):
    def __init__(self) -> None:
        super().__init__()
        self._supported_pids = ["p001", "p002"]

    def get_info(self) -> Dict[str, Any]:
        return {
            "name": "algorithm-example",
            "version": "1.0",
            "description": "示例算法（p001/p002）",
            "supported_pids": self._supported_pids,
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
            return {"status": "ERROR", "message": f"不支持的产品型号: {pid}", "error_code": "1001"}
        img = read_image_from_shared_memory(shared_mem_id, image_meta)
        if img is None:
            return {"status": "ERROR", "message": "图像数据为空", "error_code": "1002"}
        return {"status": "OK", "message": "准备就绪", "debug": {"latency_ms": 0.0}}

    def execute(
        self,
        step_index: int,
        pid: str,
        session: Session,
        user_params: Dict[str, Any],
        shared_mem_id: str,
        image_meta: Dict[str, Any],
    ) -> Dict[str, Any]:
        if pid not in self._supported_pids:
            return {"status": "ERROR", "message": f"不支持的产品型号: {pid}", "error_code": "1001"}
        img = read_image_from_shared_memory(shared_mem_id, image_meta)
        if img is None:
            return {"status": "ERROR", "message": "图像数据为空", "error_code": "1002"}
        return {"status": "OK", "data": {"result_status": "OK", "defect_rects": [], "debug": {"latency_ms": 0.0}}}