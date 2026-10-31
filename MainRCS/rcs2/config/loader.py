"""Nạp config/settings.json đè lên DEFAULTS, cùng vài hàm nhỏ phụ thuộc vào cài đặt / môi trường."""
import copy
import json
import os
import socket

from .defaults import DEFAULTS


def _merge(base, extra):
    for key, value in extra.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict) and key != "fixtures":
            _merge(base[key], value)
        else:
            base[key] = value
    return base


LEGACY_KEYS = {
    "hands": "the robot has ONE End Effector: move the heads into  end_effector.heads  (\"heads\" -> \"units\")",
    "scanners": "the robot has ONE End Effector: move the reader into  end_effector.scanner",
}


def load_settings(path=None):
    cfg = copy.deepcopy(DEFAULTS)
    if path:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        for key, advice in LEGACY_KEYS.items():
            if key in data:
                raise ValueError("%s: \"%s\" is no longer used - %s (see config/settings.example.json)" % (path, key, advice))
        _merge(cfg, data)
    return cfg


def detect_local_ip(prefix="10."):
    """Địa chỉ IPv4 cục bộ đầu tiên bắt đầu bằng `prefix` ('' nếu không có) - cùng quy tắc với chương trình cũ."""
    try:
        for ip in socket.gethostbyname_ex(socket.gethostname())[2]:
            if ip.startswith(prefix):
                return ip
    except OSError:
        pass
    return ""


def resolve_local_ip(cfg):
    return cfg["identity"]["local_ip"] or detect_local_ip()


def env_secret(name, default=""):
    return os.environ.get(name, default) if name else default
