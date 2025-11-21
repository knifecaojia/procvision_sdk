import unittest
from procvision_algorithm_sdk.session import Session


class TestSession(unittest.TestCase):
    def test_set_get_delete_exists(self):
        s = Session("sid-1", {"product_code": "p001"})
        self.assertEqual(s.id, "sid-1")
        ctx = s.context
        self.assertEqual(ctx["product_code"], "p001")
        s.set("k1", {"a": 1})
        self.assertTrue(s.exists("k1"))
        self.assertEqual(s.get("k1")["a"], 1)
        self.assertTrue(s.delete("k1"))
        self.assertFalse(s.exists("k1"))

    def test_set_non_serializable_raises(self):
        s = Session("sid-2")
        with self.assertRaises(TypeError):
            s.set("bad", set([1, 2, 3]))


if __name__ == "__main__":
    unittest.main()