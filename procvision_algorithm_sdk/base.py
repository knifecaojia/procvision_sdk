from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from .logger import StructuredLogger
from .diagnostics import Diagnostics


class BaseAlgorithm(ABC):
    def __init__(self) -> None:
        self.logger = StructuredLogger()
        self.diagnostics = Diagnostics()
        self._resources_loaded: bool = False
        self._model_version: Optional[str] = None

    @abstractmethod
    def execute(
        self,
        step_index: int,
        step_desc: str,
        cur_image: Any,
        guide_image: Any,
        guide_info: Any,
    ) -> Dict[str, Any]:
        raise NotImplementedError
