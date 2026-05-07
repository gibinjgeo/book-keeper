#!/usr/bin/env bash
set -euo pipefail

VERSION="1.0"
ARCH=$(dpkg --print-architecture 2>/dev/null || echo "amd64")
PKG_NAME="bookkeeper_${VERSION}_${ARCH}"

cd "$(dirname "$0")/.."
ROOT=$(pwd)

BUNDLE="$ROOT/dist/BookKeeper"

# Skip pip+PyInstaller if the bundle already exists (e.g. called from CI after
# a separate PyInstaller step), otherwise do a full local build.
if [ ! -f "$BUNDLE/BookKeeper" ]; then
    echo "[1/4] Installing build dependencies..."
    pip install pyinstaller streamlit pandas altair pyarrow --quiet

    echo "[2/4] Running PyInstaller..."
    pyinstaller build/BookKeeper.spec --noconfirm --clean

    if [ ! -f "$BUNDLE/BookKeeper" ]; then
        echo "ERROR: PyInstaller output not found at $BUNDLE/BookKeeper"
        exit 1
    fi
else
    echo "[1-2/4] Skipping PyInstaller (bundle already exists)"
fi

echo "[3/4] Building .deb package tree..."
DEB_ROOT="$ROOT/dist/$PKG_NAME"
APP_DIR="$DEB_ROOT/opt/book-keeper"
BIN_DIR="$DEB_ROOT/usr/local/bin"
DESKTOP_DIR="$DEB_ROOT/usr/share/applications"
DEBIAN_DIR="$DEB_ROOT/DEBIAN"

rm -rf "$DEB_ROOT"
mkdir -p "$APP_DIR" "$BIN_DIR" "$DESKTOP_DIR" "$DEBIAN_DIR"

# Copy PyInstaller bundle
cp -r "$BUNDLE/." "$APP_DIR/"
chmod +x "$APP_DIR/BookKeeper"

# Wrapper script so `book-keeper` works from the terminal
cat > "$BIN_DIR/book-keeper" <<'EOF'
#!/bin/sh
exec /opt/book-keeper/BookKeeper "$@"
EOF
chmod +x "$BIN_DIR/book-keeper"

# Desktop entry
cat > "$DESKTOP_DIR/book-keeper.desktop" <<EOF
[Desktop Entry]
Version=1.0
Name=Book Keeper
Comment=Offline double-entry accounting
Exec=/opt/book-keeper/BookKeeper
Icon=/opt/book-keeper/icon.png
Terminal=false
Type=Application
Categories=Office;Finance;
StartupNotify=true
EOF

# DEBIAN/control
INSTALLED_SIZE=$(du -sk "$APP_DIR" | cut -f1)
cat > "$DEBIAN_DIR/control" <<EOF
Package: book-keeper
Version: $VERSION
Architecture: $ARCH
Maintainer: gibinjgeo
Installed-Size: $INSTALLED_SIZE
Description: Book Keeper accounting app
 Local offline double-entry bookkeeping application
 built with Python and Streamlit.
EOF

# Fix permissions: DEBIAN dir files must be 644/755
chmod 755 "$DEBIAN_DIR"
chmod 644 "$DEBIAN_DIR/control"

echo "[4/4] Running dpkg-deb..."
dpkg-deb --build --root-owner-group "$DEB_ROOT" "$ROOT/dist/${PKG_NAME}.deb"

echo ""
echo "Done! Installer: dist/${PKG_NAME}.deb"
echo "Install with:  sudo dpkg -i dist/${PKG_NAME}.deb"
