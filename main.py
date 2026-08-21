#!/usr/bin/env python3
"""virt-connect (Qt): a native desktop launcher for virt-viewer sessions
against one or more libvirt hosts, with VM lists auto-discovered via virsh.
"""
import sys
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QApplication,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

import config
from widgets import AddHostDialog, HostCard
from workers import ConnectWorker, PowerWorker, RefreshWorker

REFRESH_INTERVAL_MS = 15_000
ICON_PATH = Path(__file__).parent / "assets" / "icon-256.png"

STYLESHEET = """
QMainWindow, QWidget#central { background: #10141a; }
QScrollArea { border: none; background: transparent; }
QWidget#scrollContent { background: transparent; }

QLabel#brand {
    font-family: 'JetBrains Mono', 'DejaVu Sans Mono', monospace;
    font-size: 17px;
    font-weight: 600;
    color: #d9dee5;
}
QLabel#brandSub {
    font-family: 'JetBrains Mono', 'DejaVu Sans Mono', monospace;
    font-size: 11.5px;
    color: #7d8a9a;
}

QFrame#hostCard {
    background: #171d26;
    border: 1px solid #2a3341;
    border-radius: 10px;
}
QWidget#hostHead {
    background: transparent;
    border-bottom: 1px solid #2a3341;
}

QPushButton {
    background: #1d2430;
    border: 1px solid #2a3341;
    border-radius: 6px;
    color: #d9dee5;
    padding: 7px 14px;
    font-size: 12.5px;
}
QPushButton:hover { background: #212a37; border-color: #8a672a; }
QPushButton:disabled { color: #55606e; }

QPushButton#primaryBtn {
    background: #e8a33d;
    border: 1px solid #e8a33d;
    color: #241a08;
    font-weight: 600;
}
QPushButton#primaryBtn:hover { background: #f0ae4b; }

QPushButton#rowBtn { padding: 5px 12px; }

QToolButton#rowBtn {
    background: #1d2430;
    border: 1px solid #2a3341;
    border-radius: 6px;
    color: #d9dee5;
    padding: 5px 10px;
    padding-right: 28px;
    min-width: 74px;
    min-height: 22px;
    font-size: 12.5px;
}
QToolButton#rowBtn:hover { background: #212a37; border-color: #8a672a; }
QToolButton#rowBtn:disabled { color: #55606e; }
QToolButton#rowBtn::menu-button {
    subcontrol-origin: border;
    subcontrol-position: right;
    border-left: 1px solid #2a3341;
    width: 24px;
}
QToolButton#rowBtn::menu-arrow {
    width: 10px;
    height: 10px;
}

QMenu {
    background: #171d26;
    border: 1px solid #2a3341;
    border-radius: 8px;
    padding: 4px;
    color: #d9dee5;
    font-size: 12.5px;
}
QMenu::item {
    padding: 7px 12px;
    border-radius: 5px;
}
QMenu::item:selected {
    background: #212a37;
    color: #e8a33d;
}

QPushButton#iconBtn, QPushButton#dangerBtn {
    background: transparent;
    border: none;
    padding: 4px 8px;
    font-size: 13px;
}
QPushButton#iconBtn:hover { background: #212a37; border-radius: 5px; }
QPushButton#dangerBtn { color: #e0616b; }
QPushButton#dangerBtn:hover { background: rgba(224,97,107,0.12); border-radius: 5px; }

QStatusBar {
    background: #10141a;
    color: #7d8a9a;
    font-family: 'JetBrains Mono', 'DejaVu Sans Mono', monospace;
    font-size: 11.5px;
    border-top: 1px solid #2a3341;
}
"""


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("virt-connect")
        self.resize(640, 560)
        if ICON_PATH.exists():
            self.setWindowIcon(QIcon(str(ICON_PATH)))

        self.hosts = config.load_hosts()
        self.cards = {}  # host name -> HostCard
        self._refresh_worker = None
        self._connect_workers = []  # keep references so they aren't GC'd mid-run
        self._power_workers = []  # keep references so they aren't GC'd mid-run

        central = QWidget()
        central.setObjectName("central")
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(20, 18, 20, 12)
        root.setSpacing(14)

        header = QWidget()
        from PyQt6.QtWidgets import QHBoxLayout

        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        brand_box = QVBoxLayout()
        brand = QLabel("> virt-connect")
        brand.setObjectName("brand")
        sub = QLabel("libvirt console launcher")
        sub.setObjectName("brandSub")
        brand_box.addWidget(brand)
        brand_box.addWidget(sub)
        header_layout.addLayout(brand_box)
        header_layout.addStretch(1)

        add_btn = QPushButton("+ Add host")
        add_btn.setObjectName("primaryBtn")
        add_btn.clicked.connect(self.on_add_host)
        header_layout.addWidget(add_btn)
        root.addWidget(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.scroll_content = QWidget()
        self.scroll_content.setObjectName("scrollContent")
        self.list_layout = QVBoxLayout(self.scroll_content)
        self.list_layout.setSpacing(12)
        self.list_layout.addStretch(1)
        scroll.setWidget(self.scroll_content)
        root.addWidget(scroll, stretch=1)

        self.status = QStatusBar()
        self.setStatusBar(self.status)

        self.rebuild_cards()
        self.refresh()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(REFRESH_INTERVAL_MS)

    # -- host list management -------------------------------------------------

    def rebuild_cards(self):
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.cards.clear()

        for h in self.hosts:
            card = HostCard(h["name"], h["uri"])
            card.connect_requested.connect(self.on_connect_requested)
            card.power_requested.connect(self.on_power_requested)
            card.refresh_requested.connect(lambda name: self.refresh())
            card.delete_requested.connect(self.on_delete_host)
            self.list_layout.addWidget(card)
            self.cards[h["name"]] = card
        self.list_layout.addStretch(1)

    def on_add_host(self):
        dlg = AddHostDialog(self)
        if dlg.exec():
            name, uri = dlg.values()
            if not name or not uri:
                QMessageBox.warning(self, "virt-connect", "Name and URI are both required.")
                return
            if any(h["name"] == name for h in self.hosts):
                QMessageBox.warning(self, "virt-connect", "A host with that name already exists.")
                return
            self.hosts.append({"name": name, "uri": uri})
            config.save_hosts(self.hosts)
            self.rebuild_cards()
            self.refresh()

    def on_delete_host(self, name):
        reply = QMessageBox.question(
            self,
            "Remove host",
            f'Remove host "{name}"? This only affects this list, not the hypervisor.',
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self.hosts = [h for h in self.hosts if h["name"] != name]
        config.save_hosts(self.hosts)
        self.rebuild_cards()
        self.refresh()

    # -- refreshing -------------------------------------------------------------

    def refresh(self):
        if self._refresh_worker is not None and self._refresh_worker.isRunning():
            return  # a refresh is already in flight
        self.status.showMessage("Refreshing…")
        self._refresh_worker = RefreshWorker(self.hosts)
        self._refresh_worker.finished_all.connect(self.on_refreshed)
        self._refresh_worker.start()

    def on_refreshed(self, results):
        for r in results:
            card = self.cards.get(r["name"])
            if card:
                card.set_content(r["vms"], r["error"])
        self.status.showMessage("Up to date", 4000)

    # -- connecting -------------------------------------------------------------

    def on_connect_requested(self, uri, vm_name, use_x11):
        for card in self.cards.values():
            card.set_row_busy(vm_name, True)
        worker = ConnectWorker(uri, vm_name, use_x11=use_x11)
        worker.finished_ok.connect(lambda: self._on_connect_done(vm_name, None))
        worker.failed.connect(lambda err: self._on_connect_done(vm_name, err))
        self._connect_workers.append(worker)
        worker.start()

    def _on_connect_done(self, vm_name, error):
        for card in self.cards.values():
            card.set_row_busy(vm_name, False)
        if error:
            QMessageBox.critical(self, "virt-connect", error)
        else:
            self.status.showMessage(f"Launched virt-viewer for {vm_name}", 4000)
        self._connect_workers = [w for w in self._connect_workers if w.isRunning()]

    # -- power control ------------------------------------------------------------

    def on_power_requested(self, uri, vm_name, action):
        for card in self.cards.values():
            card.set_row_busy(vm_name, True)
        worker = PowerWorker(uri, vm_name, action)
        worker.finished_ok.connect(lambda: self._on_power_done(vm_name, action, None))
        worker.failed.connect(lambda err: self._on_power_done(vm_name, action, err))
        self._power_workers.append(worker)
        worker.start()

    def _on_power_done(self, vm_name, action, error):
        for card in self.cards.values():
            card.set_row_busy(vm_name, False)
        if error:
            QMessageBox.critical(self, "virt-connect", error)
        else:
            self.status.showMessage(f"{action} sent to {vm_name}", 4000)
        self._power_workers = [w for w in self._power_workers if w.isRunning()]
        self.refresh()  # pick up the resulting state change


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLESHEET)
    if ICON_PATH.exists():
        app.setWindowIcon(QIcon(str(ICON_PATH)))
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
