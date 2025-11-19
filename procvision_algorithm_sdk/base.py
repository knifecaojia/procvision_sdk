from abc import ABC, abstractmethod
from typing import Any, Dict

from .logger import StructuredLogger
from .diagnostics import Diagnostics
from .session import Session


class BaseAlgorithm(ABC):
    def __init__(self, pid: str):
        self.pid = pid
        self.logger = StructuredLogger()
        self.diagnostics = Diagnostics()

    def setup(self) -> None:
        return None

    def teardown(self) -> None:
        return None

    def on_step_start(self, step_index: int, session: Session, context: Dict[str, Any]) -> None:
        return None

    def on_step_finish(self, step_index: int, session: Session, result: Dict[str, Any]) -> None:
        return None

    def reset(self, session: Session) -> None:
        return None

    @abstractmethod
    def get_info(self) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def pre_execute(
        self,
        step_index: int,
        session: Session,
        shared_mem_id: str,
        image_meta: Dict[str, Any],
        user_params: Dict[str, Any],
    ) -> Dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def execute(
        self,
        step_index: int,
        session: Session,
        shared_mem_id: str,
        image_meta: Dict[str, Any],
        user_params: Dict[str, Any],
    ) -> Dict[str, Any]:
        raise NotImplementedError