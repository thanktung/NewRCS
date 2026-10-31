"""Wire protocols (pure functions, no I/O)."""

from . import robot_legacy, robot_v2


def get_codec(name: str):
    """Return the codec module for a protocol name ('legacy' | 'v2')."""
    codecs = {robot_legacy.NAME: robot_legacy, robot_v2.NAME: robot_v2}
    try:
        return codecs[name]
    except KeyError:
        raise ValueError(f"unknown robot protocol '{name}'") from None
