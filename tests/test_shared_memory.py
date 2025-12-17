import unittest
import numpy as np
from procvision_algorithm_sdk.shared_memory import write_image_array_to_shared_memory, read_image_from_shared_memory, dev_write_image_to_shared_memory


class TestSharedMemory(unittest.TestCase):
    def test_array_roundtrip_rgb(self):
        shm = "dev-shm:test1"
        arr = np.zeros((10, 12, 3), dtype=np.uint8)
        arr[0, 0] = np.array([10, 20, 30], dtype=np.uint8)
        write_image_array_to_shared_memory(shm, arr)
        meta = {"width": 12, "height": 10, "timestamp_ms": 0, "camera_id": "cam", "color_space": "RGB"}
        img = read_image_from_shared_memory(shm, meta)
        self.assertEqual(img.shape, (10, 12, 3))
        self.assertEqual(int(img[0, 0, 0]), 10)

    def test_bytes_fallback_zero_matrix(self):
        shm = "dev-shm:test2"
        dev_write_image_to_shared_memory(shm, b"\x00invalid")
        meta = {"width": 8, "height": 6, "timestamp_ms": 0, "camera_id": "cam", "color_space": "RGB"}
        img = read_image_from_shared_memory(shm, meta)
        self.assertEqual(img.shape, (6, 8, 3))


if __name__ == "__main__":
    unittest.main()
