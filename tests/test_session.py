import unittest
from procvision_algorithm_sdk.session import Session


class TestSession(unittest.TestCase):
    def test_kv_ops(self):
        s = Session("sid", {"a": 1})
        self.assertEqual(s.id, "sid")
        self.assertEqual(s.context.get("a"), 1)
        self.assertFalse(s.exists("k"))
        s.set("k", {"x": 1})
        self.assertTrue(s.exists("k"))
        self.assertEqual(s.get("k").get("x"), 1)
        self.assertTrue(s.delete("k"))
        self.assertFalse(s.exists("k"))

    def test_set_raises_on_non_serializable(self):
        s = Session("sid")
        with self.assertRaises(TypeError):
            s.set("x", set([1, 2]))


if __name__ == "__main__":
    unittest.main()
