#!/usr/bin/env bash

# ====================================================================
# AEGIS POSE GUARD v5.5 - LOW-DISK / RASPBERRY PI SETUP SCRIPT
# ====================================================================

set -e

# 1. Redirect temporary directory away from small /tmp RAM disks
export TMPDIR=/var/tmp

echo "🚀 Starting Aegis Pose Guard setup..."

# 2. Free existing package caches
echo "🧹 Clearing package caches..."
sudo apt-get clean
python3 -m pip cache purge || true

# 3. System Dependencies Setup
echo "📦 Installing C++ build tools & OpenGL dependencies..."
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

# 4. Create Virtual Environment
echo "🐍 Creating Python Virtual Environment (.venv)..."
python3 -m venv .venv
source .venv/bin/activate

# 5. Core Libraries Installation (No-Cache Mode & CPU PyTorch)
echo "⚡ Upgrading pip..."
pip install --no-cache-dir --upgrade pip

echo "📦 Installing lightweight CPU PyTorch..."
pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu

echo "📦 Installing Aegis engine dependencies..."
pip install --no-cache-dir \
    flask \
    paho-mqtt \
    mediapipe \
    ultralytics \
    opencv-python-headless \
    numpy \
    requests

# 6. Workspace Directories & Sample Images
echo "📂 Setting up workspace folders..."
mkdir -p static/samples

echo "🖼️ Downloading Sample Assets..."
curl -s -L "https://images.unsplash.com/photo-1584515979956-d9f6e5d09982?w=600" -o sample_fallen.jpg || true
curl -s -L "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=600" -o sample_standing.jpg || true
curl -s -L "https://i.ibb.co/3kWz141/leon.png" -o sample_leon.png || true

# 7. VS Code Configuration
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

echo "✅ Setup completed successfully!"
echo "🌐 Launch Web UI with: python web_ui.py"