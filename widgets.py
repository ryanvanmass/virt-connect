from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

import viewer

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
    connect_requested = pyqtSignal(str, str, bool)  # host name, vm id, use_x11_backend
    power_requested = pyqtSignal(str, str, str)  # host name, vm id, action

    def __init__(self, host_name: str, vm: dict):
        super().__init__()
        self._host = host_name
        self._vm_id = vm.get("id", vm["name"])

        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 8, 14, 8)
        layout.setSpacing(12)

        state_lower = vm["state"].lower()
        running = state_lower == "running"
        layout.addWidget(Led(running))

        name_label = QLabel(vm["name"])
        name_label.setStyleSheet(f"font-family:{MONO}; font-size:13px; color:#d9dee5;")
        layout.addWidget(name_label, stretch=1)

        state_label = QLabel(vm["state"].lower())
        state_label.setStyleSheet(f"font-family:{MONO}; font-size:11.5px; color:#7d8a9a;")
        state_label.setFixedWidth(90)
        layout.addWidget(state_label)

        # Power control: default action depends on current state. Running
        # VMs default to Pause; paused or shut-off VMs default to Start
        # (resuming vs. booting under the hood, respectively). Shutdown is
        # always available as a secondary option via the dropdown.
        if state_lower == "running":
            self._power_label, self._power_action = "Pause", "pause"
        elif state_lower == "paused":
            self._power_label, self._power_action = "Start", "resume"
        else:
            self._power_label, self._power_action = "Start", "start"

        self.power_btn = QToolButton()
        self.power_btn.setObjectName("rowBtn")
        self.power_btn.setText(self._power_label)
        self.power_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.power_btn.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        self.power_btn.clicked.connect(
            lambda: self.power_requested.emit(self._host, self._vm_id, self._power_action)
        )

        power_menu = QMenu(self.power_btn)
        shutdown_action = power_menu.addAction("Shutdown")
        shutdown_action.setToolTip("Graceful ACPI shutdown")
        shutdown_action.triggered.connect(
            lambda: self.power_requested.emit(self._host, self._vm_id, "shutdown")
        )
        self.power_btn.setMenu(power_menu)
        layout.addWidget(self.power_btn)

        self.connect_btn = QToolButton()
        self.connect_btn.setObjectName("rowBtn")
        self.connect_btn.setText("Connect")
        self.connect_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        self.connect_btn.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        self.connect_btn.clicked.connect(
            lambda: self.connect_requested.emit(self._host, self._vm_id, False)
        )

        # X11 legacy mode only means something for the GTK virt-viewer
        # tools; on macOS the Connect button opens Saffron, so it's a plain
        # button there.
        if not viewer.uses_saffron():
            menu = QMenu(self.connect_btn)
            legacy_action = menu.addAction("Connect (X11 legacy mode)")
            legacy_action.setToolTip("Runs with GDK_BACKEND=x11 for older/legacy systems")
            legacy_action.triggered.connect(
                lambda: self.connect_requested.emit(self._host, self._vm_id, True)
            )
            self.connect_btn.setMenu(menu)
        else:
            self.connect_btn.setPopupMode(QToolButton.ToolButtonPopupMode.DelayedPopup)

        layout.addWidget(self.connect_btn)

    def set_busy(self, busy: bool):
        self.connect_btn.setEnabled(not busy)
        self.connect_btn.setText("Launching…" if busy else "Connect")
        self.power_btn.setEnabled(not busy)
        self.power_btn.setText("Working…" if busy else self._power_label)


class HostCard(QFrame):
    connect_requested = pyqtSignal(str, str, bool)  # host name, vm id, use_x11_backend
    power_requested = pyqtSignal(str, str, str)  # host name, vm id, action
    refresh_requested = pyqtSignal(str)  # host name
    delete_requested = pyqtSignal(str)  # host name

    def __init__(self, name: str, subtitle: str, badge: str = ""):
        super().__init__()
        self.setObjectName("hostCard")
        self._name = name
        self._rows = {}  # vm id -> VmRow

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

        if badge:
            badge_label = QLabel(badge)
            badge_label.setStyleSheet(
                f"font-family:{MONO}; font-size:10.5px; color:#e8a33d;"
                "border:1px solid #8a672a; border-radius:4px; padding:1px 5px;"
            )
            head_layout.addWidget(badge_label)

        uri_label = QLabel(subtitle)
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
            row = VmRow(self._name, vm)
            row.connect_requested.connect(self.connect_requested)
            row.power_requested.connect(self.power_requested)
            self.body.addWidget(row)
            self._rows[vm.get("id", vm["name"])] = row

    def set_row_busy(self, vm_id, busy):
        row = self._rows.get(vm_id)
        if row:
            row.set_busy(busy)


class AddHostDialog(QDialog):
    """Collects a new host entry: either a libvirt URI or a Proxmox VE API endpoint."""

    TYPES = [("libvirt", "libvirt (virsh)"), ("proxmox", "Proxmox VE (API)")]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add host")
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)

        top = QFormLayout()
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g. Rack-2 or Local")
        self.type_combo = QComboBox()
        for key, label in self.TYPES:
            self.type_combo.addItem(label, key)
        top.addRow("Name", self.name_edit)
        top.addRow("Type", self.type_combo)
        layout.addLayout(top)

        self.stack = QStackedWidget()

        # -- libvirt page
        libvirt_page = QWidget()
        lv = QVBoxLayout(libvirt_page)
        lv.setContentsMargins(0, 0, 0, 0)
        lv_form = QFormLayout()
        self.uri_edit = QLineEdit()
        self.uri_edit.setPlaceholderText("qemu:///system  or  qemu+ssh://user@host/system")
        lv_form.addRow("Connection URI", self.uri_edit)
        lv.addLayout(lv_form)
        lv_hint = QLabel(
            "Local hypervisor: qemu:///system\nRemote over SSH: qemu+ssh://user@host/system"
        )
        lv_hint.setStyleSheet(f"font-family:{MONO}; font-size:11px; color:#7d8a9a;")
        lv.addWidget(lv_hint)
        lv.addStretch(1)
        self.stack.addWidget(libvirt_page)

        # -- Proxmox page
        pve_page = QWidget()
        pv = QVBoxLayout(pve_page)
        pv.setContentsMargins(0, 0, 0, 0)
        pv_form = QFormLayout()
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("https://pve.lan:8006")
        self.token_id_edit = QLineEdit()
        self.token_id_edit.setPlaceholderText("user@pam!tokenname")
        self.token_secret_edit = QLineEdit()
        self.token_secret_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.token_secret_edit.setPlaceholderText("xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx")
        self.skip_tls_check = QCheckBox("Skip TLS verification (self-signed certificate)")
        pv_form.addRow("API URL", self.url_edit)
        pv_form.addRow("Token ID", self.token_id_edit)
        pv_form.addRow("Token secret", self.token_secret_edit)
        pv.addLayout(pv_form)
        pv.addWidget(self.skip_tls_check)
        pv_hint = QLabel(
            "Create a token under Datacenter → Permissions → API Tokens.\n"
            "It needs VM.Audit, VM.PowerMgmt and VM.Console on the VMs.\n"
            "Consoles use SPICE: set the VM's Display to SPICE (qxl)."
        )
        pv_hint.setStyleSheet(f"font-family:{MONO}; font-size:11px; color:#7d8a9a;")
        pv.addWidget(pv_hint)
        self.stack.addWidget(pve_page)

        layout.addWidget(self.stack)
        self.type_combo.currentIndexChanged.connect(self.stack.setCurrentIndex)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def host_entry(self):
        """Return (host_dict, error). error is a message if a required field is empty."""
        name = self.name_edit.text().strip()
        kind = self.type_combo.currentData()
        if not name:
            return None, "A name is required."
        if kind == "proxmox":
            url = self.url_edit.text().strip()
            token_id = self.token_id_edit.text().strip()
            secret = self.token_secret_edit.text().strip()
            if not url or not token_id or not secret:
                return None, "API URL, token ID and token secret are all required."
            if "!" not in token_id:
                return None, "Token ID should look like user@realm!tokenname."
            return {
                "name": name,
                "type": "proxmox",
                "url": url,
                "token_id": token_id,
                "token_secret": secret,
                "verify_tls": not self.skip_tls_check.isChecked(),
            }, None
        uri = self.uri_edit.text().strip()
        if not uri:
            return None, "A connection URI is required."
        return {"name": name, "type": "libvirt", "uri": uri}, None
