from typing import Any, Dict

import numpy as np


def read_image_from_shared_memory(shared_mem_id: str, image_meta: Dict[str, Any]) -> Any:
    height = int(image_meta.get("height", 0))
    width = int(image_meta.get("width", 0))
    channels = int(image_meta.get("channels", 3))
    return np.zeros((height, width, channels), dtype=np.uint8)