from typing import Any, Dict, Union


class Session:
    def __init__(self, id: str, context: Union[Dict[str, Any], None] = None):
        self.id = id
        self.state_store: Dict[str, Any] = {}
        self.context = context or {}

    def get(self, key: str) -> Any:
        return self.state_store.get(key)

    def set(self, key: str, value: Any) -> None:
        self.state_store[key] = value

    def delete(self, key: str) -> None:
        self.state_store.pop(key, None)

    def reset(self) -> None:
        self.state_store.clear()