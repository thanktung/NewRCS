"""Employee lookup: SOAP against a local fake ESD server + the login rules (card -> department -> level)."""
import json
import os
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

from tests.support import bridge as helpers
from rcs2 import employee as E

RESPONSE = """<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body><IsAuthorizedMeasuredESDEmp_NEWResponse xmlns="http://tempuri.org/">
    <IsAuthorizedMeasuredESDEmp_NEWResult>%s</IsAuthorizedMeasuredESDEmp_NEWResult>
  </IsAuthorizedMeasuredESDEmp_NEWResponse></soap:Body>
</soap:Envelope>"""


class FakeEsd:
    """Tiny HTTP server that answers every SOAP call with `self.result` (or an HTTP error)."""

    def __init__(self, result="24003437_Nguyen Van A_ABC100_OK", status=200):
        self.result, self.status = result, status
        self.requests = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = self.rfile.read(int(self.headers["Content-Length"])).decode("utf-8")
                outer.requests.append((self.headers.get("SOAPAction"), body))
                data = (RESPONSE % outer.result).encode("utf-8")
                self.send_response(outer.status)
                self.send_header("Content-Type", "text/xml; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *a):
                pass

        self.httpd = HTTPServer(("127.0.0.1", 0), Handler)
        self.url = "http://127.0.0.1:%d/WS_ESD/CheckEmpRightWithEsd.asmx" % self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


class LookupTests(unittest.TestCase):
    def setUp(self):
        self.esd = FakeEsd()
        self.svc = E.EmployeeService(self.esd.url, timeout_s=5)

    def tearDown(self):
        self.esd.close()

    def test_lookup_ok_and_request_shape(self):
        emp = self.svc.lookup("24003437")
        self.assertEqual((emp.id, emp.name, emp.dept, emp.status), ("24003437", "Nguyen Van A", "ABC100", "OK"))
        action, body = self.esd.requests[0]
        self.assertEqual(action, '"http://tempuri.org/IsAuthorizedMeasuredESDEmp_NEW"')
        self.assertIn("<CardID>24003437</CardID>", body)

    def test_name_may_contain_underscore(self):
        self.esd.result = "1001_Tran_Van_B_ABC100_OK"
        emp = self.svc.lookup("12345678")
        self.assertEqual((emp.name, emp.dept), ("Tran_Van_B", "ABC100"))

    def test_short_name_means_card_not_found(self):
        self.esd.result = "1001_Ab_ABC100_OK"
        with self.assertRaises(E.EmployeeError) as cm:
            self.svc.lookup("12345678")
        self.assertEqual(cm.exception.reason, "CARD_NOT_FOUND")

    def test_malformed_and_server_error(self):
        for result, reason in (("garbage", "CARD_NOT_FOUND"), ("System.Exception: boom", "BAD_RESPONSE")):
            self.esd.result = result
            with self.assertRaises(E.EmployeeError) as cm:
                self.svc.lookup("12345678")
            self.assertEqual(cm.exception.reason, reason)

    def test_http_error_and_unreachable(self):
        self.esd.status = 500
        with self.assertRaises(E.EmployeeError) as cm:
            self.svc.lookup("12345678")
        self.assertEqual(cm.exception.reason, "SERVICE_UNREACHABLE")
        dead = E.EmployeeService("http://127.0.0.1:1/x", timeout_s=1)
        with self.assertRaises(E.EmployeeError) as cm:
            dead.lookup("12345678")
        self.assertEqual(cm.exception.reason, "SERVICE_UNREACHABLE")

    def test_bad_card_never_reaches_the_network(self):
        for card in ("123", "123456789", "1234 678", "<x>12345"):
            with self.assertRaises(E.EmployeeError):
                self.svc.lookup(card)
        self.assertEqual(self.esd.requests, [])

    def test_soap_escapes_values(self):
        self.assertNotIn("<evil>", E.build_soap("<evil>", "a", "b"))


class LoginTests(unittest.TestCase):
    """Card number + shared password -> department -> level (departments file)."""

    def setUp(self):
        self.esd = FakeEsd()                       # answers: 24003437 / Nguyen Van A / dept ABC100
        self.policy = E.AccessPolicy({"ABC100": 3, "MNM561": 5, "MNM5*": 2})

    def tearDown(self):
        self.esd.close()

    def svc(self, **kw):
        kw.setdefault("policy", self.policy)
        return E.EmployeeService(self.esd.url, timeout_s=5, **kw)

    def test_default_password_and_level_from_department(self):
        r = self.svc().login("24003437", "wnc000000")
        self.assertEqual((r.employee.dept, r.level, r.job), ("ABC100", 3, "L3 ABC100"))
        self.assertIn("<CardID>24003437</CardID>", self.esd.requests[0][1])

    def test_level_follows_the_department_code(self):
        self.esd.result = "24003437_Nguyen Van A_MNM561_OK"
        self.assertEqual(self.svc().login("24003437", "wnc000000").level, 5)
        self.esd.result = "24003437_Nguyen Van A_MNM571_OK"          # not listed exactly: matches the MNM5* pattern
        self.assertEqual(self.svc().login("24003437", "wnc000000").level, 2)
        self.esd.result = "24003437_Nguyen Van A_mnm561_OK"          # case-insensitive
        self.assertEqual(self.svc().login("24003437", "wnc000000").level, 5)

    def test_unknown_department_is_refused(self):
        self.esd.result = "24003437_Nguyen Van A_XYZ999_OK"
        with self.assertRaises(E.EmployeeError) as cm:
            self.svc().login("24003437", "wnc000000")
        self.assertEqual(cm.exception.reason, "NOT_AUTHORIZED")
        self.assertIn("XYZ999", cm.exception.message)

    def test_default_level_can_admit_unlisted_departments(self):
        self.esd.result = "24003437_Nguyen Van A_XYZ999_OK"
        policy = E.AccessPolicy({"ABC100": 3}, default_level=1)
        self.assertEqual(self.svc(policy=policy).login("24003437", "wnc000000").level, 1)

    def test_wrong_password_never_reaches_the_network(self):
        for pw in ("", "wnc00000", "WNC000000", "24003437", "wnc0000000"):
            with self.assertRaises(E.EmployeeError) as cm:
                self.svc().login("24003437", pw)
            self.assertEqual(cm.exception.reason, "BAD_PASSWORD")
        self.assertEqual(self.esd.requests, [])

    def test_old_style_usernames_are_gone(self):
        for user in ("op", "pe"):
            with self.assertRaises(E.EmployeeError) as cm:
                self.svc().login(user, "24003437")
            self.assertEqual(cm.exception.reason, "BAD_CARD")
        self.assertEqual(self.esd.requests, [])

    def test_wrong_card_length(self):
        with self.assertRaises(E.EmployeeError) as cm:
            self.svc().login("123", "wnc000000")
        self.assertEqual(cm.exception.reason, "BAD_CARD")

    def test_card_that_does_not_exist(self):
        self.esd.result = "1001_Ab_ABC100_OK"
        with self.assertRaises(E.EmployeeError) as cm:
            self.svc().login("24003437", "wnc000000")
        self.assertEqual(cm.exception.reason, "CARD_NOT_FOUND")

    def test_actions_follow_min_level(self):
        policy = E.AccessPolicy({"ABC100": 3}, min_level={"manual": 3, "teach": 4})
        r = self.svc(policy=policy).login("24003437", "wnc000000")
        self.assertEqual(r.allowed, frozenset({"operate", "manual"}))
        self.assertEqual(E.AccessPolicy({}).allowed_actions(1), frozenset(E.ACTIONS))     # defaults: everybody

    def test_offline_demo(self):
        svc = E.EmployeeService("http://127.0.0.1:1/x", offline_demo=True)
        r = svc.login("12345678", "wnc000000")
        self.assertEqual((r.employee.name, r.level), ("Demo User", 5))


class AccessFileTests(unittest.TestCase):
    """The departments file: loading, validation, hot reload."""

    def write(self, data):
        with open(self.path, "w", encoding="utf-8") as fh:
            json.dump(data, fh)

    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, "departments.json")
        self.esd = FakeEsd(result="24003437_Nguyen Van A_MNM561_OK")
        self.svc = E.EmployeeService(self.esd.url, timeout_s=5, policy_path=self.path)

    def tearDown(self):
        self.esd.close()

    def test_levels_come_from_the_file_and_are_reloaded_at_every_login(self):
        self.write({"departments": {"MNM561": 4}})
        self.assertEqual(self.svc.login("24003437", "wnc000000").level, 4)
        self.write({"departments": {"MNM561": 2}})                  # edited while RCS is running
        self.assertEqual(self.svc.login("24003437", "wnc000000").level, 2)

    def test_comment_keys_and_bom_are_accepted(self):
        with open(self.path, "w", encoding="utf-8-sig") as fh:
            json.dump({"_note": "x", "departments": {"_note": "y", "MNM561": 5}, "min_level": {"_note": "z", "manual": 2}}, fh)
        r = self.svc.login("24003437", "wnc000000")
        self.assertEqual(r.level, 5)

    def test_password_can_be_overridden_in_the_file(self):
        self.write({"departments": {"MNM561": 5}, "default_password": "other-secret"})
        with self.assertRaises(E.EmployeeError):
            self.svc.login("24003437", "wnc000000")
        self.assertEqual(self.svc.login("24003437", "other-secret").level, 5)

    def test_missing_or_broken_file_refuses_the_login(self):
        with self.assertRaises(E.EmployeeError) as cm:
            self.svc.login("24003437", "wnc000000")
        self.assertEqual(cm.exception.reason, "ACCESS_FILE")
        with open(self.path, "w") as fh:
            fh.write("{ not json")
        with self.assertRaises(E.EmployeeError) as cm:
            self.svc.login("24003437", "wnc000000")
        self.assertEqual(cm.exception.reason, "ACCESS_FILE")
        self.assertEqual(self.esd.requests, [])

    def test_bad_values_are_rejected(self):
        for data in ({"departments": {"MNM561": 6}}, {"departments": {"MNM561": "x"}}, {"default_level": 9},
                     {"min_level": {"manual": 0}}, {"min_level": {"fly": 1}}, {"departments": []}):
            self.write(data)
            with self.assertRaises(E.EmployeeError) as cm:
                self.svc.login("24003437", "wnc000000")
            self.assertEqual(cm.exception.reason, "ACCESS_FILE", data)

    def test_shipped_files_are_valid(self):
        root = helpers.ROOT
        for name in ("departments.json", "departments.example.json"):
            policy = E.AccessPolicy.load(os.path.join(root, "config", name))
            self.assertEqual(policy.default_level, 0)                   # unlisted departments are refused
            self.assertIn(policy.level_for("MNM561"), E.LEVELS)


if __name__ == "__main__":
    unittest.main()
