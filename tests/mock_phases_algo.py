
from typing import Any, Dict
from procvision_algorithm_sdk.base import BaseAlgorithm

class FullAlgo(BaseAlgorithm):
    def get_info(self) -> Dict[str, Any]:
        return {"version": "1.0"}

    def pre_execute(self, *args, **kwargs) -> Dict[str, Any]:
        return {"status": "OK"}

    def execute(self, *args, **kwargs) -> Dict[str, Any]:
        return {"status": "OK"}

class MissingAlgo:
    # No methods implemented except maybe what's needed to not crash on import
    pass
