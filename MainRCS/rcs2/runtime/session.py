"""Operator session: login, logout and the automatic logout (employee.auto_logout_s / auto_logout_idle)."""


class SessionMixin:
    # operator actions used by the UI (blocking: call from a worker thread)
    def login(self, username, password):
        result = self.employee.login(username, password)
        self.operator = result
        self._login_at = self._last_activity = self.clock()
        self.sink.emit_login(result.employee.name, result.employee.id, result.job)
        self._emit_log("info", "đăng nhập: %s (%s) cấp %d" % (result.employee.name, result.employee.dept, result.level))
        return result

    def logout(self):
        self.operator = None
        self._login_at = 0.0

    # ---- automatic logout ------------------------------------------------- #
    def touch(self):
        """The operator used the program (mouse / key). Only matters with employee.auto_logout_idle."""
        self._last_activity = self.clock()

    def session_remaining(self):
        """Seconds until the automatic logout, None when nobody is logged in or the feature is off."""
        if self.operator is None or self.auto_logout_s <= 0:
            return None
        if self._login_at == 0.0:                          # operator set without login(): count from now
            self._login_at = self._last_activity = self.clock()
        since = self._last_activity if self.auto_logout_idle else self._login_at
        return self.auto_logout_s - (self.clock() - since)

    def check_auto_logout(self):
        """Logs the operator out when the time is up. True if it just did."""
        left = self.session_remaining()
        if left is None or left > 0:
            return False
        who = self.operator.employee.name
        self.logout()
        self._emit_log("info", "tự động đăng xuất: %s (hết %d giây)" % (who, self.auto_logout_s))
        return True
