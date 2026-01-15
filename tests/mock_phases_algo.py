
from typing import Any, Dict

from procvision_algorithm_sdk.base import BaseAlgorithm

class ExecuteAlgo(BaseAlgorithm):
    def execute(
        self,
        step_index: int,
        step_desc: str,
        cur_image: Any,
        guide_image: Any,
        guide_info: Any,
    ) -> Dict[str, Any]:
        return {"status": "OK", "data": {"result_status": "OK", "defect_rects": [], "debug": {"step_index": step_index}}}

class StdoutSpamAlgo(BaseAlgorithm):
    def execute(
        self,
        step_index: int,
        step_desc: str,
        cur_image: Any,
        guide_image: Any,
        guide_info: Any,
    ) -> Dict[str, Any]:
        print("spam-to-stdout")
        return {"status": "OK", "data": {"result_status": "OK", "defect_rects": [], "debug": {"step_index": step_index}}}

class MissingExecuteAlgo:
    pass
