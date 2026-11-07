"""Ed25519（RFC 8032）判据：黄金向量 + 确定性 + 篡改必拒 + 与独立实现交叉验证。

为什么值得单开判据：这是本仓**第一次**引入非对称签名面（吊销件的跨组织可信性）。
错一位就会「签名能自验、别人验不过」——那种错必须由**外部已知答案**抓，不能自证。
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import ed25519  # noqa: E402

# RFC 8032 §7.1 TEST 1（空消息）——外部已知答案，不是我们自己算出来的
SEED1 = bytes.fromhex("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60")
PUB1 = bytes.fromhex("d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a")
SIG1 = bytes.fromhex(
    "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e0652249015"
    "55fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b")


class Rfc8032GoldenTest(unittest.TestCase):
    def test_test1_public_key(self):
        self.assertEqual(PUB1, ed25519.public_key(SEED1))

    def test_test1_signature(self):
        self.assertEqual(SIG1, ed25519.sign(SEED1, b""))

    def test_test1_verify(self):
        self.assertTrue(ed25519.verify(PUB1, b"", SIG1))


class SignVerifyTest(unittest.TestCase):
    def test_round_trip_on_arbitrary_message(self):
        msg = "吊销：对象 AIGC 标识缺失".encode()
        pub = ed25519.public_key(SEED1)
        sig = ed25519.sign(SEED1, msg)
        self.assertEqual(64, len(sig))
        self.assertTrue(ed25519.verify(pub, msg, sig))

    def test_signature_is_deterministic(self):
        self.assertEqual(ed25519.sign(SEED1, b"x"), ed25519.sign(SEED1, b"x"))

    def test_tampered_message_rejected(self):
        pub, sig = ed25519.public_key(SEED1), ed25519.sign(SEED1, b"payload")
        self.assertFalse(ed25519.verify(pub, b"payload!", sig))

    def test_tampered_signature_rejected(self):
        pub, sig = ed25519.public_key(SEED1), ed25519.sign(SEED1, b"payload")
        broken = bytearray(sig)
        broken[0] ^= 0x01
        self.assertFalse(ed25519.verify(pub, b"payload", bytes(broken)))

    def test_wrong_key_rejected(self):
        sig = ed25519.sign(SEED1, b"payload")
        other = ed25519.public_key(bytes(32))
        self.assertFalse(ed25519.verify(other, b"payload", sig))

    def test_shape_edges_rejected(self):
        pub, sig = ed25519.public_key(SEED1), ed25519.sign(SEED1, b"m")
        self.assertFalse(ed25519.verify(b"", b"m", sig))
        self.assertFalse(ed25519.verify(pub, b"m", sig[:63]))
        self.assertFalse(ed25519.verify(pub, b"m", sig + b"\x00"))
        with self.assertRaises(ValueError):
            ed25519.public_key(b"short")

    def test_s_ge_l_rejected(self):
        """S >= L 不是合法签名（RFC 8032 §5.1.7 要求严格拒绝，防延展性）。"""
        pub = ed25519.public_key(SEED1)
        bad = SIG1[:32] + int.to_bytes(ed25519.L, 32, "little")
        self.assertFalse(ed25519.verify(pub, b"", bad))


def _cryptography_ed25519():
    try:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ed25519 as ref
    except ImportError:
        return None
    return ref, serialization


class CrossImplementationTest(unittest.TestCase):
    """与 cryptography 库交叉验证（它不在场就跳过——不冒充已验）。"""

    def setUp(self):
        mods = _cryptography_ed25519()
        if mods is None:
            self.skipTest("环境无 cryptography：跳过交叉验证（黄金向量已覆盖 RFC 一致性）")
        self.ref, self.ser = mods

    def _ref_keypair(self, seed: bytes):
        priv = self.ref.Ed25519PrivateKey.from_private_bytes(seed)
        pub = priv.public_key().public_bytes(self.ser.Encoding.Raw,
                                             self.ser.PublicFormat.Raw)
        return priv, pub

    def test_our_signature_verifies_in_reference(self):
        msg = b"cross-check payload"
        seed = bytes(range(32))
        _priv, pub = self._ref_keypair(seed)
        sig = ed25519.sign(seed, msg)
        _priv.public_key().verify(sig, msg)      # cryptography 认我们的签名
        self.assertEqual(pub, ed25519.public_key(seed))

    def test_reference_signature_verifies_here(self):
        msg = b"cross-check payload"
        seed = bytes(range(32))
        priv, pub = self._ref_keypair(seed)
        sig = priv.sign(msg)
        self.assertTrue(ed25519.verify(pub, msg, sig))


if __name__ == "__main__":
    unittest.main()
