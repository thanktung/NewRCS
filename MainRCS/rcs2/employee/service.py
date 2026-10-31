"""Tra cứu nhân viên qua web service ESD + quy tắc đăng nhập (mã thẻ -> bộ phận -> cấp).

Luồng đăng nhập
  1. tên đăng nhập = mã thẻ 8 ký tự, mật khẩu = mật khẩu mặc định dùng chung (DEFAULT_PASSWORD,
     có thể đè bằng "default_password" trong file bộ phận)
  2. mã thẻ -> SOAP IsAuthorizedMeasuredESDEmp_NEW -> "ID_Name_Dept_Status"
  3. mã BỘ PHẬN (ví dụ MNM561, MNM571) được tra trong file bộ phận
     (config/departments.json), cho ra cấp truy cập 1..5 (5 = cao nhất).
     Bộ phận không có trong danh sách nhận "default_level" (0 = từ chối đăng nhập).
File được đọc lại mỗi lần đăng nhập, nên sửa file không cần khởi động lại.

Lưu ý: mật khẩu dùng chung cho mọi nhân viên nên KHÔNG phải bí mật; điều kiện thật sự là thẻ
tồn tại và bộ phận của thẻ có trong danh sách với một cấp.
"""
import fnmatch
import hmac
import json
import os
import re
from dataclasses import dataclass, field
from typing import Callable, FrozenSet, Optional
from xml.etree import ElementTree as ET
from xml.sax.saxutils import escape

SOAP_ACTION = "http://tempuri.org/IsAuthorizedMeasuredESDEmp_NEW"
CARD_RE = re.compile(r"^[A-Za-z0-9]{8}$")


class EmployeeError(Exception):
    """Lỗi đăng nhập / tra cứu. `reason` là mã ngắn để chương trình đọc."""

    def __init__(self, reason, message):
        super().__init__(message)
        self.reason = reason
        self.message = message


@dataclass
class Employee:
    card: str
    id: str
    name: str
    dept: str
    status: str


@dataclass
class LoginResult:
    employee: Employee
    job: str                       # "L<level> <department>"; lưu thành staff_bp trong bảng dashboard
    level: int                     # 1..5
    allowed: FrozenSet[str] = field(default_factory=lambda: frozenset(ACTIONS))   # các thao tác cấp này được làm


def build_soap(card_id, start, end):
    return ("""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
               xmlns:xsd="http://www.w3.org/2001/XMLSchema"
               xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <IsAuthorizedMeasuredESDEmp_NEW xmlns="http://tempuri.org/">
      <CardID>%s</CardID>
      <checkESDStartTime>%s</checkESDStartTime>
      <checkESDEndTime>%s</checkESDEndTime>
    </IsAuthorizedMeasuredESDEmp_NEW>
  </soap:Body>
</soap:Envelope>""" % (escape(card_id), escape(start), escape(end)))


def parse_response(xml_text, card):
    """XML phản hồi -> Employee. Văn bản kết quả là 'ID_Name_Dept_Status'."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as ex:
        raise EmployeeError("BAD_RESPONSE", "dịch vụ ESD trả về XML không hợp lệ: %s" % ex)
    node = next((e for e in root.iter() if e.tag.endswith("IsAuthorizedMeasuredESDEmp_NEWResult")), None)
    if node is None:
        raise EmployeeError("BAD_RESPONSE", "phản hồi ESD không có kết quả")
    raw = (node.text or "").strip()
    if raw.startswith("System."):
        raise EmployeeError("BAD_RESPONSE", "lỗi từ dịch vụ ESD: %s" % raw)
    parts = raw.split("_")
    if len(parts) < 4:
        raise EmployeeError("CARD_NOT_FOUND", "kết quả ESD không hợp lệ %r" % raw)
    # id là trường đầu, status và dept là hai trường cuối; bản thân tên có thể chứa '_'
    name = "_".join(parts[1:-2])
    emp = Employee(card=card, id=parts[0], name=name, dept=parts[-2], status=parts[-1])
    if len(emp.name) < 4:          # cùng quy tắc với chương trình cũ: tên ngắn nghĩa là "không tìm thấy thẻ"
        raise EmployeeError("CARD_NOT_FOUND", "mã thẻ %s không tồn tại" % card)
    return emp


def http_post_soap(url, body, timeout):
    """Cách gửi mặc định: POST SOAP envelope, bỏ qua proxy của hệ thống. Trả về văn bản phản hồi."""
    import requests
    session = requests.Session()
    session.trust_env = False            # mạng nội bộ: không bao giờ đi qua proxy
    try:
        resp = session.post(url, data=body.encode("utf-8"), timeout=timeout, headers={
            "Content-Type": "text/xml; charset=utf-8", "SOAPAction": '"%s"' % SOAP_ACTION})
        resp.raise_for_status()
    except requests.RequestException as ex:
        raise EmployeeError("SERVICE_UNREACHABLE", "không kết nối được dịch vụ ESD: %s" % ex)
    return resp.text


DEFAULT_PASSWORD = "wnc000000"
LEVELS = (1, 2, 3, 4, 5)
# Người vận hành được làm gì. Mỗi thao tác cần tối thiểu min_level[action] (file bộ phận); mặc định 1 = ai cũng được.
ACTIONS = ("operate", "manual", "teach")
DEFAULT_MIN_LEVEL = {"operate": 1, "manual": 1, "teach": 1}


class AccessPolicy:
    """Mã bộ phận -> cấp, mật khẩu chung và cấp tối thiểu của từng thao tác."""

    def __init__(self, departments=None, default_level=0, default_password=DEFAULT_PASSWORD, min_level=None):
        self.departments = {str(k).strip().upper(): int(v) for k, v in (departments or {}).items()}
        self.default_level = int(default_level)
        self.default_password = str(default_password)
        self.min_level = dict(DEFAULT_MIN_LEVEL)
        self.min_level.update(min_level or {})
        for name, lv in list(self.departments.items()) + [("default_level", self.default_level)]:
            if lv != 0 and lv not in LEVELS:
                raise EmployeeError("ACCESS_FILE", "cấp của %s phải là 0 hoặc 1..5, nhận được %r" % (name, lv))
        for action, lv in self.min_level.items():
            if action not in ACTIONS or lv not in LEVELS:
                raise EmployeeError("ACCESS_FILE", "min_level %s=%r: quyền phải là một trong %s, cấp 1..5"
                                    % (action, lv, ", ".join(ACTIONS)))

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict) or not isinstance(data.get("departments", {}), dict):
            raise EmployeeError("ACCESS_FILE", "file bộ phận: cần một object có mục 'departments'")
        try:
            def real(d):                                   # khóa bắt đầu bằng "_" là chú thích
                return {k: v for k, v in (d or {}).items() if not str(k).startswith("_")}
            return cls(real(data.get("departments")), data.get("default_level", 0),
                       data.get("default_password", DEFAULT_PASSWORD), real(data.get("min_level")))
        except (TypeError, ValueError) as ex:
            raise EmployeeError("ACCESS_FILE", "file bộ phận: %s" % ex)

    @classmethod
    def load(cls, path):
        try:
            with open(path, "r", encoding="utf-8-sig") as fh:          # utf-8-sig: Notepad có thể thêm BOM
                data = json.load(fh)
        except FileNotFoundError:
            raise EmployeeError("ACCESS_FILE", "không tìm thấy file bộ phận: %s" % path)
        except (OSError, ValueError) as ex:
            raise EmployeeError("ACCESS_FILE", "không đọc được file bộ phận %s: %s" % (path, ex))
        return cls.from_dict(data)

    def level_for(self, dept):
        """Mã bộ phận khớp chính xác trước (không phân biệt hoa thường), rồi tới mẫu như 'MNM5*'; nếu không thì default_level."""
        key = (dept or "").strip().upper()
        if key in self.departments:
            return self.departments[key]
        for pattern, lv in self.departments.items():
            if any(c in pattern for c in "*?[") and fnmatch.fnmatchcase(key, pattern):
                return lv
        return self.default_level

    def check_password(self, password):
        return hmac.compare_digest(password.strip().encode("utf-8"), self.default_password.encode("utf-8"))

    def allowed_actions(self, level):
        return frozenset(a for a in ACTIONS if level >= self.min_level[a])


def check_card(card):
    card = (card or "").strip()
    if not CARD_RE.match(card):
        raise EmployeeError("BAD_CARD", "Sai mã thẻ (8 ký tự chữ/số)")
    return card


class EmployeeService:
    def __init__(self, url, timeout_s=30, start="2026-01-01 00:00:00", end="2050-12-28 23:59:59",
                 offline_demo=False, transport: Optional[Callable] = None, policy_path=None, policy=None):
        self.url, self.timeout_s = url, timeout_s
        self.start, self.end = start, end
        self.offline_demo = offline_demo
        self._transport = transport or http_post_soap
        self.policy_path = policy_path
        self._policy = policy
        if offline_demo and policy is None:               # demo: không cần file, người dùng demo có cấp 5
            self._policy = AccessPolicy({"DEMO": 5})

    @classmethod
    def from_settings(cls, cfg, transport=None, base_dir=None):
        e = cfg["employee"]
        path = e.get("departments_path", "config/departments.json")
        if base_dir and not os.path.isabs(path):
            path = os.path.join(base_dir, path)
        return cls(e["url"], e["timeout_s"], e["check_start"], e["check_end"], e["offline_demo"], transport,
                   policy_path=path)

    def policy(self):
        """Chính sách truy cập (đọc lại từ file mỗi lần gọi, nên sửa file có hiệu lực từ lần đăng nhập sau)."""
        if self._policy is not None:
            return self._policy
        if not self.policy_path:
            raise EmployeeError("ACCESS_FILE", "chưa cấu hình file bộ phận (employee.departments_path)")
        return AccessPolicy.load(self.policy_path)

    def lookup(self, card):
        """Mã thẻ -> Employee (ném EmployeeError)."""
        card = check_card(card)
        if self.offline_demo:
            return Employee(card, card, "Demo User", "DEMO", "OK")
        xml = self._transport(self.url, build_soap(card, self.start, self.end), self.timeout_s)
        return parse_response(xml, card)

    def login(self, username, password):
        """Mã thẻ + mật khẩu chung -> LoginResult. Ném EmployeeError(reason, message)."""
        card = check_card(username)
        policy = self.policy()
        if not policy.check_password(password or ""):
            raise EmployeeError("BAD_PASSWORD", "Sai mật khẩu")
        emp = self.lookup(card)
        level = policy.level_for(emp.dept)
        if level not in LEVELS:
            raise EmployeeError("NOT_AUTHORIZED", "Bộ phận %s chưa được phép dùng RCS" % (emp.dept or "?"))
        return LoginResult(emp, "L%d %s" % (level, emp.dept), level, policy.allowed_actions(level))
