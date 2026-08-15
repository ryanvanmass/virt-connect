from PyQt6.QtCore import QThread, pyqtSignal

import virsh_client


class RefreshWorker(QThread):
    """Fetches VM lists for all hosts off the UI thread."""

    finished_all = pyqtSignal(list)  # list of {"name","uri","vms","error"}

    def __init__(self, hosts, parent=None):
        super().__init__(parent)
        self._hosts = hosts

    def run(self):
        results = []
        for h in self._hosts:
            vms, error = virsh_client.list_vms(h["uri"])
            results.append({"name": h["name"], "uri": h["uri"], "vms": vms, "error": error})
        self.finished_all.emit(results)


class ConnectWorker(QThread):
    """Launches virt-viewer off the UI thread (Popen is fast, but keep it consistent)."""

    finished_ok = pyqtSignal()
    failed = pyqtSignal(str)

    def __init__(self, uri, vm, use_x11=False, parent=None):
        super().__init__(parent)
        self._uri = uri
        self._vm = vm
        self._use_x11 = use_x11

    def run(self):
        try:
            virsh_client.connect(self._uri, self._vm, use_x11=self._use_x11)
            self.finished_ok.emit()
        except FileNotFoundError:
            self.failed.emit("virt-viewer is not installed or not on PATH")
        except Exception as e:  # noqa: BLE001 — surface any launch failure to the UI
            self.failed.emit(str(e))
