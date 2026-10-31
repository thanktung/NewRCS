"""Client-side protocol helpers (the bridge/client constants are compared in test_bridge_simple.py)."""
import unittest

from rcs2.robot import protocol as P


class ProtocolTest(unittest.TestCase):
    def test_encode_decode_roundtrip(self):
        msg = {"id": 1, "cmd": "ping", "args": {"x": "é"}}
        raw = P.encode(msg)
        self.assertTrue(raw.endswith(b"\n"))
        self.assertEqual(raw.count(b"\n"), 1)                 # exactly one line per message
        self.assertEqual(P.decode(raw), msg)

    def test_decode_rejects_non_objects(self):
        with self.assertRaises(ValueError):
            P.decode(b"[1,2,3]\n")


if __name__ == "__main__":
    unittest.main()
