"""Login dialog: card-based login through the ESD web service (runs off the GUI thread)."""
from PySide6 import QtCore, QtWidgets
from PySide6.QtCore import Qt

from ...employee import EmployeeError
from ..kit import fluent as F


class _Worker(QtCore.QThread):
    done = QtCore.Signal(object, str)      # (LoginResult | None, error text)

    def __init__(self, runtime, user, password):
        super().__init__()
        self.runtime, self.user, self.password = runtime, user, password

    def run(self):
        try:
            self.done.emit(self.runtime.login(self.user, self.password), "")
        except EmployeeError as ex:
            self.done.emit(None, ex.message)
        except Exception as ex:                      # network or unexpected problem
            self.done.emit(None, "%s: %s" % (type(ex).__name__, ex))


class LoginDialog(QtWidgets.QDialog):
    def __init__(self, runtime, parent=None):
        super().__init__(parent)
        self.runtime = runtime
        self.result_login = None
        self.setWindowTitle("Đăng nhập")
        self.setModal(True)
        self.setMinimumWidth(420)
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(28, 24, 28, 22)
        lay.setSpacing(6)
        head = QtWidgets.QHBoxLayout()
        head.setSpacing(10)
        head.addWidget(F.GlyphLabel("person", F.ACCENT, 22))
        title = QtWidgets.QLabel("Đăng nhập")
        title.setObjectName("title")
        head.addWidget(title)
        head.addStretch()
        lay.addLayout(head)
        hint = QtWidgets.QLabel("Đăng nhập bằng mã thẻ. Bộ phận của bạn quyết định bạn được làm gì.")
        hint.setObjectName("caption")
        lay.addWidget(hint)
        lay.addSpacing(10)

        self.user = QtWidgets.QLineEdit()
        self.user.setPlaceholderText("Mã thẻ (8 ký tự)")
        self.password = QtWidgets.QLineEdit()
        self.password.setPlaceholderText("Mật khẩu")
        self.password.setEchoMode(QtWidgets.QLineEdit.Password)
        for text, edit in (("Mã thẻ", self.user), ("Mật khẩu", self.password)):
            lab = QtWidgets.QLabel(text)
            lab.setObjectName("muted")
            lay.addWidget(lab)
            lay.addWidget(edit)
            lay.addSpacing(6)

        self.status = QtWidgets.QLabel("")
        self.status.setObjectName("formStatus")
        self.status.setWordWrap(True)
        self.status.setMinimumHeight(20)
        lay.addWidget(self.status)
        lay.addSpacing(8)

        self.btn = QtWidgets.QPushButton("Đăng nhập")
        self.btn.setProperty("kind", "accent")
        self.btn.setDefault(True)
        cancel = QtWidgets.QPushButton("Hủy")
        row = QtWidgets.QHBoxLayout()
        row.addStretch()
        row.addWidget(cancel)
        row.addWidget(self.btn)
        lay.addLayout(row)
        self.btn.clicked.connect(self._submit)
        cancel.clicked.connect(self.reject)
        self.password.returnPressed.connect(self._submit)
        self.user.returnPressed.connect(self.password.setFocus)
        self._worker = None

    def _set_status(self, text, tone=""):
        self.status.setProperty("tone", tone)
        F.repolish(self.status)
        self.status.setText(text)

    def _submit(self):
        if self._worker is not None:
            return
        self.btn.setEnabled(False)
        self._set_status("Đang kiểm tra thẻ ...")
        self._worker = _Worker(self.runtime, self.user.text(), self.password.text())
        self._worker.done.connect(self._finished)
        self._worker.start()

    def _finished(self, result, error):
        self._worker.wait()
        self._worker = None
        self.btn.setEnabled(True)
        if result is None:
            self._set_status(error, "error")
            self.password.selectAll()
            self.password.setFocus()
            return
        self.result_login = result
        self.accept()

