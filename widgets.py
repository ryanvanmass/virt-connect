from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

MONO = "'JetBrains Mono', 'DejaVu Sans Mono', monospace"


class Led(QLabel):
    """Small filled circle indicating a VM's power state."""

    def __init__(self, running: bool):
        super().__init__()
        self.setFixedSize(10, 10)
        color = "#5fd97a" if running else "#444d5c"
        glow = "0 0 6px #5fd97a" if running else "none"
        self.setStyleSheet(
            f"background:{color}; border-radius:5px;"
        )


class VmRow(QWidget):
    connect_requested = pyqtSignal(str, str, bool)  # uri, vm name, use_x11_backend

    def __init__(self, uri: str, vm: dict):
        super().__init__()
        self._uri = uri
        self._vm_name = vm["name"]

        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 8, 14, 8)
        layout.setSpacing(12)

        running = vm["state"].lower() == "running"
        layout.addWidget(Led(running))

        name_label = QLabel(vm["name"])
        name_label.setStyleSheet(f"font-family:{MONO}; font-size:13px; color:#d9dee5;")
        layout.addWidget(name_label, stretch=1)

        state_label = QLabel(vm["state"].lower())
        state_label.setStyleSheet(f"font-family:{MONO}; font-size:11.5px; color:#7d8a9a;")
        state_label.setFixedWidth(90)
        layout.addWidget(state_label)

        self.connect_btn = QToolButton()
        self.connect_btn.setObjectName("rowBtn")
        self.connect_btn.setText("Connect")
        self.connect_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.connect_btn.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        self.connect_btn.clicked.connect(
            lambda: self.connect_requested.emit(self._uri, self._vm_name, False)
        )

        menu = QMenu(self.connect_btn)
        legacy_action = menu.addAction("Connect (X11 legacy mode)")
        legacy_action.setToolTip("Runs with GDK_BACKEND=x11 for older/legacy systems")
        legacy_action.triggered.connect(
            lambda: self.connect_requested.emit(self._uri, self._vm_name, True)
        )
        self.connect_btn.setMenu(menu)

        layout.addWidget(self.connect_btn)

    def set_busy(self, busy: bool):
        self.connect_btn.setEnabled(not busy)
        self.connect_btn.setText("Launching…" if busy else "Connect")


class HostCard(QFrame):
    connect_requested = pyqtSignal(str, str, bool)  # uri, vm name, use_x11_backend
    refresh_requested = pyqtSignal(str)  # host name
    delete_requested = pyqtSignal(str)  # host name

    def __init__(self, name: str, uri: str):
        super().__init__()
        self.setObjectName("hostCard")
        self._name = name
        self._uri_for_rows = uri
        self._rows = {}  # vm name -> VmRow

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        head = QWidget()
        head.setObjectName("hostHead")
        head_layout = QHBoxLayout(head)
        head_layout.setContentsMargins(16, 10, 10, 10)

        title = QLabel(f"{name}")
        title.setStyleSheet(f"font-family:{MONO}; font-weight:600; font-size:14px; color:#d9dee5;")
        head_layout.addWidget(title)

        uri_label = QLabel(uri)
        uri_label.setStyleSheet(f"font-family:{MONO}; font-size:11.5px; color:#7d8a9a;")
        head_layout.addWidget(uri_label)
        head_layout.addStretch(1)

        refresh_btn = QPushButton("\u21bb")
        refresh_btn.setObjectName("iconBtn")
        refresh_btn.setToolTip("Refresh")
        refresh_btn.clicked.connect(lambda: self.refresh_requested.emit(self._name))
        head_layout.addWidget(refresh_btn)

        delete_btn = QPushButton("\u2715")
        delete_btn.setObjectName("dangerBtn")
        delete_btn.setToolTip("Remove host")
        delete_btn.clicked.connect(lambda: self.delete_requested.emit(self._name))
        head_layout.addWidget(delete_btn)

        outer.addWidget(head)

        self.body = QVBoxLayout()
        self.body.setContentsMargins(0, 0, 0, 0)
        self.body.setSpacing(0)
        body_widget = QWidget()
        body_widget.setLayout(self.body)
        outer.addWidget(body_widget)

    def set_content(self, vms, error):
        while self.body.count():
            item = self.body.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._rows.clear()

        if error:
            lbl = QLabel(error)
            lbl.setStyleSheet(f"font-family:{MONO}; font-size:12.5px; color:#e0616b; padding:14px 18px;")
            self.body.addWidget(lbl)
            return

        if not vms:
            lbl = QLabel("No VMs found on this host.")
            lbl.setStyleSheet(f"font-family:{MONO}; font-size:12.5px; color:#7d8a9a; padding:14px 18px;")
            self.body.addWidget(lbl)
            return

        for vm in vms:
            row = VmRow(self._uri_for_rows, vm)
            row.connect_requested.connect(self.connect_requested)
            self.body.addWidget(row)
            self._rows[vm["name"]] = row

    def set_uri_context(self, uri):
        self._uri_for_rows = uri

    def set_row_busy(self, vm_name, busy):
        row = self._rows.get(vm_name)
        if row:
            row.set_busy(busy)


class AddHostDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add host")
        self.setMinimumWidth(380)

        layout = QVBoxLayout(self)

        form = QFormLayout()
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g. Rack-2 or Local")
        self.uri_edit = QLineEdit()
        self.uri_edit.setPlaceholderText("qemu:///system  or  qemu+ssh://user@host/system")
        form.addRow("Name", self.name_edit)
        form.addRow("Connection URI", self.uri_edit)
        layout.addLayout(form)

        hint = QLabel(
            "Local hypervisor: qemu:///system\nRemote over SSH: qemu+ssh://user@host/system"
        )
        hint.setStyleSheet(f"font-family:{MONO}; font-size:11px; color:#7d8a9a;")
        layout.addWidget(hint)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def values(self):
        return self.name_edit.text().strip(), self.uri_edit.text().strip()
