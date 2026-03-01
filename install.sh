#!/bin/bash

set -e

ENABLE_WEBUI=false
for arg in "$@"; do
    case $arg in
        --webui)
            ENABLE_WEBUI=true
            ;;
    esac
done

echo "=== Pi FM Radio Installer ==="
echo

if [ "$EUID" -ne 0 ]; then
    echo "Please run as root (sudo ./install.sh)"
    exit 1
fi

if ! grep -q "Raspberry Pi" /proc/cpuinfo 2>/dev/null; then
    echo "Warning: This doesn't appear to be a Raspberry Pi"
    read -p "Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo "[1/6] Installing dependencies..."
apt-get update
apt-get install -y git sox libsox-fmt-mp3 curl build-essential

echo "[2/6] Building PiFmRds..."
if [ ! -d "/tmp/PiFmRds" ]; then
    git clone https://github.com/ChristopheJacquet/PiFmRds.git /tmp/PiFmRds
fi
cd /tmp/PiFmRds/src
make
cp pi_fm_rds /usr/local/bin/
cd -

echo "[3/6] Installing fm-radio script..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cp "$SCRIPT_DIR/fm-radio.sh" /usr/local/bin/fm-radio.sh
chmod +x /usr/local/bin/fm-radio.sh

echo "[4/6] Setting up configuration..."
mkdir -p /etc/fm-radio
if [ ! -f /etc/fm-radio/config ]; then
    cp "$SCRIPT_DIR/config.example" /etc/fm-radio/config
    echo "Created config at /etc/fm-radio/config"
    echo "Please edit this file to set your stream URL!"
else
    echo "Config already exists at /etc/fm-radio/config"
fi

echo "[5/6] Installing systemd service..."
cp "$SCRIPT_DIR/fm-radio.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable fm-radio.service

echo "[6/6] Installing Web UI..."
WEBUI_WAS_RUNNING=false
if systemctl is-active --quiet fm-radio-webui 2>/dev/null; then
    WEBUI_WAS_RUNNING=true
    systemctl stop fm-radio-webui
fi
cp "$SCRIPT_DIR/webui.py" /usr/local/bin/fm-radio-webui.py
chmod +x /usr/local/bin/fm-radio-webui.py
cp "$SCRIPT_DIR/fm-radio-webui.service" /etc/systemd/system/
systemctl daemon-reload
if [ "$WEBUI_WAS_RUNNING" = true ] || [ "$ENABLE_WEBUI" = true ]; then
    systemctl enable --now fm-radio-webui
    echo "Web UI enabled and started"
fi

echo
echo "=== Installation complete! ==="
echo
echo "Next steps:"
echo "  1. Edit your config:    sudo nano /etc/fm-radio/config"
echo "  2. Start the service:   sudo systemctl start fm-radio"
echo "  3. Check status:        sudo systemctl status fm-radio"
echo
if [ "$ENABLE_WEBUI" = true ] || [ "$WEBUI_WAS_RUNNING" = true ]; then
    echo "Web UI is running at http://<pi-ip>:8080"
else
    echo "Optional - Enable Web UI:"
    echo "  sudo systemctl enable --now fm-radio-webui"
    echo "  Then visit http://<pi-ip>:8080"
fi
echo
echo "Note: FM transmission requires a wire connected to GPIO 4 as antenna."
