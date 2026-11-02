"""Viewer selection: virt-viewer/remote-viewer everywhere but macOS, Saffron on macOS."""
import os
import stat

import pytest

import proxmox_client
import viewer
import virsh_client


@pytest.fixture
def no_saffron(monkeypatch, tmp_path):
    monkeypatch.delenv("VIRT_CONNECT_SAFFRON", raising=False)
    monkeypatch.setenv("PATH", str(tmp_path))
    monkeypatch.setattr(viewer, "SAFFRON_APP_EXECUTABLES", (str(tmp_path / "Saffron.app/Contents/MacOS/saffron"),))
    return tmp_path


def _exe(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\n")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return str(path)


def test_linux_keeps_virt_viewer_tools():
    assert viewer.libvirt_command("qemu:///system", "vm", platform="linux") == [
        "virt-viewer", "--connect", "qemu:///system", "--wait", "vm"]
    assert viewer.vv_command("/tmp/x.vv", platform="linux") == ["remote-viewer", "/tmp/x.vv"]
    assert viewer.name(platform="linux") == "virt-viewer"
    assert viewer.name(proxmox=True, platform="linux") == "remote-viewer"


def test_mac_uses_saffron_for_both_paths(no_saffron):
    exe = _exe(no_saffron / "Saffron.app/Contents/MacOS/saffron")
    assert viewer.libvirt_command("qemu+ssh://root@kvm/system", "vm", platform="darwin") == [
        exe, "--connect", "qemu+ssh://root@kvm/system", "--wait", "vm"]
    assert viewer.vv_command("/tmp/x.vv", platform="darwin") == [exe, "/tmp/x.vv"]
    assert viewer.name(proxmox=True, platform="darwin") == "Saffron"


def test_saffron_lookup_order(no_saffron, monkeypatch):
    app = _exe(no_saffron / "Saffron.app/Contents/MacOS/saffron")
    assert viewer.find_saffron() == app
    on_path = _exe(no_saffron / "saffron")
    assert viewer.find_saffron() == on_path
    monkeypatch.setenv("VIRT_CONNECT_SAFFRON", "/opt/custom/saffron")
    assert viewer.find_saffron() == "/opt/custom/saffron"


def test_missing_saffron_explains_where_to_get_it(no_saffron):
    with pytest.raises(viewer.ViewerNotFound, match="Saffron is not installed.*releases"):
        viewer.vv_command("/tmp/x.vv", platform="darwin")


def test_launch_reports_missing_binary():
    with pytest.raises(viewer.ViewerNotFound, match="no-such-viewer is not installed"):
        viewer.launch(["no-such-viewer"])


def test_virsh_connect_launches_viewer(monkeypatch):
    launched = {}
    monkeypatch.setattr(viewer, "launch", lambda cmd, use_x11=False: launched.update(cmd=cmd, x11=use_x11))
    monkeypatch.setattr(viewer, "libvirt_command", lambda uri, vm: ["V", uri, vm])
    virsh_client.connect("qemu:///system", "vm", use_x11=True)
    assert launched == {"cmd": ["V", "qemu:///system", "vm"], "x11": True}


def test_proxmox_connect_opens_vv_in_viewer(monkeypatch):
    launched = {}
    monkeypatch.setattr(viewer, "vv_viewer", lambda: "/Applications/Saffron.app/Contents/MacOS/saffron")
    monkeypatch.setattr(viewer, "launch", lambda cmd, use_x11=False: launched.update(cmd=cmd))
    monkeypatch.setattr(proxmox_client, "spice_config", lambda host, vm_id: {
        "type": "spice", "host": "pvespiceproxy:x", "tls-port": 61000, "delete-this-file": 1,
        "ca": "-----BEGIN CERTIFICATE-----\nAAA\n-----END CERTIFICATE-----"})
    proxmox_client.connect({"type": "proxmox"}, "pve/100")
    exe, path = launched["cmd"]
    assert exe.endswith("Saffron.app/Contents/MacOS/saffron")
    text = open(path).read()
    assert "tls-port=61000" in text and "ca=-----BEGIN CERTIFICATE-----\\nAAA\\n" in text
    os.unlink(path)


def test_proxmox_missing_viewer_does_not_fetch_a_ticket(monkeypatch, no_saffron):
    monkeypatch.setattr(viewer, "uses_saffron", lambda platform=None: True)
    def boom(*a):
        raise AssertionError("asked Proxmox for a ticket with no viewer installed")
    monkeypatch.setattr(proxmox_client, "spice_config", boom)
    with pytest.raises(viewer.ViewerNotFound):
        proxmox_client.connect({"type": "proxmox"}, "pve/100")
