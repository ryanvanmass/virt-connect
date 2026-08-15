# virt-connect (Qt)

A native desktop launcher for `virt-viewer` sessions against your
KVM/libvirt hosts — no browser involved. Add a host once (local or
remote-over-SSH), and it auto-discovers VMs via `virsh`.

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

## Run

```
cd virt-connect-qt
python3 main.py
```

## Use

- **+ Add host** → name it, then give a libvirt connection URI:
  - Local: `qemu:///system`
  - Remote over SSH: `qemu+ssh://user@host/system`
- Each host card lists its VMs with a running/off indicator, refreshed
  every 15s in the background (won't freeze the window — virsh calls run
  on a worker thread).
- Click **Connect** next to any VM to launch `virt-viewer` for it.

Hosts are stored in `~/.config/virt-connect/hosts.json`.

## Optional: launcher / desktop entry

To get this in your app launcher, install it under your XDG user
directories rather than pointing the `.desktop` file at wherever you
happened to unzip it — that way it survives you moving or deleting the
original folder, and the icon resolves through the icon theme instead of
a hardcoded path.

1. **Install the app itself** to `~/.local/share/virt-connect`:

   ```
   mkdir -p ~/.local/share/virt-connect
   cp -r main.py config.py virsh_client.py workers.py widgets.py assets \
       ~/.local/share/virt-connect/
   ```

2. **Install the icon** into the hicolor icon theme, one size per
   directory, named after the app (no `.svg`/`.png` variant suffixes):

   ```
   for size in 16 24 32 48 64 128 256; do
     dir=~/.local/share/icons/hicolor/${size}x${size}/apps
     mkdir -p "$dir"
     cp ~/.local/share/virt-connect/assets/icon-${size}.png "$dir/virt-connect.png"
   done
   gtk-update-icon-cache ~/.local/share/icons/hicolor 2>/dev/null || true
   ```

3. **Add the desktop entry** at
   `~/.local/share/applications/virt-connect.desktop`:

   ```ini
   [Desktop Entry]
   Type=Application
   Name=virt-connect
   Comment=libvirt console launcher
   Exec=python3 %h/.local/share/virt-connect/main.py
   Icon=virt-connect
   Terminal=false
   Categories=System;Network;
   ```

   `Icon=virt-connect` (just the name, no path) lets the desktop
   environment pick whichever installed size fits — panel, launcher grid,
   alt-tab, etc. — instead of scaling one fixed PNG.

4. Refresh the desktop database so the entry shows up immediately:

   ```
   update-desktop-database ~/.local/share/applications
   ```

After this, `virt-connect` should appear in your app launcher with its
own icon. To update the app later, just re-run step 1 to overwrite the
installed copy.
