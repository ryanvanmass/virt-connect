"""Talk to a Proxmox VE server over its REST API (no extra dependencies).

Authentication uses a Proxmox API token, sent as
``Authorization: PVEAPIToken=USER@REALM!TOKENID=SECRET``. Tokens don't need
the CSRF header that ticket/cookie auth does, so POSTs work as-is.

A Proxmox host entry in hosts.json looks like::

    {
      "name": "pve",
      "type": "proxmox",
      "url": "https://pve.lan:8006",
      "token_id": "root@pam!virt-connect",
      "token_secret": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
      "verify_tls": false
    }

VMs are identified as ``"<node>/<vmid>"`` so a cluster with several nodes
works without an extra lookup when sending power actions or opening a
console.
"""
import json
import os
import ssl
import tempfile
import urllib.error
import urllib.parse
import urllib.request

import viewer

API_TIMEOUT = 8  # seconds — same budget as virsh, keeps a dead host from hanging a refresh

# UI action name -> Proxmox status endpoint (POST /nodes/{node}/qemu/{vmid}/status/<x>).
# "suspend" on Proxmox pauses the guest in memory, matching "virsh suspend".
POWER_COMMANDS = {
    "pause": "suspend",
    "resume": "resume",
    "start": "start",
    "shutdown": "shutdown",
}


class ProxmoxError(Exception):
    pass


def _base_url(host):
    url = host.get("url", "").strip().rstrip("/")
    if not url:
        raise ProxmoxError("no Proxmox API URL configured")
    if "://" not in url:
        url = "https://" + url
    parsed = urllib.parse.urlparse(url)
    if parsed.port is None:
        # Proxmox's API listens on 8006 by default; add it if the user left it off.
        url = f"{parsed.scheme}://{parsed.hostname}:8006{parsed.path}"
    return url


def _request(host, method, path, data=None):
    """Make an API call and return the decoded ``data`` field of the response."""
    url = f"{_base_url(host)}/api2/json{path}"
    body = None
    headers = {
        "Authorization": f"PVEAPIToken={host.get('token_id', '')}={host.get('token_secret', '')}",
        "Accept": "application/json",
    }
    if data is not None:
        body = urllib.parse.urlencode(data).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    elif method == "POST":
        body = b""

    ctx = ssl.create_default_context()
    if not host.get("verify_tls", True):
        # Proxmox ships with a self-signed certificate; let the user opt out.
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=API_TIMEOUT, context=ctx) as resp:
            payload = json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        if e.code == 401:
            raise ProxmoxError("authentication failed — check the API token ID and secret") from e
        if e.code == 403:
            raise ProxmoxError("permission denied — the API token lacks the needed privilege") from e
        raise ProxmoxError(f"Proxmox API error {e.code}: {e.reason}") from e
    except urllib.error.URLError as e:
        reason = e.reason
        if isinstance(reason, ssl.SSLCertVerificationError):
            raise ProxmoxError(
                "TLS certificate not trusted — enable “skip TLS verification” for self-signed certs"
            ) from e
        if isinstance(reason, TimeoutError):
            raise ProxmoxError("timed out reaching host") from e
        raise ProxmoxError(f"could not reach host: {reason}") from e
    except TimeoutError as e:
        raise ProxmoxError("timed out reaching host") from e
    except json.JSONDecodeError as e:
        raise ProxmoxError("unexpected (non-JSON) response from Proxmox") from e
    return payload.get("data")


def _split_id(vm_id):
    node, _, vmid = vm_id.partition("/")
    if not node or not vmid:
        raise ProxmoxError(f"bad VM id: {vm_id}")
    return node, vmid


def list_vms(host):
    """Return (vms, error). vms is a list of {"id", "name", "state"}.

    States are mapped onto the same vocabulary virsh uses ("running",
    "paused", "shut off") so the UI treats both backends identically.
    """
    try:
        resources = _request(host, "GET", "/cluster/resources?type=vm") or []
        vms = []
        for r in resources:
            if r.get("type") != "qemu" or r.get("template"):
                continue  # skip LXC containers (no SPICE console) and templates
            node, vmid = r.get("node"), r.get("vmid")
            status = r.get("status", "unknown")
            if status == "running":
                # cluster/resources reports paused guests as "running"; the real
                # QEMU state is only in status/current.
                try:
                    cur = _request(host, "GET", f"/nodes/{node}/qemu/{vmid}/status/current") or {}
                    if cur.get("qmpstatus") in ("paused", "suspended"):
                        status = "paused"
                except ProxmoxError:
                    pass
            elif status == "stopped":
                status = "shut off"
            name = r.get("name") or f"vm{vmid}"
            vms.append({"id": f"{node}/{vmid}", "name": f"{name} ({vmid})", "state": status})
        vms.sort(key=lambda v: v["name"].lower())
        return vms, None
    except ProxmoxError as e:
        return [], str(e)


def power_action(host, vm_id, action):
    """Send a power action. Returns (ok, error)."""
    cmd = POWER_COMMANDS.get(action)
    if cmd is None:
        return False, f"unknown power action: {action}"
    try:
        node, vmid = _split_id(vm_id)
        _request(host, "POST", f"/nodes/{node}/qemu/{vmid}/status/{cmd}")
    except ProxmoxError as e:
        return False, str(e)
    return True, None


def spice_config(host, vm_id):
    """Ask Proxmox for a one-shot SPICE connection config (the .vv file contents).

    Requires the VM's display to be SPICE (qxl) and the token to hold
    VM.Console on it. The ticket inside is single-use and short-lived, so
    launch the viewer right away.
    """
    node, vmid = _split_id(vm_id)
    # "proxy" tells Proxmox which address the client should reach spiceproxy
    # on; use the host the user configured, which we know is reachable.
    proxy = urllib.parse.urlparse(_base_url(host)).hostname
    cfg = _request(host, "POST", f"/nodes/{node}/qemu/{vmid}/spiceproxy", {"proxy": proxy})
    if not cfg:
        raise ProxmoxError("Proxmox returned no SPICE configuration")
    return cfg


def write_vv_file(cfg):
    """Write a SPICE config dict to a private temp .vv file and return its path."""
    lines = ["[virt-viewer]"]
    for key, value in cfg.items():
        if isinstance(value, str):
            value = value.replace("\n", "\\n")  # the CA cert is multi-line
        lines.append(f"{key}={value}")
    fd, path = tempfile.mkstemp(prefix="virt-connect-", suffix=".vv")
    with os.fdopen(fd, "w") as f:
        f.write("\n".join(lines) + "\n")
    os.chmod(path, 0o600)
    return path


def connect(host, vm_id, use_x11=False):
    """Fetch a SPICE ticket and open it in remote-viewer (Saffron on macOS).

    Raises viewer.ViewerNotFound (a FileNotFoundError) if the viewer is
    missing, ProxmoxError for API failures.
    """
    # Resolve the viewer before asking for a ticket, so a missing viewer
    # doesn't burn one (and leave a .vv with a live ticket on disk).
    exe = viewer.vv_viewer()
    path = write_vv_file(spice_config(host, vm_id))
    # Proxmox's config sets delete-this-file=1, so the viewer removes the
    # .vv after reading it (remote-viewer and Saffron both honour it); the
    # ticket inside expires after ~30s regardless.
    try:
        viewer.launch([exe, path], use_x11=use_x11)
    except FileNotFoundError:
        os.unlink(path)
        raise
