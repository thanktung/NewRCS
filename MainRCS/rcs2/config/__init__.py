"""Cài đặt của NewRCS: một file JSON deep-merge đè lên DEFAULTS (xem config/README.md)."""
from .defaults import DEFAULTS
from .loader import LEGACY_KEYS, detect_local_ip, env_secret, load_settings, resolve_local_ip

__all__ = ["DEFAULTS", "LEGACY_KEYS", "detect_local_ip", "env_secret", "load_settings", "resolve_local_ip"]
