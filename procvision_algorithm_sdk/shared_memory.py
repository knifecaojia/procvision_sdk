from typing import Any, Dict

import os
import re
import tempfile
import numpy as np

_DEV_SHM: Dict[str, Any] = {}


def _shm_dir() -> str:
    d = os.environ.get("PROC_SHM_DIR") or os.path.join(tempfile.gettempdir(), "procvision_dev_shm")
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        pass
    return d


def _safe_name(shared_mem_id: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]", "_", shared_mem_id)


def dev_write_image_to_shared_memory(shared_mem_id: str, image_bytes: bytes) -> None:
    _DEV_SHM[shared_mem_id] = image_bytes
    try:
        p = os.path.join(_shm_dir(), _safe_name(shared_mem_id) + ".bin")
        with open(p, "wb") as f:
            f.write(image_bytes)
    except Exception:
        pass


def dev_clear_shared_memory(shared_mem_id: str) -> None:
    _DEV_SHM.pop(shared_mem_id, None)


def write_image_array_to_shared_memory(shared_mem_id: str, image_array: Any) -> None:
    _DEV_SHM[shared_mem_id] = image_array
    try:
        p = os.path.join(_shm_dir(), _safe_name(shared_mem_id) + ".npy")
        np.save(p, image_array)
    except Exception:
        pass


def read_image_from_shared_memory(shared_mem_id: str, image_meta: Dict[str, Any]) -> Any:
    width = int(image_meta.get("width", 0))
    height = int(image_meta.get("height", 0))
    if width <= 0 or height <= 0:
        return None
    data = _DEV_SHM.get(shared_mem_id)
    if data is not None:
        if isinstance(data, np.ndarray):
            arr = data
            if arr.ndim == 2:
                arr = np.stack([arr, arr, arr], axis=-1)
            elif arr.ndim == 3 and arr.shape[2] == 1:
                arr = np.repeat(arr, 3, axis=-1)
            elif arr.ndim == 3 and arr.shape[2] == 3:
                pass
            else:
                arr = None
            if arr is not None:
                cs = str(image_meta.get("color_space", "RGB")).upper()
                if cs == "BGR" and arr.ndim == 3 and arr.shape[2] == 3:
                    arr = arr[:, :, ::-1]
                return arr.astype(np.uint8, copy=False)
        try:
            from PIL import Image  # type: ignore
            import io
            img = Image.open(io.BytesIO(data))
            arr = np.array(img)
            if arr.ndim == 2:
                arr = np.stack([arr, arr, arr], axis=-1)
            return arr
        except Exception:
            pass
    # 文件系统后备（适配器子进程可见）
    try:
        base = os.path.join(_shm_dir(), _safe_name(shared_mem_id))
        npy_path = base + ".npy"
        bin_path = base + ".bin"
        if os.path.isfile(npy_path):
            try:
                arr = np.load(npy_path, allow_pickle=False)
                if isinstance(arr, np.ndarray):
                    if arr.ndim == 2:
                        arr = np.stack([arr, arr, arr], axis=-1)
                    elif arr.ndim == 3 and arr.shape[2] == 1:
                        arr = np.repeat(arr, 3, axis=-1)
                    cs = str(image_meta.get("color_space", "RGB")).upper()
                    if cs == "BGR" and arr.ndim == 3 and arr.shape[2] == 3:
                        arr = arr[:, :, ::-1]
                    return arr.astype(np.uint8, copy=False)
            except Exception:
                pass
        if os.path.isfile(bin_path):
            try:
                with open(bin_path, "rb") as f:
                    buf = f.read()
                try:
                    from PIL import Image  # type: ignore
                    import io
                    img = Image.open(io.BytesIO(buf))
                    arr = np.array(img)
                    if arr.ndim == 2:
                        arr = np.stack([arr, arr, arr], axis=-1)
                    return arr
                except Exception:
                    pass
            except Exception:
                pass
    except Exception:
        pass
    return np.zeros((height, width, 3), dtype=np.uint8)
