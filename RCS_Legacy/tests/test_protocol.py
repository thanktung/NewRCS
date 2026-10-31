import unittest

from rcs.protocol import commands as C
from rcs.protocol import get_codec, robot_legacy, robot_v2
from rcs.protocol.box import parse_state
from rcs.models import BoxState


class CommandTests(unittest.TestCase):
    def test_item_arity_checked(self):
        with self.assertRaises(ValueError):
            C.pick((1, 2))            # needs 3 ints
        with self.assertRaises(ValueError):
            C.RobotCommand(C.CHANGE, ((1,),))
        with self.assertRaises(ValueError):
            C.RobotCommand(C.PICK)    # needs items

    def test_change_cannot_batch(self):
        with self.assertRaises(ValueError):
            C.RobotCommand(C.CHANGE, ((1,), (2,)))

    def test_motion_flags(self):
        self.assertTrue(C.pick((1, 0, 0)).is_motion)
        self.assertTrue(C.change().is_motion)
        self.assertFalse(C.status().is_motion)

    def test_str(self):
        self.assertEqual(str(C.pick((1, 5, 0), (1, 6, 1))), "PICK:1,5,0|1,6,1")
        self.assertEqual(str(C.change()), "CHANGE")


class LegacyCodecTests(unittest.TestCase):
    def test_encode_matches_old_wire_format(self):
        self.assertEqual(robot_legacy.encode(C.pick((1, 7, 2)), 1), "PICK:1,7,2;")
        self.assertEqual(robot_legacy.encode(C.load((3, 0)), 9), "LOAD:3,0;")
        self.assertEqual(robot_legacy.encode(C.place((0, 4, 1)), 9), "PLACE:0,4,1;")
        self.assertEqual(robot_legacy.encode(C.change(), 1), "CHANGE;")

    def test_no_batch_no_status(self):
        with self.assertRaises(ValueError):
            robot_legacy.encode(C.pick((1, 0, 0), (1, 1, 1)), 1)
        with self.assertRaises(ValueError):
            robot_legacy.encode(C.status(), 1)

    def test_parse(self):
        r = robot_legacy.parse("DONE:PICK\r")
        self.assertEqual((r.kind, r.name), (C.DONE, "PICK"))
        self.assertEqual(robot_legacy.parse("DONE").name, "")
        self.assertEqual(robot_legacy.parse("hello").kind, C.OTHER)


class V2CodecTests(unittest.TestCase):
    def test_encode(self):
        self.assertEqual(robot_v2.encode(C.pick((1, 5, 2)), 12), "#12 PICK:1,5,2;")
        self.assertEqual(robot_v2.encode(C.pick((1, 5, 0), (1, 6, 1)), 13),
                         "#13 PICK:1,5,0|1,6,1;")
        self.assertEqual(robot_v2.encode(C.change(), 14), "#14 CHANGE;")
        self.assertEqual(robot_v2.encode(C.status(), 15), "#15 STATUS;")

    def test_parse_replies(self):
        self.assertEqual(robot_v2.parse("ACK:12"), C.Reply(C.ACK, seq=12, raw="ACK:12"))
        d = robot_v2.parse("DONE:12:pick")
        self.assertEqual((d.kind, d.seq, d.name), (C.DONE, 12, "PICK"))
        e = robot_v2.parse("ERR:13:PICK:1:VAC_FAIL")
        self.assertEqual((e.kind, e.seq, e.name, e.index, e.code),
                         (C.ERR, 13, "PICK", 1, "VAC_FAIL"))
        s = robot_v2.parse("STAT:15:BUSY")
        self.assertEqual((s.kind, s.seq, s.code), (C.STAT, 15, "BUSY"))

    def test_garbage_never_raises(self):
        for line in ("", "ACK", "ACK:x", "DONE:1", "ERR:1:PICK:x:Y", "STAT:1", "###"):
            self.assertEqual(robot_v2.parse(line).kind, C.OTHER, line)

    def test_legacy_done_is_not_a_v2_reply(self):
        self.assertEqual(robot_v2.parse("DONE:PICK").kind, C.OTHER)


class MiscTests(unittest.TestCase):
    def test_get_codec(self):
        self.assertIs(get_codec("legacy"), robot_legacy)
        self.assertIs(get_codec("v2"), robot_v2)
        with self.assertRaises(ValueError):
            get_codec("nope")

    def test_box_state_parse(self):
        self.assertEqual(parse_state("ready_for_test\r"), BoxState.READY)
        self.assertEqual(parse_state("PASS"), BoxState.PASS)
        self.assertIsNone(parse_state("OK"))
        self.assertIsNone(parse_state("BUSY"))


if __name__ == "__main__":
    unittest.main()
