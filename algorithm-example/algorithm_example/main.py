from typing import Any, Dict, List
import random
import time

from procvision_algorithm_sdk import BaseAlgorithm, Session, read_image_from_shared_memory


class AlgorithmExample(BaseAlgorithm):
    def __init__(self) -> None:
        super().__init__()
        self._supported_pids = ["p001", "p002"]
        
    def setup(self) -> None:
        self._model_version = "example_v1"
        self.logger.info("setup", model_version=self._model_version)

    def teardown(self) -> None:
        self.logger.info("teardown")

    def on_step_start(self, step_index: int, session: Session, context: Dict[str, Any]) -> None:
        session.set("step_start_ms", int(time.time() * 1000))
        self.logger.info("on_step_start", step_index=step_index, context=context)

    def on_step_finish(self, step_index: int, session: Session, result: Dict[str, Any]) -> None:
        start_ms = session.get("step_start_ms", None)
        if isinstance(start_ms, (int, float)):
            latency_ms = int(time.time() * 1000) - int(start_ms)
            self.diagnostics.publish("step_latency_ms", latency_ms)
            self.logger.info("on_step_finish", step_index=step_index, latency_ms=latency_ms)
        else:
            self.logger.info("on_step_finish", step_index=step_index)

    def reset(self, session: Session) -> None:
        session.delete("step_start_ms")

    def get_info(self) -> Dict[str, Any]:
        return {
            "name": "algorithm-example",
            "version": "1.0",
            "description": "示例算法（p001/p002）",
            "supported_pids": self._supported_pids,
            "steps": [
                {
                    "index": 1,
                    "name": "定位主板",
                    "params": [
                        {"key": "roi", "type": "rect", "required": True, "description": "定位区域"},
                        {"key": "exposure", "type": "float", "default": 12.5, "min": 8.0, "max": 16.0, "unit": "ms"},
                    ],
                },
                {
                    "index": 2,
                    "name": "检测左上角螺丝",
                    "params": [
                        {"key": "threshold", "type": "float", "default": 0.7, "min": 0.5, "max": 0.9, "description": "置信度阈值"},
                        {"key": "mode", "type": "enum", "choices": ["fast", "accurate"], "default": "fast"},
                    ],
                },
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
        start = time.time()
        img = read_image_from_shared_memory(shared_mem_id, image_meta)
        if img is None:
            return {"status": "ERROR", "message": "图像数据为空", "error_code": "1002"}

        width = int(image_meta.get("width", 640))
        height = int(image_meta.get("height", 480))

        def _rand_rects(n: int) -> List[Dict[str, Any]]:
            rects: List[Dict[str, Any]] = []
            for _ in range(n):
                w = random.randint(max(10, width // 20), max(20, width // 8))
                h = random.randint(max(10, height // 20), max(20, height // 8))
                x = random.randint(0, max(0, width - w))
                y = random.randint(0, max(0, height - h))
                rects.append({"x": x, "y": y, "width": w, "height": h, "label": "pos"})
            return rects

        count = random.randint(1, 3)
        latency_ms = (time.time() - start) * 1000.0
        return {
            "status": "OK",
            "message": f"准备就绪: 返回{count}个标定框",
            "data": {"calibration_rects": _rand_rects(count)},
            "debug": {"latency_ms": latency_ms},
        }

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
        start = time.time()
        img = read_image_from_shared_memory(shared_mem_id, image_meta)
        if img is None:
            return {"status": "ERROR", "message": "图像数据为空", "error_code": "1002"}

        width = int(image_meta.get("width", 640))
        height = int(image_meta.get("height", 480))

        def _rand_rects(n: int) -> List[Dict[str, Any]]:
            rects: List[Dict[str, Any]] = []
            for _ in range(n):
                w = random.randint(max(10, width // 20), max(20, width // 8))
                h = random.randint(max(10, height // 20), max(20, height // 8))
                x = random.randint(0, max(0, width - w))
                y = random.randint(0, max(0, height - h))
                rects.append({"x": x, "y": y, "width": w, "height": h, "label": "pos"})
            return rects

        count = random.randint(1, 3)
        is_ng = (step_index % 2 == 1)
        latency_ms = (time.time() - start) * 1000.0
        if is_ng:
            return {
                "status": "OK",
                "data": {
                    "result_status": "NG",
                    "ng_reason": f"随机生成标定框{count}个",
                    "defect_rects": _rand_rects(count),
                    "debug": {"latency_ms": latency_ms},
                },
            }
        else:
            return {
                "status": "OK",
                "data": {
                    "result_status": "OK",
                    "position_rects": _rand_rects(count),
                    "debug": {"latency_ms": latency_ms},
                },
            }