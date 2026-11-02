"""Persist the list of hosts to ~/.config/virt-connect/hosts.json

Entries are either libvirt hosts ({"name", "type": "libvirt", "uri"}) or
Proxmox VE hosts ({"name", "type": "proxmox", "url", "token_id",
"token_secret", "verify_tls"}). Entries without "type" are libvirt.
"""
import os
import json
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "virt-connect"
HOSTS_FILE = CONFIG_DIR / "hosts.json"

DEFAULT_HOSTS = [{"name": "Local", "type": "libvirt", "uri": "qemu:///system"}]


def load_hosts():
    if not HOSTS_FILE.exists():
        save_hosts(DEFAULT_HOSTS)
        return list(DEFAULT_HOSTS)
    try:
        return json.loads(HOSTS_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return list(DEFAULT_HOSTS)


def save_hosts(hosts):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    # Proxmox API token secrets live in this file, so keep it owner-only.
    fd = os.open(HOSTS_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(json.dumps(hosts, indent=2))
    os.chmod(HOSTS_FILE, 0o600)
