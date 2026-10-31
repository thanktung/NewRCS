import threading
import time
import unittest

from rcs.clients.box_client import BoxClient
from rcs.clients.errors import (BoxNotConnected, RobotCommandError,
                                RobotConnectionError, RobotProtocolError,
                                RobotTimeout)
from rcs.clients.robot_client import RobotGateway
from rcs.models import BoxState
from rcs.protocol import commands as C
from rcs.protocol import robot_legacy, robot_v2
from sim.box_simulator import SimBox
from sim.robot_simulator import SimRobot


def wait_until(pred, timeout=3.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if pred():
            return True
        time.sleep(0.02)
    return False


class RobotV2Tests(unittest.TestCase):
    def setUp(self):
        self.sim = SimRobot(protocol="v2", move_time=0.01).start()
        self.gw = RobotGateway("127.0.0.1", self.sim.port, robot_v2,
                               ack_timeout=0.4, done_timeout=1.0)
        self.gw.connect()

    def tearDown(self):
        self.gw.close()
        self.sim.stop()

    def test_single_command(self):
        r = self.gw.execute(C.pick((1, 5, 2)))
        self.assertEqual((r.kind, r.name), (C.DONE, "PICK"))
        self.assertEqual(self.sim.executed, [("PICK", (1, 5, 2))])

    def test_batch_executes_all_items_in_order(self):
        self.gw.execute(C.pick((1, 0, 0), (1, 1, 1), (1, 2, 2)))
        self.assertEqual([i for _, i in self.sim.executed],
                         [(1, 0, 0), (1, 1, 1), (1, 2, 2)])

    def test_err_reports_failing_item_and_stops(self):
        self.sim.inject_error("PICK", index=1, code="VAC_FAIL")
        with self.assertRaises(RobotCommandError) as cm:
            self.gw.execute(C.pick((1, 0, 0), (1, 1, 1), (1, 2, 2)))
        self.assertEqual((cm.exception.index, cm.exception.code), (1, "VAC_FAIL"))
        # item 0 done, items 1 and 2 NOT executed
        self.assertEqual([i for _, i in self.sim.executed], [(1, 0, 0)])

    def test_timeout_when_robot_silent_and_no_resend(self):
        self.sim.hang_next()
        with self.assertRaises(RobotTimeout):
            self.gw.execute(C.pick((1, 0, 0)))
        # exactly ONE PICK line was sent: motion commands are never re-sent
        self.assertEqual(sum(1 for c in self.sim.commands if "PICK" in c), 1)

    def test_late_reply_does_not_pollute_next_command(self):
        # Command 1 times out; the robot then answers late. The next command
        # must still get ITS OWN reply (sequence numbers), not the stale one.
        slow = SimRobot(protocol="v2", move_time=0.3).start()
        gw = RobotGateway("127.0.0.1", slow.port, robot_v2,
                          ack_timeout=0.5, done_timeout=0.1)
        gw.connect()
        try:
            with self.assertRaises(RobotTimeout):
                gw.execute(C.pick((1, 0, 0)))            # DONE:1 arrives after 0.3 s
            gw._done_timeout = 3.0
            reply = gw.execute(C.load((2, 0)))           # stale DONE:1 must be dropped
            self.assertEqual((reply.name, reply.seq), ("LOAD", 2))
        finally:
            gw.close()
            slow.stop()
    def test_status_answered_while_busy(self):
        sim = SimRobot(protocol="v2", move_time=0.4).start()
        gw = RobotGateway("127.0.0.1", sim.port, robot_v2,
                          ack_timeout=0.5, done_timeout=3.0)
        gw.connect()
        try:
            t = threading.Thread(target=lambda: gw.execute(C.pick((1, 0, 0))))
            t.start()
            self.assertTrue(wait_until(lambda: sim._busy))
            self.assertEqual(gw.query_status(), "BUSY")
            t.join()
            self.assertEqual(gw.query_status(), "IDLE")
        finally:
            gw.close()
            sim.stop()

    def test_alarm_status_and_motion_error(self):
        self.sim.set_alarm(True)
        self.assertEqual(self.gw.query_status(), "ALARM")
        with self.assertRaises(RobotCommandError) as cm:
            self.gw.execute(C.pick((1, 0, 0)))
        self.assertEqual(cm.exception.code, "ALARM")

    def test_connection_lost_raises(self):
        self.sim.drop_connection()
        time.sleep(0.4)
        with self.assertRaises(RobotConnectionError):
            self.gw.execute(C.pick((1, 0, 0)))
        self.assertFalse(self.gw.connected)

    def test_connection_lost_during_command_wakes_waiter(self):
        self.sim.hang_next()
        threading.Timer(0.15, self.sim.drop_connection).start()
        with self.assertRaises(RobotConnectionError):
            self.gw.execute(C.pick((1, 0, 0)))


class RobotLegacyTests(unittest.TestCase):
    def setUp(self):
        self.sim = SimRobot(protocol="legacy", move_time=0.01).start()
        self.gw = RobotGateway("127.0.0.1", self.sim.port, robot_legacy,
                               ack_timeout=0.4, done_timeout=0.5)
        self.gw.connect()

    def tearDown(self):
        self.gw.close()
        self.sim.stop()

    def test_done_matches_command(self):
        self.gw.execute(C.load((3, 1)))
        self.assertEqual(self.sim.commands, ["LOAD:3,1;"])

    def test_timeout_does_not_resend(self):
        self.sim.hang_next()
        with self.assertRaises(RobotTimeout):
            self.gw.execute(C.change())
        self.assertEqual(len(self.sim.commands), 1)

    def test_wrong_done_is_protocol_error(self):
        # Robot (mis)answers DONE:PLACE to a PICK
        sim = SimRobot(protocol="legacy", move_time=0.0).start()
        orig = sim._run_command

        def wrong(seq, name, items):
            sim._send("DONE:PLACE")
        sim._run_command = wrong
        gw = RobotGateway("127.0.0.1", sim.port, robot_legacy, done_timeout=1.0)
        gw.connect()
        try:
            with self.assertRaises(RobotProtocolError):
                gw.execute(C.pick((1, 0, 0)))
        finally:
            gw.close()
            sim.stop()

    def test_batch_rejected(self):
        with self.assertRaises(ValueError):
            self.gw.execute(C.pick((1, 0, 0), (1, 1, 1)))


class BoxClientTests(unittest.TestCase):
    def setUp(self):
        self.box = SimBox(1, test_time=(0.1, 0.1), fail_rate=0.0,
                          ready_delay=0.02).start()
        self.states = []
        self.conn = []
        self.client = BoxClient(1, ("127.0.0.1", self.box.port),
                                connect_timeout=1.0, recv_timeout=1.0,
                                reconnect_backoff=0.1)

    def tearDown(self):
        self.client.stop()
        self.box.stop()

    def _start(self):
        self.client.start(lambda i, s: self.states.append(s),
                          lambda i, up: self.conn.append(up))

    def test_state_pushed_on_connect(self):
        self._start()
        self.assertTrue(wait_until(lambda: BoxState.EMPTY in self.states))
        self.assertTrue(self.client.connected)
        self.assertEqual(self.conn[0], True)

    def test_load_then_full_cycle_and_unload(self):
        self._start()
        self.assertTrue(wait_until(lambda: self.client.connected))
        self.assertEqual(self.client.load(), "OK")
        self.assertTrue(wait_until(lambda: BoxState.PASS in self.states))
        self.assertEqual(self.client.unload(), "OK")
        self.assertTrue(wait_until(lambda: self.states[-1] == BoxState.EMPTY))

    def test_rejected_commands_are_visible(self):
        self._start()
        self.assertTrue(wait_until(lambda: self.client.connected))
        self.assertEqual(self.client.unload(), "NOT_READY")   # box is empty
        self.assertEqual(self.client.load(), "OK")
        self.assertEqual(self.client.load(), "BUSY")          # already loaded

    def test_not_connected_raises(self):
        with self.assertRaises(BoxNotConnected):
            self.client.load()

    def test_auto_reconnect_after_drop(self):
        self._start()
        self.assertTrue(wait_until(lambda: self.client.connected))
        self.box.drop_connections()
        self.assertTrue(wait_until(lambda: False in self.conn))
        self.assertTrue(wait_until(lambda: self.client.connected, timeout=3.0))
        self.assertEqual(self.client.load(), "OK")

    def test_unreachable_box_does_not_block_start(self):
        dead = BoxClient(2, ("127.0.0.1", 1), connect_timeout=0.3,
                         recv_timeout=0.3, reconnect_backoff=0.1)
        t0 = time.monotonic()
        dead.start(lambda *_: None)
        self.assertLess(time.monotonic() - t0, 0.2)     # start() is non-blocking
        dead.stop()


if __name__ == "__main__":
    unittest.main()

