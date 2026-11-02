"""Which console viewer to launch, and how.

Linux (and anything that isn't macOS) keeps the virt-viewer tools:
`virt-viewer --connect URI --wait VM` for libvirt hosts and
`remote-viewer FILE.vv` for Proxmox. On macOS, where virt-viewer is poorly
maintained, both paths open Saffron (https://github.com/ryanvanmass/Saffron)
instead: a SPICE viewer built on IT Toolbox's SPICE client that takes the
same arguments.
"""
import os
import shutil
import subprocess
import sys

SAFFRON_RELEASES = "https://github.com/ryanvanmass/Saffron/releases"

# Where a drag-to-Applications install of Saffron.app puts its executable.
SAFFRON_APP_EXECUTABLES = (
    "/Applications/Saffron.app/Contents/MacOS/saffron",
    "~/Applications/Saffron.app/Contents/MacOS/saffron",
)


class ViewerNotFound(FileNotFoundError):
    """The viewer isn't installed. str() is a message fit for the user."""


def uses_saffron(platform=None):
    return (platform or sys.platform) == "darwin"


def find_saffron():
    """Path to the Saffron executable: $VIRT_CONNECT_SAFFRON, then `saffron`
    on PATH, then Saffron.app in /Applications or ~/Applications."""
    override = os.environ.get("VIRT_CONNECT_SAFFRON")
    if override:
        return override
    on_path = shutil.which("saffron")
    if on_path:
        return on_path
    for candidate in SAFFRON_APP_EXECUTABLES:
        path = os.path.expanduser(candidate)
        if os.access(path, os.X_OK):
            return path
    raise ViewerNotFound(
        f"Saffron is not installed. Download it from {SAFFRON_RELEASES} and drag it to Applications."
    )


def name(proxmox=False, platform=None):
    """The viewer's name, for status messages."""
    if uses_saffron(platform):
        return "Saffron"
    return "remote-viewer" if proxmox else "virt-viewer"


def libvirt_command(uri, vm, platform=None):
    viewer = find_saffron() if uses_saffron(platform) else "virt-viewer"
    return [viewer, "--connect", uri, "--wait", vm]


def vv_viewer(platform=None):
    """The executable that opens .vv connection files."""
    return find_saffron() if uses_saffron(platform) else "remote-viewer"


def vv_command(path, platform=None):
    return [vv_viewer(platform), path]


def launch(cmd, use_x11=False):
    """Start the viewer detached from virt-connect.

    use_x11 sets GDK_BACKEND=x11 for the GTK virt-viewer tools on legacy
    Wayland setups; Saffron is Qt and ignores it.
    """
    env = None
    if use_x11:
        env = os.environ.copy()
        env["GDK_BACKEND"] = "x11"
    try:
        subprocess.Popen(
            cmd,
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env,
        )
    except FileNotFoundError as e:
        raise ViewerNotFound(f"{os.path.basename(cmd[0])} is not installed or not on PATH") from e
