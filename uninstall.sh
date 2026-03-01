#!/bin/bash

set -e

echo "=== Pi FM Radio Uninstaller ==="
echo

if [ "$EUID" -ne 0 ]; then
    echo "Please run as root (sudo ./uninstall.sh)"
    exit 1
fi

echo "[1/4] Stopping and disabling service..."
systemctl stop fm-radio.service 2>/dev/null || true
systemctl disable fm-radio.service 2>/dev/null || true

echo "[2/4] Removing service file..."
rm -f /etc/systemd/system/fm-radio.service
systemctl daemon-reload

echo "[3/4] Removing installed files..."
rm -f /usr/local/bin/fm-radio.sh
rm -f /usr/local/bin/pi_fm_rds

echo "[4/4] Configuration..."
if [ -d /etc/fm-radio ]; then
    read -p "Remove configuration at /etc/fm-radio? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf /etc/fm-radio
        echo "Configuration removed."
    else
        echo "Configuration kept at /etc/fm-radio"
    fi
fi

echo
read -p "Remove dependencies (sox, libsox-fmt-mp3)? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    apt-get remove -y sox libsox-fmt-mp3
    apt-get autoremove -y
    echo "Dependencies removed."
else
    echo "Dependencies kept."
fi

echo
echo "=== Uninstall complete! ==="
