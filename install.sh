#!/usr/bin/env bash
#
# Installe (ou met a jour) le service World Clock. Idempotent :
# tu peux le relancer autant de fois que tu veux sans rien casser.
#
set -euo pipefail

# Dossier du projet = dossier ou se trouve ce script
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_NAME="worldclock"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
RUN_USER="${SUDO_USER:-$USER}"
PY="$(command -v python3)"

echo ">>> Projet : $PROJECT_DIR"

echo ">>> [1/5] Dependances systeme..."
sudo apt-get update -qq
sudo apt-get install -y git python3-dev cython3 >/dev/null

echo ">>> [2/5] Bibliotheque LED (rgbmatrix)..."
if "$PY" -c "import rgbmatrix" 2>/dev/null; then
  echo "    Deja installee, on saute la compilation."
else
  BUILD_DIR="$HOME/rpi-rgb-led-matrix"
  [ -d "$BUILD_DIR/.git" ] || git clone --depth 1 https://github.com/hzeller/rpi-rgb-led-matrix.git "$BUILD_DIR"
  make -C "$BUILD_DIR/bindings/python" build-python PYTHON="$PY"
  sudo make -C "$BUILD_DIR/bindings/python" install-python PYTHON="$PY"
fi

echo ">>> [3/5] Desactivation du son integre (conflit connu)..."
echo "blacklist snd_bcm2835" | sudo tee /etc/modprobe.d/blacklist-rgb-matrix.conf >/dev/null
sudo modprobe -r snd_bcm2835 2>/dev/null || true

echo ">>> [4/5] Service systemd..."
sudo tee "$SERVICE_FILE" >/dev/null <<SERVICE
[Unit]
Description=World Clock LED Matrix
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$PROJECT_DIR
ExecStart=$PY $PROJECT_DIR/main.py
Restart=always
RestartSec=3
User=root

[Install]
WantedBy=multi-user.target
SERVICE

echo ">>> [5/5] Activation + demarrage..."
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME" >/dev/null
sudo systemctl restart "$SERVICE_NAME"

echo ""
echo ">>> OK. L'horloge tourne et redemarrera automatiquement au boot."
echo "    Etat  : sudo systemctl status $SERVICE_NAME"
echo "    Logs  : journalctl -u $SERVICE_NAME -f"
echo "    Config: $PROJECT_DIR/config.json  (puis: sudo systemctl restart $SERVICE_NAME)"
