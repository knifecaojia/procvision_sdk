from typing import Any, Dict

import numpy as np

from procvision_algorithm_sdk import BaseAlgorithm, read_image_from_shared_memory, Session


class DemoAlgorithm(BaseAlgorithm):
    def setup(self) -> None:
        self.logger.info("setup", pid=self.pid)

    def teardown(self) -> None:
        self.logger.info("teardown", pid=self.pid)

    def get_info(self) -> Dict[str, Any]:
        return {
            "name": "demo_sample",
            "version": "0.0.1",
            "description": "sample algorithm",
            "steps": [
                {
                    "index": 0,
                    "name": "demo_step",
                    "params": [
                        {"key": "roi", "type": "rect", "required": True, "description": "检测区域"},
                        {"key": "threshold", "type": "float", "default": 0.5, "min": 0.0, "max": 1.0},
                        {"key": "mode", "type": "enum", "choices": ["fast", "accurate"], "default": "fast"}
                    ],
                }
            ],
        }

    def on_step_start(self, step_index: int, session: Session, context: Dict[str, Any]) -> None:
        self.logger.info("on_step_start", step_index=step_index, session_id=session.id)

    def on_step_finish(self, step_index: int, session: Session, result: Dict[str, Any]) -> None:
        self.logger.info("on_step_finish", step_index=step_index, session_id=session.id, status=result.get("status"))

    def reset(self, session: Session) -> None:
        self.logger.info("reset", session_id=session.id)

    def pre_execute(self, step_index: int, session: Session, shared_mem_id: str, image_meta: Dict[str, Any], user_params: Dict[str, Any]) -> Dict[str, Any]:
        self.logger.info("pre_execute", step_index=step_index, session_id=session.id)
        return {
            "status": "OK",
            "suggest_action": "retry",
            "error_type": None,
            "message": "init",
            "overlay": {"roi_rects": [{"x": 0, "y": 0, "width": 10, "height": 10, "label": "roi"}]},
            "debug": {"latency_ms": 0.0},
        }

    def execute(self, step_index: int, session: Session, shared_mem_id: str, image_meta: Dict[str, Any], user_params: Dict[str, Any]) -> Dict[str, Any]:
        self.logger.info("execute", step_index=step_index, session_id=session.id)
        img = read_image_from_shared_memory(shared_mem_id, image_meta)
        brightness = float(np.mean(img)) if isinstance(img, np.ndarray) else 0.0
        return {
            "status": "OK",
            "ng_reason": None,
            "suggest_action": "retry",
            "error_type": None,
            "defect_rects": [],
            "position_rects": [],
            "diagnostics": {"brightness": brightness},
        }