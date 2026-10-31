"""Tên bảng / DDL / câu INSERT của MySQL, giống hệt RCS cũ (Produce.cs "DataBase").

Giữ nguyên bố cục cũ nên dashboard hiện có vẫn chạy mà không phải sửa.

kind          tên bảng
error         {Model}_{stations nối bằng _}_{ip với _}_Y{year}_M{month}
login         LoginLog_{Model}_{stations}_{ip}_Y{year}_M{month}
result        TestResult_{Model}_{stations}_{ip}_Y{year}_M{month}
ats_hourly    ATSHourlyIDE_{Model}_{stations}_{ip}_Y{year}_M{month}
robot_speed   RobotSpeed_{Model}_{stations}_{ip}            (không có hậu tố tháng)

Tháng luôn lấy từ thời điểm của chính sự kiện (không phải "bây giờ"), nên các dòng nằm trong
outbox một thời gian vẫn vào đúng bảng của tháng đó.
"""
from datetime import datetime

KINDS = ("error", "login", "result", "ats_hourly", "robot_speed")


def _ts(value):
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value)


class SqlTargets:
    def __init__(self, model, stations, local_ip):
        self.model = model
        self.stations = list(stations)
        self.ip = local_ip

    # ---- tên ------------------------------------------------------------ #
    @property
    def _base(self):
        return "%s_%s_%s" % (self.model, "_".join(self.stations), self.ip.replace(".", "_"))

    @property
    def station_label(self):
        """Giá trị cột 'Station' của bảng lỗi."""
        return "%s_%s" % (self.model, "_".join(self.stations))

    def table(self, kind, when):
        when = _ts(when)
        ym = "Y%d_M%02d" % (when.year, when.month)
        name = {
            "error": "%s_%s" % (self._base, ym),
            "login": "LoginLog_%s_%s" % (self._base, ym),
            "result": "TestResult_%s_%s" % (self._base, ym),
            "ats_hourly": "ATSHourlyIDE_%s_%s" % (self._base, ym),
            "robot_speed": "RobotSpeed_%s" % self._base,
        }.get(kind)
        if name is None:
            raise ValueError("unknown kind %r" % kind)
        if "`" in name or "\x00" in name:
            raise ValueError("illegal character in table name %r" % name)
        return name

    @staticmethod
    def when_of(kind, payload):
        key = {"error": "start", "login": "start", "result": "update_time",
               "ats_hourly": "update_time", "robot_speed": "update_time"}[kind]
        return _ts(payload[key])

    # ---- câu lệnh ------------------------------------------------------- #
    @staticmethod
    def ddl(kind, table):
        cols = {
            "error": "Station VARCHAR(100), ErrorCode VARCHAR(50), Error VARCHAR(255), "
                     "Start_Time DATETIME, End_Time DATETIME",
            "login": "StaffName VARCHAR(255), StaffID VARCHAR(255), StaffBP VARCHAR(255), Start_Time DATETIME",
            "result": "UpdateTime DATETIME, FixtureNo VARCHAR(100), ATS_IP VARCHAR(50), "
                      "Result VARCHAR(50), TestTime DOUBLE, ProductType VARCHAR(50)",
            "ats_hourly": "Fixture VARCHAR(255), IDE INT NOT NULL, Update_Time DATETIME NOT NULL",
            "robot_speed": "RobotName VARCHAR(100), Speed DOUBLE, Update_Time DATETIME",
        }[kind]
        return "CREATE TABLE IF NOT EXISTS `%s` (id INT AUTO_INCREMENT PRIMARY KEY, %s)" % (table, cols)

    def insert(self, kind, table, payload):
        """-> (sql có chỗ giữ %s, tuple tham số)."""
        p = payload
        if kind == "error":
            return ("INSERT INTO `%s` (Station, ErrorCode, Error, Start_Time, End_Time) "
                    "VALUES (%%s, %%s, %%s, %%s, %%s)" % table,
                    (p.get("station") or self.station_label, p["error_code"], p["error"],
                     _ts(p["start"]), _ts(p["end"])))
        if kind == "login":
            return ("INSERT INTO `%s` (StaffName, StaffID, StaffBP, Start_Time) VALUES (%%s, %%s, %%s, %%s)" % table,
                    (p["staff_name"], p["staff_id"], p["staff_bp"], _ts(p["start"])))
        if kind == "result":
            return ("INSERT INTO `%s` (UpdateTime, FixtureNo, ATS_IP, Result, TestTime, ProductType) "
                    "VALUES (%%s, %%s, %%s, %%s, %%s, %%s)" % table,
                    (_ts(p["update_time"]), p["fixture_no"], p["ats_ip"], p["result"],
                     float(p["test_time"]), p["product_type"]))
        if kind == "ats_hourly":
            return ("INSERT INTO `%s` (Fixture, IDE, Update_Time) VALUES (%%s, %%s, %%s)" % table,
                    (p["fixture"], int(p["ide"]), _ts(p["update_time"])))
        if kind == "robot_speed":
            return ("INSERT INTO `%s` (RobotName, Speed, Update_Time) VALUES (%%s, %%s, %%s)" % table,
                    (p["robot_name"], float(p["speed"]), _ts(p["update_time"])))
        raise ValueError("unknown kind %r" % kind)
