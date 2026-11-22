import unittest
from capability import Grant, allows, normalize


class CapabilityTest(unittest.TestCase):
    def test_read_only(self):
        g = Grant(frozenset({"read"}))
        self.assertTrue(allows(g, "read", 0))
        self.assertFalse(allows(g, "comment", 0))
        self.assertFalse(allows(g, "reassemble", 0))

    def test_reassemble(self):
        g = Grant(frozenset({"read", "reassemble"}))
        self.assertTrue(allows(g, "reassemble", 0))
        self.assertFalse(allows(g, "export", 0))

    def test_admin(self):
        g = Grant(frozenset({"admin"}))
        for cap in ("read", "comment", "reassemble", "export", "share"):
            self.assertTrue(allows(g, cap, 0))

    def test_expiry(self):
        g = Grant(frozenset({"read"}), expires_at=100)
        self.assertTrue(allows(g, "read", 99))
        self.assertFalse(allows(g, "read", 100))

    def test_revoked(self):
        g = Grant(frozenset({"read"}), revoked=True)
        self.assertFalse(allows(g, "read", 0))

    def test_unknown_cap(self):
        self.assertFalse(allows(Grant(frozenset({"read"})), "write", 0))

    def test_unknown_grant_rejected(self):
        with self.assertRaises(ValueError):
            normalize({"read", "write"})

    def test_empty(self):
        self.assertFalse(allows(Grant(), "read", 0))


if __name__ == "__main__":
    unittest.main()
