"""
net.py - Small socket helpers shared by BoxClient and RobotGateway.
"""

from __future__ import annotations

import socket
from typing import Optional


class LineReader:
    """Accumulates bytes from a socket and yields complete text lines.

    The socket must have a short timeout so callers can poll a stop flag.
    Only ONE thread may call read_line() on a given LineReader.
    """

    def __init__(self) -> None:
        self._buf = b""

    def clear(self) -> None:
        self._buf = b""

    def read_line(self, sock: socket.socket) -> Optional[str]:
        """Return one stripped line, None on socket timeout.

        Raises ConnectionError when the peer closed the connection.
        """
        while b"\n" not in self._buf:
            try:
                data = sock.recv(1024)
            except socket.timeout:
                return None
            if not data:
                raise ConnectionError("peer closed the connection")
            self._buf += data
        raw, self._buf = self._buf.split(b"\n", 1)
        return raw.decode("utf-8", errors="replace").strip()


def open_connection(address: tuple, connect_timeout: float,
                    io_timeout: float) -> socket.socket:
    """Connect with a timeout (the OS default can block ~20 s) and set TCP_NODELAY."""
    sock = socket.create_connection(address, timeout=connect_timeout)
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    sock.settimeout(io_timeout)
    return sock


def close_quietly(sock: Optional[socket.socket]) -> None:
    if sock is None:
        return
    try:
        sock.shutdown(socket.SHUT_RDWR)
    except OSError:
        pass
    try:
        sock.close()
    except OSError:
        pass
