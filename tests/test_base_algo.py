import unittest
from typing import Any, Dict
import numpy as np

from procvision_algorithm_sdk import BaseAlgorithm


class DummyAlgo(BaseAlgorithm):
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
        if cur_image is None or guide_image is None:
            return {"status": "ERROR", "message": "图像数据为空", "error_code": "1002"}
        return {"status": "OK", "data": {"result_status": "OK", "defect_rects": [], "debug": {"latency_ms": 0.0}}}


class TestBaseAlgorithm(unittest.TestCase):
    def test_dummy_algo_flow(self):
        alg = DummyAlgo()
        img = np.zeros((100, 100, 3), dtype=np.uint8)
        exe = alg.execute(1, "demo", img, img, [])
        self.assertIn(exe.get("status"), {"OK", "ERROR"})


if __name__ == "__main__":
    unittest.main()
