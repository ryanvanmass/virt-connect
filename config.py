"""Persist the list of libvirt hosts to ~/.config/virt-connect/hosts.json"""
import json
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "virt-connect"
HOSTS_FILE = CONFIG_DIR / "hosts.json"

DEFAULT_HOSTS = [{"name": "Local", "uri": "qemu:///system"}]


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
    HOSTS_FILE.write_text(json.dumps(hosts, indent=2))
