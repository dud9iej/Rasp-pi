#!/usr/bin/env bash

# ====================================================================
# AEGIS POSE GUARD v5.5 - STORAGE DEEP CLEAN & FRESH ENVIRONMENT SETUP
# ====================================================================

set -e

echo "🧹 [1/5] Wiping simulation caches, build artifacts, and temp buffers..."

# 1. Purge all Python bytecode, cache folders, and temp builds (preserving *.py / *.ino scripts)
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete 2>/dev/null || true
find . -type f -name "*.pyo" -delete 2>/dev/null || true

# 2. Clear global user caches (Pip, PyTorch, Ultralytics model downloads)
rm -rf ~/.cache/pip
rm -rf ~/.cache/torch
rm -rf ~/.cache/ultralytics
rm -rf ~/.cache/matplotlib 2>/dev/null || true

# 3. Clear temporary RAM/disk swap buffers
sudo rm -rf /tmp/* 2>/dev/null || true
sudo rm -rf /var/tmp/* 2>/dev/null || true
export TMPDIR=/var/tmp

# 4. Deep-clean APT package archives & system journal logs
echo "🗑️ [2/5] Cleaning APT archives and system journal logs..."
sudo apt-get clean
sudo apt-get autoremove --purge -y
sudo journalctl --vacuum-size=10M 2>/dev/null || true

# 5. Remove old virtual environment for a clean start
if [ -d ".venv" ]; then
    echo "♻️ Removing old virtual environment (.venv)..."
    rm -rf .venv
fi

echo "✨ Storage successfully reclaimed!"
echo "📦 [3/5] Installing core C++ & OpenGL system packages..."

sudo apt-get update && sudo apt-get install -y \
    python3-pip \
    python3-venv \
    python3-dev \
    libgl1 \
    libglx-mesa0 \
    libglib2.0-0 \
    mosquitto \
    mosquitto-clients \
    git \
    curl

echo "🐍 [4/5] Building clean virtual environment..."
python3 -m venv .venv
source .venv/bin/activate

echo "⚡ [5/5] Installing lightweight dependencies (No-Cache CPU Mode)..."
pip install --no-cache-dir --upgrade pip

# Install lightweight CPU-only PyTorch (prevents 2.5GB CUDA download)
pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu

# Install core runtime dependencies (using opencv-python to satisfy ultralytics)
pip install --no-cache-dir \
    flask \
    paho-mqtt \
    mediapipe \
    ultralytics \
    opencv-python \
    numpy \
    requests

# Re-ensure sample assets directory exists
mkdir -p static/samples

echo "🖼️ Checking sample test assets..."
[ ! -f "sample_fallen.jpg" ] && curl -s -L "https://images.unsplash.com/photo-1584515979956-d9f6e5d09982?w=600" -o sample_fallen.jpg || true
[ ! -f "sample_standing.jpg" ] && curl -s -L "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=600" -o sample_standing.jpg || true
[ ! -f "sample_leon.png" ] && curl -s -L "https://i.ibb.co/3kWz141/leon.png" -o sample_leon.png || true

# VS Code config verification
mkdir -p .vscode
cat << 'EOF' > .vscode/settings.json
{
    "python.defaultInterpreterPath": "${workspaceFolder}/.venv/bin/python",
    "python.analysis.extraPaths": ["${workspaceFolder}"],
    "editor.formatOnSave": true
}
EOF

cat << 'EOF' > .vscode/launch.json
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Run Web UI (Debug Mode)",
            "type": "debugpy",
            "request": "launch",
            "program": "${workspaceFolder}/web_ui.py",
            "console": "integratedTerminal"
        },
        {
            "name": "Run Main Engine (Pi Mode)",
            "type": "debugpy",
            "request": "launch",
            "program": "${workspaceFolder}/main_engine.py",
            "console": "integratedTerminal"
        }
    ]
}
EOF

echo "🎉 Total reset complete! All scripts preserved and dependencies resolved."
echo "🚀 Run Web UI with: source .venv/bin/activate && python web_ui.py"