import json
import sys
import time
from typing import Any, Dict, Optional


class StructuredLogger:
    def __init__(self, sink: Optional[Any] = None):
        self.sink = sink or sys.stderr

    def _emit(self, level: str, payload: Dict[str, Any]) -> None:
        record: Dict[str, Any] = {"level": level, "timestamp_ms": int(time.time() * 1000)}
        record.update(payload)
        self.sink.write(json.dumps(record, ensure_ascii=False) + "\n")
        self.sink.flush()

    def info(self, message: str, **fields: Any) -> None:
        self._emit("info", {"message": message, **fields})

    def debug(self, message: str, **fields: Any) -> None:
        self._emit("debug", {"message": message, **fields})

    def error(self, message: str, **fields: Any) -> None:
        self._emit("error", {"message": message, **fields})