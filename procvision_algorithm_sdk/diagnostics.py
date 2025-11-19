from typing import Any, Dict


class Diagnostics:
    def __init__(self):
        self.items: Dict[str, Any] = {}

    def publish(self, key: str, value: Any) -> None:
        self.items[key] = value

    def get(self) -> Dict[str, Any]:
        return dict(self.items)