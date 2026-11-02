# virt-connect (Qt)

A native desktop launcher for VM consoles on your KVM/libvirt and
Proxmox VE hosts — no browser involved. Add a host once (local libvirt,
libvirt over SSH, or a Proxmox VE server via its API), and it
auto-discovers VMs: via `virsh` for libvirt, via the REST API for Proxmox.

## Requirements

```
sudo apt install python3-pyqt6 virt-viewer libvirt-clients
```

(`libvirt-clients` provides `virsh`.) If `python3-pyqt6` isn't available
on your Ubuntu release, `pip install PyQt6 --break-system-packages` works
too.

If you'll connect to remote libvirt hosts over SSH (`qemu+ssh://...`),
set up passwordless (key-based) SSH to those hosts first — otherwise
virsh/virt-viewer will block on a password prompt you won't see.

Proxmox hosts need no extra packages: the API is called with Python's
standard library, and consoles open in `remote-viewer` (part of
`virt-viewer`).

## Run

```
cd virt-connect-qt
python3 main.py
```

## Use

- **+ Add host** → name it and pick a type:
  - **libvirt (virsh)** — give a connection URI:
    - Local: `qemu:///system`
    - Remote over SSH: `qemu+ssh://user@host/system`
  - **Proxmox VE (API)** — give the API URL (e.g. `https://pve.lan:8006`;
    port 8006 is assumed if left off), an API token ID
    (`user@realm!tokenname`) and its secret. Tick **Skip TLS verification**
    if the server still uses Proxmox's default self-signed certificate.
    See [Proxmox setup](#proxmox-setup) below.
- Each host card lists its VMs with a running/off indicator, refreshed
  every 15s in the background (won't freeze the window — virsh calls run
  on a worker thread).
- Each VM has two split buttons:
  - **Power control** — defaults to **Pause** for a running VM, or **Start**
    for a paused or shut-off one (resuming vs. booting under the hood,
    respectively). The dropdown arrow adds **Shutdown** as a secondary
    option (a graceful ACPI shutdown via `virsh shutdown`).
  - **Connect** — launches `virt-viewer`. The dropdown adds **Connect (X11
    legacy mode)**, which runs the same command with `GDK_BACKEND=x11` set —
    useful if `virt-viewer` misbehaves under Wayland on older/legacy systems.
- The list refreshes automatically after any power action so the state and
  button label catch up, in addition to the normal 15s background refresh.

Hosts are stored in `~/.config/virt-connect/hosts.json`. Because Proxmox
token secrets are kept there in plain text, the file is written with
owner-only (`0600`) permissions.

## Proxmox setup

1. In the Proxmox web UI, go to **Datacenter → Permissions → API Tokens**
   and add a token (e.g. `root@pam!virt-connect`). Copy the secret — it's
   only shown once.
2. Give the token the privileges it needs, either by unticking
   **Privilege Separation** (it inherits the user's rights) or by granting
   it a role on `/vms` that includes `VM.Audit` (list), `VM.PowerMgmt`
   (start/pause/shutdown) and `VM.Console` (connect). The built-in
   `PVEVMUser` role covers all three.
3. For **Connect** to work, set each VM's **Hardware → Display** to
   **SPICE (qxl)**. virt-connect asks Proxmox for a one-time SPICE ticket
   and opens it in `remote-viewer`, going through Proxmox's SPICE proxy on
   port 3128 of the host you configured.

On Proxmox, VMs are listed across every node in the cluster as
`name (vmid)`. LXC containers and templates are skipped, since they have
no SPICE console.

## Optional: launcher / desktop entry

Run the included installer to install the app under the standard XDG
user locations, register the icon, and create a launcher entry:

```
./install.sh
```

It's safe to re-run any time (e.g. after pulling an update) — it just
overwrites the installed copy. It does three things, matching XDG
conventions rather than pointing anything at wherever you unzipped the
project:

1. Copies the app to `~/.local/share/virt-connect`, so it survives you
   moving or deleting the original folder.
2. Installs each icon size into `~/.local/share/icons/hicolor/<size>/apps/`
   so `Icon=virt-connect` resolves through the icon theme (panel,
   launcher grid, alt-tab all pick whichever size fits) instead of one
   fixed PNG at a hardcoded path.
3. Writes `~/.local/share/applications/virt-connect.desktop` pointing at
   the installed copy, and refreshes the desktop database.

`virt-connect` should then appear in your app launcher with its icon.
Run `./install.sh --uninstall` to remove everything it installed.

<details>
<summary>Doing it by hand instead</summary>

```
mkdir -p ~/.local/share/virt-connect
cp -r main.py config.py backends.py virsh_client.py proxmox_client.py \
    workers.py widgets.py assets \
    ~/.local/share/virt-connect/

for size in 16 24 32 48 64 128 256; do
  dir=~/.local/share/icons/hicolor/${size}x${size}/apps
  mkdir -p "$dir"
  cp ~/.local/share/virt-connect/assets/icon-${size}.png "$dir/virt-connect.png"
done
gtk-update-icon-cache ~/.local/share/icons/hicolor 2>/dev/null || true

cat > ~/.local/share/applications/virt-connect.desktop <<EOF
[Desktop Entry]
Type=Application
Name=virt-connect
Comment=libvirt / Proxmox console launcher
Exec=python3 $HOME/.local/share/virt-connect/main.py
Icon=virt-connect
Terminal=false
Categories=System;Network;
EOF

update-desktop-database ~/.local/share/applications
```

</details>
