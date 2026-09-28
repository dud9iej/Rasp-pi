import os
import sys
import cv2
import math
import base64
import numpy as np
import urllib.request
from flask import Flask, request, jsonify, render_template_string
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

# 1. Download MediaPipe Pose Model if not present
MODEL_FILE = "pose_landmarker.task"
MODEL_URL = "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_full/float16/latest/pose_landmarker_full.task"

if not os.path.exists(MODEL_FILE):
    print("⏳ Downloading MediaPipe Pose Landmarker model...")
    urllib.request.urlretrieve(MODEL_URL, MODEL_FILE)
    print("✅ Model downloaded successfully!")

# 2. Initialize MediaPipe Detector
base_options = python.BaseOptions(model_asset_path=MODEL_FILE)
options = vision.PoseLandmarkerOptions(
    base_options=base_options,
    running_mode=vision.RunningMode.IMAGE,
    num_poses=1,
    min_pose_detection_confidence=0.5
)
detector = vision.PoseLandmarker.create_from_options(options)

POSE_CONNECTIONS = [
    (11, 12), (11, 13), (13, 15), (12, 14), (14, 16), # Upper Body / Arms
    (11, 23), (12, 24), (23, 24),                   # Torso
    (23, 25), (25, 27), (24, 26), (26, 28)          # Legs
]

# 3. Flask Server Setup
app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AegisPoseGuard - Codespaces Edition</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<bg-slate-950 class="bg-slate-950 text-slate-100 min-h-screen p-6 font-sans">
    <div id="lovable-app" class="w-full max-w-5xl mx-auto p-6 bg-slate-900 rounded-2xl shadow-2xl border border-slate-800">
        <!-- Header Bar -->
        <div class="flex items-center justify-between pb-6 border-b border-slate-800">
            <div class="flex items-center gap-3">
                <div class="w-3 h-3 rounded-full bg-emerald-500 animate-pulse"></div>
                <h1 class="text-xl font-bold bg-gradient-to-r from-emerald-400 to-cyan-400 bg-clip-text text-transparent">
                    AegisPoseGuard <span class="text-xs font-normal text-slate-400 border border-slate-700 px-2 py-0.5 rounded-full">v2.5 (Codespaces)</span>
                </h1>
            </div>
            <div id="status-badge" class="px-3 py-1 text-xs font-semibold rounded-full bg-slate-800 text-slate-400 border border-slate-700">
                IDLE
            </div>
        </div>

        <!-- Dashboard Content -->
        <div class="mt-6">
            <!-- Idle State Banner -->
            <div id="idle-view" class="flex flex-col items-center justify-center py-16 border-2 border-dashed border-slate-800 rounded-xl bg-slate-950/50">
                <div class="w-16 h-16 mb-4 rounded-full bg-emerald-500/10 flex items-center justify-center text-emerald-400 text-2xl">
                    🛡️
                </div>
                <h2 class="text-lg font-medium text-slate-200">System Standing By</h2>
                <p class="text-xs text-slate-500 mt-1 max-w-sm text-center">Activate to initiate a 10-second dual-channel pose scan & fall risk assessment.</p>
                <button id="activate-btn" onclick="startSystem()" class="mt-6 px-6 py-3 bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-400 hover:to-teal-500 text-slate-950 font-bold text-sm rounded-xl transition-all transform hover:scale-105 shadow-lg shadow-emerald-500/20 active:scale-95 flex items-center gap-2">
                    <span>🚀</span> Activate Pose Guard
                </button>
            </div>

            <!-- Active Monitoring Studio -->
            <div id="monitoring-view" class="hidden space-y-4">
                <!-- Timer & Progress Bar -->
                <div class="bg-slate-950 p-4 rounded-xl border border-slate-800 flex flex-col gap-2">
                    <div class="flex justify-between items-center text-xs font-medium">
                        <span class="text-slate-400">Monitoring Scan Duration</span>
                        <span id="timer-text" class="text-emerald-400 font-mono text-sm">10.0s</span>
                    </div>
                    <div class="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
                        <div id="timer-bar" class="bg-gradient-to-r from-emerald-400 to-cyan-400 h-full w-full transition-all duration-100"></div>
                    </div>
                </div>

                <!-- Dual Video Feeds -->
                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <!-- Left View: Raw Camera Feed -->
                    <div class="relative bg-slate-950 rounded-xl overflow-hidden border border-slate-800 shadow-inner">
                        <span class="absolute top-3 left-3 z-10 px-2.5 py-1 text-[10px] font-bold tracking-wider uppercase rounded bg-slate-900/80 text-slate-300 backdrop-blur border border-slate-700">
                            Raw RGB Input
                        </span>
                        <canvas id="webcam-canvas" width="640" height="480" class="hidden"></canvas>
                        <video id="webcam-video" autoplay playsinline class="w-full h-56 md:h-64 object-cover transform -scale-x-100"></video>
                    </div>

                    <!-- Right View: MediaPipe Engine Output -->
                    <div class="relative bg-slate-950 rounded-xl overflow-hidden border border-slate-800 shadow-inner">
                        <span class="absolute top-3 left-3 z-10 px-2.5 py-1 text-[10px] font-bold tracking-wider uppercase rounded bg-emerald-950/80 text-emerald-400 backdrop-blur border border-emerald-800">
                            Vector Skeleton Output
                        </span>
                        <img id="output-frame" class="w-full h-56 md:h-64 object-cover" />
                    </div>
                </div>
            </div>

            <!-- Verdict Banner -->
            <div id="verdict-banner" class="hidden mt-4 p-4 rounded-xl border text-center font-bold text-sm animate-bounce"></div>
        </div>
    </div>

    <script>
        let mediaStream = null;
        let systemActive = false;
        let scanInterval = null;
        let fallFrames = 0;
        let totalFrames = 0;
        let startTime = 0;
        const SCAN_DURATION = 10.0;

        function playBuzzAlarm() {
            try {
                const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
                const osc = audioCtx.createOscillator();
                const gain = audioCtx.createGain();

                osc.type = 'sawtooth';
                osc.frequency.setValueAtTime(160, audioCtx.currentTime);
                osc.frequency.linearRampToValueAtTime(320, audioCtx.currentTime + 0.5);
                osc.frequency.linearRampToValueAtTime(160, audioCtx.currentTime + 1.0);
                osc.frequency.linearRampToValueAtTime(320, audioCtx.currentTime + 1.5);
                osc.frequency.linearRampToValueAtTime(160, audioCtx.currentTime + 2.0);

                gain.gain.setValueAtTime(0.3, audioCtx.currentTime);
                gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 3.0);

                osc.connect(gain);
                gain.connect(audioCtx.destination);

                osc.start();
                osc.stop(audioCtx.currentTime + 3.0);
            } catch (e) {
                console.warn("Audio blocked:", e);
            }
        }

        async function startSystem() {
            document.getElementById('idle-view').classList.add('hidden');
            document.getElementById('monitoring-view').classList.remove('hidden');
            document.getElementById('verdict-banner').classList.add('hidden');

            const badge = document.getElementById('status-badge');
            badge.className = "px-3 py-1 text-xs font-semibold rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 animate-pulse";
            badge.innerText = "ACTIVE SCANNING";

            const video = document.getElementById('webcam-video');
            mediaStream = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 } });
            video.srcObject = mediaStream;
            await new Promise((resolve) => video.onloadedmetadata = resolve);

            systemActive = true;
            fallFrames = 0;
            totalFrames = 0;
            startTime = Date.now();

            scanInterval = setInterval(processLoop, 80);
        }

        function stopCamera() {
            if (mediaStream) {
                mediaStream.getTracks().forEach(track => track.stop());
                mediaStream = null;
            }
            if (scanInterval) clearInterval(scanInterval);
            systemActive = false;
        }

        async function processLoop() {
            if (!systemActive) return;

            const elapsed = (Date.now() - startTime) / 1000.0;
            const timeLeft = Math.max(0, SCAN_DURATION - elapsed);
            
            document.getElementById('timer-bar').style.width = `${(timeLeft / SCAN_DURATION) * 100}%`;
            document.getElementById('timer-text').innerText = `${timeLeft.toFixed(1)}s`;

            if (elapsed >= SCAN_DURATION) {
                finishScan();
                return;
            }

            const video = document.getElementById('webcam-video');
            const canvas = document.getElementById('webcam-canvas');
            const ctx = canvas.getContext('2d');
            ctx.drawImage(video, 0, 0, 640, 480);
            const frameData = canvas.toDataURL('image/jpeg', 0.8);

            try {
                const res = await fetch('/process_frame', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ image: frameData })
                });
                const data = await res.json();
                
                if (data.processed_image) {
                    document.getElementById('output-frame').src = data.processed_image;
                }
                
                if (data.detected) {
                    totalFrames++;
                    if (data.is_down) fallFrames++;
                }
            } catch (err) {
                console.error("Frame processing error:", err);
            }
        }

        function finishScan() {
            stopCamera();
            document.getElementById('monitoring-view').classList.add('hidden');
            document.getElementById('idle-view').classList.remove('hidden');

            const badge = document.getElementById('status-badge');
            badge.className = "px-3 py-1 text-xs font-semibold rounded-full bg-slate-800 text-slate-400 border border-slate-700";
            badge.innerText = "IDLE";

            const banner = document.getElementById('verdict-banner');
            banner.classList.remove('hidden');

            const isFall = totalFrames > 0 && (fallFrames / totalFrames > 0.35);

            if (isFall) {
                banner.className = "mt-4 p-4 rounded-xl border text-center font-bold text-sm bg-rose-500/10 text-rose-400 border-rose-500/30";
                banner.innerHTML = "⚠️ CRITICAL ALERT: Fall Detected! Person down or unconscious.";
                playBuzzAlarm();
            } else {
                banner.className = "mt-4 p-4 rounded-xl border text-center font-bold text-sm bg-emerald-500/10 text-emerald-400 border-emerald-500/30";
                banner.innerHTML = "✅ VERDICT: Person is Awake & Upright. System returned to standby.";
            }
        }
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/process_frame', methods=['POST'])
def process_frame():
    data = request.json
    if not data or 'image' not in data:
        return jsonify({'error': 'No frame supplied'}), 400

    # Base64 Decode
    encoded_data = data['image'].split(',')[1]
    nparr = np.frombuffer(base64.b64decode(encoded_data), np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    h, w, _ = frame.shape

    # MediaPipe Analysis
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
    detection_result = detector.detect(mp_image)

    detected = False
    is_down = False
    torso_angle = 0.0

    if detection_result.pose_landmarks:
        detected = True
        landmarks = detection_result.pose_landmarks[0]

        # Draw Skeleton Connections
        for start_idx, end_idx in POSE_CONNECTIONS:
            pt1 = (int(landmarks[start_idx].x * w), int(landmarks[start_idx].y * h))
            pt2 = (int(landmarks[end_idx].x * w), int(landmarks[end_idx].y * h))
            cv2.line(frame, pt1, pt2, (0, 255, 136), 2)

        # Draw Joints
        for lm in landmarks:
            cx, cy = int(lm.x * w), int(lm.y * h)
            cv2.circle(frame, (cx, cy), 3, (255, 200, 0), -1)

        # Telemetry & Fall Detection
        ls, rs = landmarks[11], landmarks[12]
        lh, rh = landmarks[23], landmarks[24]
        nose = landmarks[0]

        shoulder_avg_y = (ls.y + rs.y) / 2.0
        hip_avg_y = (lh.y + rh.y) / 2.0
        shoulder_avg_x = (ls.x + rs.x) / 2.0
        hip_avg_x = (lh.x + rh.x) / 2.0

        dx = shoulder_avg_x - hip_avg_x
        dy = shoulder_avg_y - hip_avg_y
        torso_angle = math.degrees(math.atan2(abs(dx), abs(dy)))

        if torso_angle > 50 or nose.y >= hip_avg_y - 0.05:
            is_down = True
            status_text = "STATE: FALL / DOWN"
            status_color = (0, 0, 255)
        else:
            status_text = "STATE: UPRIGHT"
            status_color = (0, 255, 0)

        cv2.putText(frame, status_text, (15, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.7, status_color, 2)
        cv2.putText(frame, f"Torso Angle: {torso_angle:.1f}deg", (15, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (220, 220, 220), 1)

    # Base64 Encode Output Frame
    _, buffer = cv2.imencode('.jpg', frame)
    processed_base64 = f"data:image/jpeg;base64,{base64.b64encode(buffer).decode('utf-8')}"

    return jsonify({
        'processed_image': processed_base64,
        'detected': detected,
        'is_down': is_down,
        'torso_angle': torso_angle
    })

if __name__ == '__main__':
    print("🚀 AegisPoseGuard running on http://127.0.0.1:5000")
    app.run(host='0.0.0.0', port=5000, debug=False)