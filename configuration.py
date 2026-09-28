import os

# ====================================================================
# AEGIS POSE GUARD v6.0 - CYBERPUNK HUD & DUAL VISION CONFIG
# ====================================================================

DEBUG_MODE = True

# Server & Network Topology
WEB_UI_HOST = "0.0.0.0"
WEB_UI_PORT = 4000
MQTT_BROKER = "localhost"
MQTT_PORT = 1883

# Hardware Parameters
ESP32_STREAM_URL = "http://192.168.1.101/capture"
CAPTURE_DURATION_SEC = 10

# Detection & Posture Thresholds
FALL_TORSO_ANGLE_THRESHOLD = 45.0  # Torso angle relative to vertical (degrees)
FALL_ASPECT_RATIO_THRESHOLD = 1.15  # Bounding box width / height ratio for floor alignment
KEYPOINT_CONFIDENCE_MIN = 0.35

# Local Asset Registry (Mapped directly to workspace files)
WORKSPACE_ASSETS = {
    "fell": {
        "title": "Staircase Fall Test",
        "file": "oh no,he fell.png",
        "desc": "High pitch torso displacement on stairs"
    },
    "handsome": {
        "title": "Upright Subject Test",
        "file": "handsome.png",
        "desc": "Nominal upright posture check"
    },
    "leon": {
        "title": "Tactical Stance Test",
        "file": "LEON.png",
        "desc": "Combat ready bent posture analysis"
    },
    "cat": {
        "title": "Non-Human Target Test",
        "file": "cute cat.png",
        "desc": "Non-human object filtering test"
    }
}