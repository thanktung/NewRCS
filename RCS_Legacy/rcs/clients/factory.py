"""
factory.py - Creates the clients a Scheduler needs.

The Scheduler never instantiates sockets itself: it asks a factory. Tests pass
a factory that returns in-memory fakes, so the whole scheduling logic can be
tested without any hardware or network.

A factory is any object with:
    create_robot(cfg) -> robot   (connect, close, reconnect, execute,
                                  connected, supports_batch, query_status)
    create_box(box_id, cfg) -> box (start, stop, load, unload, connected)
"""

from __future__ import annotations

from ..config import StationConfig
from ..protocol import get_codec
from .box_client import BoxClient
from .robot_client import RobotGateway


class TcpClientFactory:
    """Real TCP clients (talk to hardware or to the simulators in sim/)."""

    def create_robot(self, cfg: StationConfig) -> RobotGateway:
        return RobotGateway(
            cfg.robot_host, cfg.robot_port, get_codec(cfg.protocol),
            ack_timeout=cfg.robot_ack_timeout,
            done_timeout=cfg.robot_done_timeout,
            connect_timeout=cfg.box_connect_timeout,
        )

    def create_box(self, box_id: int, cfg: StationConfig) -> BoxClient:
        return BoxClient(
            box_id, cfg.box_address[box_id],
            connect_timeout=cfg.box_connect_timeout,
            recv_timeout=cfg.box_recv_timeout,
            reconnect_backoff=cfg.box_reconnect_backoff,
        )
