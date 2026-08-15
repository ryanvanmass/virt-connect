#!/usr/bin/env bash
# Installs virt-connect into the standard XDG user locations and registers
# it as a desktop launcher entry with its own icon.
#
# Usage:
#   ./install.sh            install / update
#   ./install.sh --uninstall   remove everything this script installed
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$HOME/.local/share/virt-connect"
ICON_THEME_DIR="$HOME/.local/share/icons/hicolor"
DESKTOP_DIR="$HOME/.local/share/applications"
DESKTOP_FILE="$DESKTOP_DIR/virt-connect.desktop"
ICON_SIZES=(16 24 32 48 64 128 256)

uninstall() {
  echo "Removing virt-connect..."
  rm -rf "$APP_DIR"
  rm -f "$DESKTOP_FILE"
  for size in "${ICON_SIZES[@]}"; do
    rm -f "$ICON_THEME_DIR/${size}x${size}/apps/virt-connect.png"
  done
  command -v update-desktop-database >/dev/null && \
    update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true
  command -v gtk-update-icon-cache >/dev/null && \
    gtk-update-icon-cache "$ICON_THEME_DIR" 2>/dev/null || true
  echo "Done."
}

if [[ "${1:-}" == "--uninstall" ]]; then
  uninstall
  exit 0
fi

for f in main.py config.py virsh_client.py workers.py widgets.py; do
  if [[ ! -f "$SCRIPT_DIR/$f" ]]; then
    echo "error: expected $f next to install.sh, but it's missing." >&2
    exit 1
  fi
done
if [[ ! -d "$SCRIPT_DIR/assets" ]]; then
  echo "error: assets/ directory (icons) not found next to install.sh." >&2
  exit 1
fi

echo "Installing app files to $APP_DIR..."
mkdir -p "$APP_DIR"
cp -r "$SCRIPT_DIR"/main.py "$SCRIPT_DIR"/config.py "$SCRIPT_DIR"/virsh_client.py \
      "$SCRIPT_DIR"/workers.py "$SCRIPT_DIR"/widgets.py "$SCRIPT_DIR"/assets \
      "$APP_DIR/"

echo "Installing icon into the hicolor theme..."
for size in "${ICON_SIZES[@]}"; do
  src="$APP_DIR/assets/icon-${size}.png"
  if [[ -f "$src" ]]; then
    dest_dir="$ICON_THEME_DIR/${size}x${size}/apps"
    mkdir -p "$dest_dir"
    cp "$src" "$dest_dir/virt-connect.png"
  fi
done

echo "Writing desktop entry to $DESKTOP_FILE..."
mkdir -p "$DESKTOP_DIR"
cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Name=virt-connect
Comment=libvirt console launcher
Exec=python3 $APP_DIR/main.py
Icon=virt-connect
Terminal=false
Categories=System;Network;
EOF

echo "Refreshing desktop and icon caches..."
command -v update-desktop-database >/dev/null && \
  update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true
command -v gtk-update-icon-cache >/dev/null && \
  gtk-update-icon-cache "$ICON_THEME_DIR" 2>/dev/null || true

echo
echo "Installed. virt-connect should now appear in your app launcher."
echo "Re-run this script any time to update it after pulling changes."
echo "To remove it later: ./install.sh --uninstall"
