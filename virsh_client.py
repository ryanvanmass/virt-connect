"""Thin wrappers around the virsh and virt-viewer command-line tools."""
import os
import re
import subprocess

VIRSH_TIMEOUT = 8  # seconds — keeps a dead remote host from hanging the UI


def list_vms(uri):
    """Return (vms, error). vms is a list of {"name": str, "state": str}."""
    try:
        proc = subprocess.run(
            ["virsh", "-c", uri, "list", "--all"],
            capture_output=True,
            text=True,
            timeout=VIRSH_TIMEOUT,
        )
    except FileNotFoundError:
        return [], "virsh is not installed or not on PATH"
    except subprocess.TimeoutExpired:
        return [], "timed out reaching host"

    if proc.returncode != 0:
        return [], (proc.stderr or "virsh returned an error").strip()

    vms = []
    for line in proc.stdout.splitlines():
        m = re.match(r"^\s*(-|\d+)\s+(\S+)\s+(.+?)\s*$", line)
        if not m:
            continue
        _id, name, state = m.groups()
        vms.append({"name": name, "state": state.strip()})
    return vms, None


def connect(uri, vm, use_x11=False):
    """Launch virt-viewer for the given VM. Raises FileNotFoundError if missing.

    If use_x11 is True, runs with GDK_BACKEND=x11 set — useful for legacy
    systems where virt-viewer's default (often Wayland) backend misbehaves.
    """
    env = None
    if use_x11:
        env = os.environ.copy()
        env["GDK_BACKEND"] = "x11"

    subprocess.Popen(
        ["virt-viewer", "--connect", uri, "--wait", vm],
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=env,
    )


# Maps the action names used in the UI to the virsh subcommand that
# implements them. "pause" suspends a running VM; "resume" un-pauses one;
# "start" boots a shut-off VM; "shutdown" requests a graceful ACPI shutdown.
POWER_COMMANDS = {
    "pause": "suspend",
    "resume": "resume",
    "start": "start",
    "shutdown": "shutdown",
}


def power_action(uri, vm, action):
    """Run a virsh power-control subcommand. Returns (ok, error)."""
    cmd = POWER_COMMANDS.get(action)
    if cmd is None:
        return False, f"unknown power action: {action}"

    try:
        proc = subprocess.run(
            ["virsh", "-c", uri, cmd, vm],
            capture_output=True,
            text=True,
            timeout=VIRSH_TIMEOUT,
        )
    except FileNotFoundError:
        return False, "virsh is not installed or not on PATH"
    except subprocess.TimeoutExpired:
        return False, "timed out reaching host"

    if proc.returncode != 0:
        return False, (proc.stderr or f"virsh {cmd} failed").strip()
    return True, None
