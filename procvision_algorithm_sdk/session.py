import json
from typing import Any, Dict, Optional


class Session:
    def __init__(self, id: str, context: Optional[Dict[str, Any]] = None):
        self._id = id
        self._state_store: Dict[str, Any] = {}
        self._context: Dict[str, Any] = context or {}

    @property
    def id(self) -> str:
        return self._id

    @property
    def context(self) -> Dict[str, Any]:
        return self._context.copy()

    def get(self, key: str, default: Any = None) -> Any:
        return self._state_store.get(key, default)

    def set(self, key: str, value: Any) -> None:
        try:
            json.dumps(value)
        except (TypeError, ValueError):
            raise TypeError(f"值必须是JSON可序列化的: {type(value)}")
        self._state_store[key] = value

    def delete(self, key: str) -> bool:
        if key in self._state_store:
            del self._state_store[key]
            return True
        return False

    def exists(self, key: str) -> bool:
        return key in self._state_store