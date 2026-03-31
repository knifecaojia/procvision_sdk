from typing import Any, Dict, List
import random
import time

from procvision_algorithm_sdk import BaseAlgorithm


class AlgorithmExample(BaseAlgorithm):
    def __init__(self) -> None:
        super().__init__()

    def execute(
        self,
        step_index: int,
        step_desc: str,
        cur_image: Any,
        guide_image: Any,
        guide_info: Any,
    ) -> Dict[str, Any]:
        start = time.time()
        if cur_image is None or guide_image is None:
            return {"status": "ERROR", "message": "图像数据为空", "error_code": "1002"}

        shape = getattr(guide_image, "shape", None)
        height = int(shape[0]) if shape is not None and len(shape) >= 2 else 480
        width = int(shape[1]) if shape is not None and len(shape) >= 2 else 640

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
                    "ng_reason": f"{step_desc or '步骤'}: 随机生成标定框{count}个",
                    "defect_rects": _rand_rects(count),
                    "debug": {"latency_ms": latency_ms, "guide_info_count": len(guide_info or [])},
                },
            }
        else:
            return {
                "status": "OK",
                "data": {
                    "result_status": "OK",
                    "defect_rects": [],
                    "position_rects": _rand_rects(count),
                    "debug": {"latency_ms": latency_ms, "guide_info_count": len(guide_info or [])},
                },
            }

