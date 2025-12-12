import unittest
import numpy as np
from procvision_algorithm_sdk import write_image_array_to_shared_memory, read_image_from_shared_memory

class TestSharedMemoryArray(unittest.TestCase):
    def test_read_array_rgb_passthrough(self):
        shm_id = "dev-shm:rgb"
        arr = np.zeros((240, 320, 3), dtype=np.uint8)
        arr[0, 0] = np.array([10, 20, 30], dtype=np.uint8)
        write_image_array_to_shared_memory(shm_id, arr)
        meta = {"width": 320, "height": 240, "timestamp_ms": 0, "camera_id": "cam", "color_space": "RGB"}
        img = read_image_from_shared_memory(shm_id, meta)
        self.assertEqual(tuple(img.shape), (240, 320, 3))
        self.assertTrue((img[0, 0] == np.array([10, 20, 30], dtype=np.uint8)).all())

    def test_read_array_gray_expand(self):
        shm_id = "dev-shm:gray"
        arr = np.full((240, 320), 128, dtype=np.uint8)
        write_image_array_to_shared_memory(shm_id, arr)
        meta = {"width": 320, "height": 240, "timestamp_ms": 0, "camera_id": "cam"}
        img = read_image_from_shared_memory(shm_id, meta)
        self.assertEqual(tuple(img.shape), (240, 320, 3))
        self.assertEqual(int(img[0, 0, 0]), 128)
        self.assertEqual(int(img[0, 0, 1]), 128)
        self.assertEqual(int(img[0, 0, 2]), 128)

    def test_read_array_bgr_to_rgb(self):
        shm_id = "dev-shm:bgr"
        arr = np.zeros((2, 2, 3), dtype=np.uint8)
        arr[0, 0] = np.array([0, 0, 255], dtype=np.uint8)
        write_image_array_to_shared_memory(shm_id, arr)
        meta = {"width": 2, "height": 2, "timestamp_ms": 0, "camera_id": "cam", "color_space": "BGR"}
        img = read_image_from_shared_memory(shm_id, meta)
        self.assertEqual(tuple(img.shape), (2, 2, 3))
        self.assertTrue((img[0, 0] == np.array([255, 0, 0], dtype=np.uint8)).all())

if __name__ == "__main__":
    unittest.main()
