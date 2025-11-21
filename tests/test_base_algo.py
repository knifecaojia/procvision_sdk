import unittest
from typing import Any, Dict
from procvision_algorithm_sdk import BaseAlgorithm, Session, read_image_from_shared_memory


class DummyAlgo(BaseAlgorithm):
    def __init__(self) -> None:
        super().__init__()
        self._supported_pids = ["p001"]

    def get_info(self) -> Dict[str, Any]:
        return {
            "name": "dummy",
            "version": "0.0.1",
            "description": "dummy",
            "supported_pids": self._supported_pids,
            "steps": [{"index": 0, "name": "s", "params": []}],
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
        return {"status": "OK", "message": "准备就绪"}

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
            return {"status": "ERROR", "message": "图像数据为空", "error_code": "1002"}
        return {"status": "OK", "data": {"result_status": "OK", "defect_rects": [], "debug": {"latency_ms": 0.0}}}


class TestBaseAlgorithm(unittest.TestCase):
    def test_dummy_algo_flow(self):
        alg = DummyAlgo()
        info = alg.get_info()
        self.assertEqual(info["supported_pids"], ["p001"])
        session = Session("sid")
        meta = {"width": 100, "height": 100, "timestamp_ms": 0, "camera_id": "cam"}
        pre = alg.pre_execute(0, "p001", session, {}, "dev-shm:sid", meta)
        exe = alg.execute(0, "p001", session, {}, "dev-shm:sid", meta)
        self.assertIn(pre.get("status"), {"OK", "ERROR"})
        self.assertIn(exe.get("status"), {"OK", "ERROR"})


if __name__ == "__main__":
    unittest.main()