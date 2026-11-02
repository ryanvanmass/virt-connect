from PyQt6.QtCore import QThread, pyqtSignal

import backends
import viewer


class RefreshWorker(QThread):
    """Fetches VM lists for all hosts off the UI thread."""

    finished_all = pyqtSignal(list)  # list of {"name","vms","error"}

    def __init__(self, hosts, parent=None):
        super().__init__(parent)
        self._hosts = [dict(h) for h in hosts]  # snapshot; the UI may edit the list meanwhile

    def run(self):
        results = []
        for h in self._hosts:
            try:
                vms, error = backends.list_vms(h)
            except Exception as e:  # noqa: BLE001 — one bad host shouldn't kill the refresh
                vms, error = [], str(e)
            results.append({"name": h["name"], "vms": vms, "error": error})
        self.finished_all.emit(results)


class ConnectWorker(QThread):
    """Opens a console viewer off the UI thread.

    For libvirt this is just a Popen; for Proxmox it also makes an API call
    to fetch a SPICE ticket, so it really does need to be off the UI thread.
    """

    finished_ok = pyqtSignal()
    failed = pyqtSignal(str)

    def __init__(self, host, vm_id, use_x11=False, parent=None):
        super().__init__(parent)
        self._host = dict(host)
        self._vm_id = vm_id
        self._use_x11 = use_x11

    def run(self):
        try:
            backends.connect(self._host, self._vm_id, use_x11=self._use_x11)
            self.finished_ok.emit()
        except viewer.ViewerNotFound as e:
            self.failed.emit(str(e))
        except FileNotFoundError:
            self.failed.emit(f"{backends.viewer_name(self._host)} is not installed or not on PATH")
        except Exception as e:  # noqa: BLE001 — surface any launch failure to the UI
            self.failed.emit(str(e))


class PowerWorker(QThread):
    """Runs a power-control action (pause/resume/start/shutdown) off the UI thread."""

    finished_ok = pyqtSignal()
    failed = pyqtSignal(str)

    def __init__(self, host, vm_id, action, parent=None):
        super().__init__(parent)
        self._host = dict(host)
        self._vm_id = vm_id
        self._action = action

    def run(self):
        try:
            ok, error = backends.power_action(self._host, self._vm_id, self._action)
        except Exception as e:  # noqa: BLE001
            ok, error = False, str(e)
        if ok:
            self.finished_ok.emit()
        else:
            self.failed.emit(error)
