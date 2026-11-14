#!/bin/sh
# Adds Lizard, with its icon, to the desktop's application menu for the current user.
#
#   packaging/linux/install-desktop-entry.sh                 uses the `lizard` command on the PATH
#   packaging/linux/install-desktop-entry.sh /opt/lizard     uses that program (e.g. the PyInstaller binary)
#   packaging/linux/install-desktop-entry.sh --remove        takes it out of the menu again
set -eu

here=$(cd "$(dirname "$0")" && pwd)
assets="$here/../../lizard/assets"
data="${XDG_DATA_HOME:-$HOME/.local/share}"
apps="$data/applications"
icons="$data/icons/hicolor"

refresh_caches() {
    if command -v update-desktop-database >/dev/null 2>&1; then update-desktop-database "$apps" || true; fi
    if command -v gtk-update-icon-cache >/dev/null 2>&1; then gtk-update-icon-cache -q -t "$icons" || true; fi
}

if [ "${1:-}" = "--remove" ]; then
    rm -f "$apps/lizard.desktop"
    for size in 48 64 256 512; do
        rm -f "$icons/${size}x${size}/apps/lizard.png"
    done
    refresh_caches
    echo "Lizard was removed from the application menu."
    exit 0
fi

program="${1:-$(command -v lizard || true)}"
if [ -z "$program" ] || [ ! -x "$program" ]; then
    echo "Can't find the 'lizard' program. Install Lizard first (pip install .), activate its virtual" >&2
    echo "environment, or pass the path of the program: $0 /path/to/lizard" >&2
    exit 1
fi

for size in 48 64 256 512; do
    mkdir -p "$icons/${size}x${size}/apps"
done
cp "$assets/lizard-48.png" "$icons/48x48/apps/lizard.png"
cp "$assets/lizard-64.png" "$icons/64x64/apps/lizard.png"
cp "$assets/lizard.png" "$icons/256x256/apps/lizard.png"
cp "$assets/lizard-512.png" "$icons/512x512/apps/lizard.png"

mkdir -p "$apps"
sed "s|^Exec=lizard\$|Exec=\"$program\"|" "$here/lizard.desktop" > "$apps/lizard.desktop"
refresh_caches
echo "Lizard was added to the application menu: $apps/lizard.desktop"
