import unittest
from procvision_algorithm_sdk.shared_memory import dev_write_image_to_shared_memory, read_image_from_shared_memory


class TestSharedMemory(unittest.TestCase):
    def test_read_image_fallback(self):
        shm_id = "dev-shm:test"
        dev_write_image_to_shared_memory(shm_id, b"not-an-image")
        meta = {"width": 320, "height": 240, "timestamp_ms": 0, "camera_id": "cam"}
        img = read_image_from_shared_memory(shm_id, meta)
        self.assertIsNotNone(img)
        self.assertEqual(tuple(img.shape), (240, 320, 3))


if __name__ == "__main__":
    unittest.main()