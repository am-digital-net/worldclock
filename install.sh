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
sudo apt-get install -y git python3-dev python3-pip cython3 build-essential >/dev/null

echo ">>> [2/5] Packages Python (requirements.txt)..."
# --break-system-packages requis sur Raspberry Pi OS Bookworm+ (PEP 668).
#
# rgbmatrix compile un shim C qui inclut le header "Imaging.h" de Pillow :
# Pillow DOIT etre installee avant le build. Comme pip isole le build par
# defaut (venv temporaire vide), on pre-installe Pillow + les outils de build
# et on desactive l'isolation avec --no-build-isolation.
PIP_OPTS="--break-system-packages"
sudo "$PY" -m pip install $PIP_OPTS Pillow scikit-build-core cython cmake ninja
sudo "$PY" -m pip install $PIP_OPTS --no-build-isolation -r "$PROJECT_DIR/requirements.txt"

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
