"""
config.py - Station configuration.

Reads station.ini + FixtureIP.ini into an immutable StationConfig object.
There are NO module-level constants: every component receives the config
object explicitly, so several stations (several StationConfig instances)
can live in one process.

Validation raises ConfigError (never `assert`, which is stripped by -O).
"""

from __future__ import annotations

import configparser
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).resolve().parent.parent

# Hard system limits (hardware / protocol). NOT station specific.
MAX_BOX_COUNT = 30
MAX_GRIPPER_HEADS = 15
MAX_TRAY_COLS = 20
MAX_TRAY_ROWS = 20

MODES = ("sim", "real")
PROTOCOLS = ("legacy", "v2")
PLACE_POLICIES = ("tray1", "origin")


class ConfigError(ValueError):
    """Raised when station.ini / FixtureIP.ini is invalid."""


@dataclass(frozen=True)
class StationConfig:
    # --- system ---
    station_name: str = "Station"
    mode: str = "sim"                       # sim | real

    # --- network ---
    box_host: str = "127.0.0.1"
    box_start_port: int = 5001
    robot_host: str = "127.0.0.1"
    robot_port: int = 6000
    box_address: dict = field(default_factory=dict)  # box_id -> (host, port)

    # --- scale ---
    box_count: int = 30
    gripper_heads: int = 8
    tray_cols: int = 8
    tray_rows: int = 5
    ng_tray_slots: int = 40
    box_layout: tuple = ()                  # ((label, (ids...)), ...)

    # --- timing ---
    poll_interval: float = 0.2              # safety wake-up of the scheduler loop
    box_recv_timeout: float = 5.0
    box_connect_timeout: float = 3.0
    box_reconnect_backoff: float = 2.0      # first retry delay (doubles up to 30 s)

    # --- robot ---
    protocol: str = "legacy"                # legacy | v2
    robot_ack_timeout: float = 3.0          # v2 only
    robot_done_timeout: float = 30.0        # legacy: recv timeout, v2: DONE timeout
    robot_max_retries: int = 3              # legacy only
    batch_enabled: bool = False             # v2 only
    batch_max_items: int = 4
    heartbeat_interval: float = 0.0         # v2 only, 0 = off

    # --- policy ---
    place_policy: str = "tray1"             # tray1 | origin
    box_fail_streak_limit: int = 0          # 0 = never auto-disable
    retest_ng: bool = False                 # re-test NG in another box once

    # --- watchdog ---
    test_timeout_sec: float = 0.0           # 0 = off
    ready_timeout_sec: float = 0.0          # 0 = off

    # --- paths ---
    state_file: Path = BASE_DIR / "station_last_state.json"
    log_dir: Path = BASE_DIR / "logs"
    results_dir: Path = BASE_DIR / "logs"

    @property
    def tray_slots(self) -> int:
        return self.tray_cols * self.tray_rows


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Parsing helpers
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def _new_parser() -> configparser.ConfigParser:
    cp = configparser.ConfigParser(inline_comment_prefixes=(";",))
    cp.optionxform = str        # keep key case ("Side A")
    return cp


def _parse_range(spec: str) -> tuple:
    """'25-30' -> (25, 26, ..., 30)"""
    try:
        a, b = spec.split("-")
        return tuple(range(int(a.strip()), int(b.strip()) + 1))
    except ValueError as e:
        raise ConfigError(f"[layout] bad range '{spec}', expected 'start-end'") from e


def _parse_bool(text: str, key: str) -> bool:
    t = text.strip().lower()
    if t in ("1", "true", "yes", "on"):
        return True
    if t in ("0", "false", "no", "off", ""):
        return False
    raise ConfigError(f"{key}: '{text}' is not a boolean")


def load_fixture_ips(path: Path) -> dict:
    """FixtureIP.ini -> {box_id: (ip, port)}. Missing file -> {}."""
    if not path.exists():
        return {}
    cp = _new_parser()
    cp.read(path, encoding="utf-8-sig")
    result: dict = {}
    if cp.has_section("fixtures"):
        for key, value in cp.items("fixtures"):
            try:
                box_id = int(key)
            except ValueError as e:
                raise ConfigError(f"FixtureIP.ini: key '{key}' is not a box id") from e
            if ":" not in value:
                raise ConfigError(
                    f"FixtureIP.ini: box {key} = '{value}' missing port (use ip:port)"
                )
            ip, port = value.rsplit(":", 1)
            result[box_id] = (ip.strip(), int(port.strip()))
    return result


def _resolve_path(text: str, default: Path) -> Path:
    if not text.strip():
        return default
    p = Path(text.strip())
    return p if p.is_absolute() else BASE_DIR / p


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Public API
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def load_config(ini_path: Optional[Path] = None,
                fixture_path: Optional[Path] = None) -> StationConfig:
    ini_path = Path(ini_path) if ini_path else BASE_DIR / "station.ini"
    fixture_path = Path(fixture_path) if fixture_path else BASE_DIR / "FixtureIP.ini"
    if not ini_path.exists():
        raise ConfigError(f"station.ini not found: {ini_path}")

    cp = _new_parser()
    cp.read(ini_path, encoding="utf-8-sig")

    def get(section, key, default):
        return cp.get(section, key, fallback=default)

    mode = get("system", "mode", "sim").strip().lower()
    box_host = cp.get("network", "box_host")
    box_start_port = cp.getint("network", "box_start_port")
    box_count = cp.getint("scale", "box_count")

    # Per-box address: real fixtures use FixtureIP.ini, sim uses box_host+port.
    fixtures = load_fixture_ips(fixture_path) if mode == "real" else {}
    box_address = {}
    for bid in range(1, box_count + 1):
        box_address[bid] = fixtures.get(bid, (box_host, box_start_port + bid - 1))

    tray_cols = cp.getint("tray", "cols")
    tray_rows = cp.getint("tray", "rows")
    ng_raw = get("tray", "ng_tray_slots", "").strip()
    ng_slots = int(ng_raw) if ng_raw else tray_cols * tray_rows

    layout = tuple(
        (label, _parse_range(rng)) for label, rng in cp.items("layout")
    ) if cp.has_section("layout") else ()

    cfg = StationConfig(
        station_name=get("system", "station_name", "Station").strip(),
        mode=mode,
        box_host=box_host,
        box_start_port=box_start_port,
        robot_host=cp.get("network", "robot_host"),
        robot_port=cp.getint("network", "robot_port"),
        box_address=box_address,
        box_count=box_count,
        gripper_heads=cp.getint("scale", "gripper_heads"),
        tray_cols=tray_cols,
        tray_rows=tray_rows,
        ng_tray_slots=ng_slots,
        box_layout=layout,
        poll_interval=cp.getfloat("timing", "poll_interval"),
        box_recv_timeout=cp.getfloat("timing", "box_recv_timeout"),
        box_connect_timeout=cp.getfloat("timing", "box_connect_timeout", fallback=3.0),
        box_reconnect_backoff=cp.getfloat("timing", "box_reconnect_backoff", fallback=2.0),
        protocol=get("robot", "protocol", "legacy").strip().lower(),
        robot_ack_timeout=cp.getfloat("robot", "ack_timeout", fallback=3.0),
        robot_done_timeout=cp.getfloat("timing", "robot_recv_timeout"),
        robot_max_retries=cp.getint("timing", "robot_max_retries"),
        batch_enabled=_parse_bool(get("robot", "batch_enabled", "0"), "robot.batch_enabled"),
        batch_max_items=cp.getint("robot", "batch_max_items", fallback=4),
        heartbeat_interval=cp.getfloat("robot", "heartbeat_interval", fallback=0.0),
        place_policy=get("policy", "place_policy", "tray1").strip().lower(),
        box_fail_streak_limit=cp.getint("policy", "box_fail_streak_limit", fallback=0),
        retest_ng=_parse_bool(get("policy", "retest_ng", "0"), "policy.retest_ng"),
        test_timeout_sec=cp.getfloat("watchdog", "test_timeout_sec", fallback=0.0),
        ready_timeout_sec=cp.getfloat("watchdog", "ready_timeout_sec", fallback=0.0),
        state_file=_resolve_path(get("paths", "state_file", ""),
                                 BASE_DIR / "station_last_state.json"),
        log_dir=_resolve_path(get("paths", "log_dir", ""), BASE_DIR / "logs"),
        results_dir=_resolve_path(get("paths", "results_dir", ""), BASE_DIR / "logs"),
    )
    validate(cfg)
    return cfg


def validate(cfg: StationConfig) -> None:
    """Raise ConfigError if the configuration is inconsistent."""
    if cfg.mode not in MODES:
        raise ConfigError(f"system.mode='{cfg.mode}', expected one of {MODES}")
    if cfg.protocol not in PROTOCOLS:
        raise ConfigError(f"robot.protocol='{cfg.protocol}', expected one of {PROTOCOLS}")
    if cfg.place_policy not in PLACE_POLICIES:
        raise ConfigError(
            f"policy.place_policy='{cfg.place_policy}', expected one of {PLACE_POLICIES}"
        )
    if cfg.batch_enabled and cfg.protocol != "v2":
        raise ConfigError("robot.batch_enabled requires robot.protocol = v2")
    if cfg.heartbeat_interval and cfg.protocol != "v2":
        raise ConfigError("robot.heartbeat_interval requires robot.protocol = v2")
    if cfg.batch_max_items < 1:
        raise ConfigError("robot.batch_max_items must be >= 1")

    if not 1 <= cfg.box_count <= MAX_BOX_COUNT:
        raise ConfigError(f"box_count={cfg.box_count} outside 1..{MAX_BOX_COUNT}")
    # The scheduler always keeps one head free for unloading -> need >= 2 heads.
    if not 2 <= cfg.gripper_heads <= MAX_GRIPPER_HEADS:
        raise ConfigError(
            f"gripper_heads={cfg.gripper_heads} outside 2..{MAX_GRIPPER_HEADS} "
            f"(one head is always kept free for unloading)"
        )
    if not (1 <= cfg.tray_cols <= MAX_TRAY_COLS and 1 <= cfg.tray_rows <= MAX_TRAY_ROWS):
        raise ConfigError(
            f"tray {cfg.tray_cols}x{cfg.tray_rows} outside max "
            f"{MAX_TRAY_COLS}x{MAX_TRAY_ROWS}"
        )
    if cfg.ng_tray_slots < 1:
        raise ConfigError("ng_tray_slots must be >= 1")

    covered = sorted(b for _, ids in cfg.box_layout for b in ids)
    if covered != list(range(1, cfg.box_count + 1)):
        raise ConfigError(
            f"[layout] must cover exactly 1..{cfg.box_count}, currently covers {covered}"
        )
    bad = sorted(b for b in cfg.box_address if not 1 <= b <= MAX_BOX_COUNT)
    if bad:
        raise ConfigError(f"box ids {bad} outside 1..{MAX_BOX_COUNT}")
    for name in ("poll_interval", "box_recv_timeout", "robot_done_timeout",
                 "robot_ack_timeout", "box_connect_timeout"):
        if getattr(cfg, name) <= 0:
            raise ConfigError(f"{name} must be > 0")
