"""End-to-end: real Scheduler + real TCP clients + the simulators on localhost."""

import unittest

from rcs.clients.factory import TcpClientFactory
from rcs.core.scheduler import Scheduler
from rcs.models import SystemState as S
from sim.box_simulator import SimBox
from sim.robot_simulator import SimRobot
from tests.fakes import all_board_ids, make_cfg, wait_until


class E2EBase(unittest.TestCase):
    N_BOXES = 6

    def start_station(self, protocol="legacy", **cfg_kw):
        self.boxes = [SimBox(i, test_time=(0.05, 0.12), fail_rate=0.2,
                             ready_delay=0.02).start()
                      for i in range(1, self.N_BOXES + 1)]
        self.robot = SimRobot(protocol=protocol, move_time=0.005).start()
        kw = dict(
            box_count=self.N_BOXES, gripper_heads=4, tray_cols=3, tray_rows=2,
            ng_tray_slots=100,
            box_address={b.box_id: ("127.0.0.1", b.port) for b in self.boxes},
            robot_port=self.robot.port, protocol=protocol,
            robot_done_timeout=2.0, robot_ack_timeout=1.0,
            box_recv_timeout=2.0, box_connect_timeout=1.0)
        kw.update(cfg_kw)
        cfg = make_cfg(**kw)
        self.sched = Scheduler(cfg, TcpClientFactory())
        self.addCleanup(self._cleanup)
        self.sched.start()

    def _cleanup(self):
        self.sched.emergency_stop()
        self.robot.stop()
        for b in self.boxes:
            b.stop()

    def assertHealthy(self):
        self.assertEqual(self.sched.sm.state, S.RUNNING, self.sched.snapshot().fault)
        ids = all_board_ids(self.sched)
        self.assertEqual(len(ids), len(set(ids)))


class LegacyProtocolE2E(E2EBase):
    def test_runs_many_cycles_without_fault(self):
        self.start_station("legacy")
        ok = wait_until(lambda: self.sched.stats["change"] >= 2 and
                        self.sched.stats["pass"] >= 15, timeout=30)
        self.assertTrue(ok, f"{self.sched.stats} {self.sched.snapshot().fault}")
        self.assertHealthy()
        self.assertTrue(self.sched.stats["ng"] > 0)             # 20% fail rate
        self.assertFalse(any("|" in c for c in self.robot.commands))   # no batch


class V2ProtocolE2E(E2EBase):
    def test_v2_with_batch_runs_without_fault(self):
        self.start_station("v2", batch_enabled=True, batch_max_items=3,
                           heartbeat_interval=0.1)
        ok = wait_until(lambda: self.sched.stats["change"] >= 2 and
                        self.sched.stats["pass"] >= 15, timeout=30)
        self.assertTrue(ok, f"{self.sched.stats} {self.sched.snapshot().fault}")
        self.assertHealthy()
        self.assertTrue(any("|" in c for c in self.robot.commands), "no batch was sent")
        self.assertTrue(any("STATUS" in c for c in self.robot.commands), "no heartbeat")

    def test_v2_robot_error_code_reaches_the_fault_message(self):
        self.start_station("v2")
        self.robot.inject_error("PICK", index=0, code="COLLISION")
        self.assertTrue(wait_until(lambda: self.sched.sm.state == S.FAULT))
        self.assertIn("COLLISION", self.sched.snapshot().fault)

    def test_v2_silent_robot_times_out_into_fault_without_resend(self):
        self.start_station("v2", robot_done_timeout=0.5)
        self.robot.hang_next()
        self.assertTrue(wait_until(lambda: self.sched.sm.state == S.FAULT, timeout=10))
        picks = [c for c in self.robot.commands if " PICK" in c]
        self.assertEqual(len(picks), 1)

    def test_fault_acknowledge_and_resume_over_real_sockets(self):
        self.start_station("v2", robot_done_timeout=0.5)
        self.robot.hang_next()
        self.assertTrue(wait_until(lambda: self.sched.sm.state == S.FAULT, timeout=10))
        self.sched.acknowledge_fault()
        self.assertEqual(self.sched.sm.state, S.PAUSED)
        before = self.sched.stats["loaded"]
        self.sched.resume()
        self.assertTrue(wait_until(lambda: self.sched.stats["loaded"] > before, timeout=10))


class BoxNetworkE2E(E2EBase):
    def test_box_drop_and_reconnect_while_running(self):
        self.start_station("legacy", box_reconnect_backoff=0.1)
        self.assertTrue(wait_until(lambda: self.sched.stats["loaded"] >= 3, timeout=10))
        self.boxes[2].drop_connections()
        self.assertTrue(wait_until(
            lambda: "box3_conn" in self.sched.snapshot().alerts, timeout=5))
        self.assertTrue(wait_until(
            lambda: "box3_conn" not in self.sched.snapshot().alerts, timeout=8))


if __name__ == "__main__":
    unittest.main()

