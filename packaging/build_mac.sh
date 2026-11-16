#!/bin/bash
# Build the Mac app and a disk image to share: dist/Drive-Organizer-Mac.dmg
# Run from the project folder with the project's Python environment active (see BUILD.md).
set -e
cd "$(dirname "$0")/.."

python -m PyInstaller packaging/drive_organizer.spec --noconfirm

# The disk image shows the app next to an Applications shortcut: drag one onto the other to install.
staging="build/dmg"
rm -rf "$staging" && mkdir -p "$staging"
cp -R "dist/Drive Organizer.app" "$staging/"
ln -s /Applications "$staging/Applications"
hdiutil create -volname "Drive Organizer" -srcfolder "$staging" -ov -format UDZO dist/Drive-Organizer-Mac.dmg
echo "✅ dist/Drive-Organizer-Mac.dmg"
