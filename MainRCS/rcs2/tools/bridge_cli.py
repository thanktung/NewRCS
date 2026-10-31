"""Công cụ dòng lệnh để thử bridge robot bằng tay.

    python -m rcs2.tools.bridge_cli --host 192.168.2.10 status
    python -m rcs2.tools.bridge_cli --host 192.168.2.10 r-read 1
    python -m rcs2.tools.bridge_cli --host 192.168.2.10 move 300 0 200 180 0 0 --override 5
    python -m rcs2.tools.bridge_cli --host 192.168.2.10 put 1 --override 5

Lệnh chuyển động arm bridge trong lúc chạy lệnh rồi disarm sau đó.
LUÔN thử với override thấp và một tay đặt sẵn trên E-stop.
"""
import argparse
import json
import sys

from rcs2.robot.client import BridgeClient, RobotError
from rcs2.robot.protocol import DEFAULT_PORT


def build_parser():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    ap.add_argument("--token", default="")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("hello")
    sub.add_parser("status")
    sub.add_parser("connect-robot")
    sub.add_parser("fault-clear")
    sub.add_parser("alarm-clear")

    p = sub.add_parser("r-read"); p.add_argument("index", type=int)
    p = sub.add_parser("r-write"); p.add_argument("index", type=int); p.add_argument("value", type=float)
    p = sub.add_parser("pr-read"); p.add_argument("group", type=int); p.add_argument("index", type=int)
    p = sub.add_parser("io-read"); p.add_argument("kind"); p.add_argument("index", type=int)
    p.add_argument("count", type=int, nargs="?", default=1)

    for name in ("move", "rmove", "gosafetarge"):
        p = sub.add_parser(name)
        p.add_argument("pose", type=float, nargs=6, metavar=("X", "Y", "Z", "W", "P", "R"))
        p.add_argument("--override", type=int)
    for name in ("put", "get", "down", "up"):
        p = sub.add_parser(name)
        p.add_argument("station", type=int)
        p.add_argument("--override", type=int)
    p = sub.add_parser("gosafehere"); p.add_argument("--override", type=int)
    return ap


def main(argv=None):
    args = build_parser().parse_args(argv)
    client = BridgeClient(args.host, args.port, token=args.token, ping_interval=1.0)
    try:
        client.connect()
        out = None
        if args.cmd == "hello":
            out = client.hello
        elif args.cmd == "status":
            out = client.status()
        elif args.cmd == "connect-robot":
            out = client.robot_connect()
        elif args.cmd == "fault-clear":
            out = client.fault_clear()
        elif args.cmd == "alarm-clear":
            out = client.alarm_clear()
        elif args.cmd == "r-read":
            out = client.r_read(args.index)
        elif args.cmd == "r-write":
            value = int(args.value) if args.value == int(args.value) else args.value
            out = client.r_write(args.index, value)
        elif args.cmd == "pr-read":
            out = client.pr_read(args.group, args.index)
        elif args.cmd == "io-read":
            out = client.io_read(args.kind, args.index, args.count)
        else:  # chuyển động
            client.arm()
            try:
                if args.cmd in ("move", "rmove", "gosafetarge"):
                    out = getattr(client, args.cmd)(args.pose, override=args.override)
                elif args.cmd == "gosafehere":
                    out = client.gosafehere(override=args.override)
                else:
                    out = getattr(client, args.cmd)(args.station, override=args.override)
            finally:
                client.disarm()
        print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
        return 0
    except RobotError as ex:
        print("ERROR %s: %s" % (ex.code, ex.message), file=sys.stderr)
        return 2
    except (ConnectionError, OSError) as ex:
        print("CONNECTION ERROR: %s" % ex, file=sys.stderr)
        return 3
    finally:
        client.close()


if __name__ == "__main__":
    sys.exit(main())
