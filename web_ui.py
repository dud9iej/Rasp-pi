from flask import Flask, render_template_string, request, jsonify, send_from_directory
import paho.mqtt.client as mqtt
import cv2
import numpy as np
import base64
import os
import json
import threading
import time

try:
    from main_engine import AegisCyberEngine
except ImportError:
    AegisCyberEngine = None

import configuration as config

app = Flask(__name__)

engine = AegisCyberEngine() if AegisCyberEngine else None

DEFAULT_TELEMETRY = {
    "status": "CLEAR",
    "state": "UPRIGHT",
    "risk_level": "NOMINAL",
    "torso_angle": 0.0,
    "head_angle": 0.0,
    "d_head": 0.0,
    "d_ankle": 0.0,
    "percentage_change": 0.0,
    "confidence": 0.0,
    "detected": False,
    "target_detected": False,
    "fps": 60.0,
    "source": "Aegis_Tactical_Core"
}

latest_telemetry = DEFAULT_TELEMETRY.copy()
MQTT_BROKER = getattr(config, "MQTT_BROKER", "localhost")
MQTT_PORT = getattr(config, "MQTT_PORT", 1883)
mqtt_connected = False

def on_connect(client, userdata, flags, rc, properties=None):
    global mqtt_connected
    if rc == 0:
        mqtt_connected = True
        client.subscribe("aegis/telemetry")

def on_message(client, userdata, msg):
    global latest_telemetry
    if msg.topic == "aegis/telemetry":
        try:
            payload = json.loads(msg.payload.decode('utf-8'))
            latest_telemetry.update(payload)
        except Exception:
            pass

try:
    mqtt_client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id="Aegis_Web_UI_60FPS"
    )
    mqtt_client.on_connect = on_connect
except AttributeError:
    mqtt_client = mqtt.Client(client_id="Aegis_Web_UI_60FPS")

mqtt_client.on_message = on_message

def mqtt_thread():
    while True:
        try:
            mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
            mqtt_client.loop_forever()
        except Exception:
            time.sleep(3)

threading.Thread(target=mqtt_thread, daemon=True).start()

# --- ROBUST INFERNO HTML/JS TEMPLATE ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AEGIS POSE GUARD // FORSAKEN INFERNO 60FPS HUD</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/@mediapipe/pose/pose.js" crossorigin="anonymous"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700;900&display=swap');
        * { font-family: 'JetBrains Mono', monospace; }
        
        .panel-normal { background: rgba(11, 15, 25, 0.96); border: 1px solid #1e293b; transition: all 0.3s ease; }
        .panel-inferno { background: rgba(22, 4, 2, 0.98); border: 3px solid #ff3300; box-shadow: 0 0 60px rgba(255, 50, 0, 0.9), inset 0 0 35px rgba(255, 100, 0, 0.6); }
        
        @keyframes flamePulse {
            0% { filter: drop-shadow(0 0 10px #ff3300); }
            50% { filter: drop-shadow(0 0 30px #ff9900) drop-shadow(0 0 10px #ff0000); }
            100% { filter: drop-shadow(0 0 10px #ff3300); }
        }
        .inferno-title { animation: flamePulse 0.8s infinite ease-in-out; }
    </style>
</head>
<body id="body-root" class="bg-[#03060d] text-slate-100 p-4 min-h-screen flex flex-col justify-center items-center select-none overflow-x-hidden transition-colors duration-500">

    <!-- Procedural Fire & Ember Background Canvas -->
    <canvas id="fire-canvas" class="fixed inset-0 pointer-events-none z-50 opacity-0 transition-opacity duration-700"></canvas>

    <!-- Reliable HTML5 Audio Engine Component -->
    <audio id="inferno-audio" src="https://static.wikia.nocookie.net/forsaken2024/images/7/70/M4_slasher_chase.mp3/revision/latest?cb=20250831042328" preload="auto" loop></audio>

    <div id="main-panel" class="w-full max-w-7xl panel-normal rounded-2xl shadow-2xl p-6 space-y-6 relative z-10">
        
        <!-- Header -->
        <div class="flex flex-col md:flex-row md:items-center justify-between pb-4 border-b border-slate-800 gap-4" id="header-border">
            <div class="flex items-center gap-3">
                <div id="status-beacon" class="w-3.5 h-3.5 rounded-full bg-emerald-400"></div>
                <div>
                    <h1 id="app-title" class="text-2xl font-black bg-gradient-to-r from-cyan-400 via-teal-300 to-emerald-400 bg-clip-text text-transparent tracking-wider">
                        AEGIS POSE GUARD 60FPS
                    </h1>
                    <p id="app-subtitle" class="text-[11px] text-slate-400">Clean Feed + Isolated Vector HUD Overlay Window</p>
                </div>
            </div>

            <div class="flex items-center gap-3 text-xs font-mono">
                <div class="bg-slate-900 border border-slate-800 px-3 py-1.5 rounded-lg flex items-center gap-2">
                    <span class="text-slate-400">TARGET FPS:</span>
                    <span id="fps-counter" class="text-emerald-400 font-bold">60</span>
                </div>
                <div id="system-mode-badge" class="px-3 py-1.5 rounded-lg font-bold tracking-wider bg-slate-800 text-slate-400 border border-slate-700">
                    IDLE
                </div>
                <button onclick="openTestSuite()" class="px-4 py-2 bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 text-white font-bold text-xs rounded-xl transition-all shadow-lg cursor-pointer">
                    🧪 ASSET SUITE
                </button>
            </div>
        </div>

        <!-- Main Grid Layout -->
        <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
            
            <!-- Controls & Telemetry -->
            <div class="space-y-4 flex flex-col justify-between">
                <div id="control-deck" class="bg-[#070b14] p-5 rounded-xl border border-slate-800 space-y-4 transition-colors">
                    <span class="text-[10px] text-cyan-400 uppercase tracking-widest font-bold" id="control-deck-title">CONTROL MODULE</span>
                    
                    <div class="space-y-2">
                        <label class="text-xs text-slate-400">Scan Mode</label>
                        <select id="scan-mode-select" class="w-full bg-slate-900 border border-slate-700 rounded-lg p-2.5 text-xs text-slate-200 focus:outline-none focus:border-emerald-500">
                            <option value="10">Timed Scan (10 Seconds)</option>
                            <option value="30">Timed Scan (30 Seconds)</option>
                            <option value="0">Continuous Monitoring</option>
                        </select>
                    </div>

                    <div class="grid grid-cols-2 gap-2">
                        <div class="space-y-1">
                            <label class="text-[10px] text-slate-400">Height (px)</label>
                            <input type="number" id="view-height-input" value="420" min="280" max="900" class="w-full bg-slate-900 border border-slate-700 rounded p-1.5 text-xs text-slate-200 text-center font-bold">
                        </div>
                        <div class="space-y-1">
                            <label class="text-[10px] text-slate-400">Aspect Ratio</label>
                            <select id="aspect-select" class="w-full bg-slate-900 border border-slate-700 rounded p-1.5 text-xs text-slate-200">
                                <option value="16:9">16:9 Widescreen</option>
                                <option value="4:3">4:3 Standard</option>
                                <option value="1:1">1:1 Square</option>
                            </select>
                        </div>
                    </div>

                    <button id="action-btn" onclick="toggleSystemState()" class="w-full py-4 bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-400 hover:to-teal-400 text-slate-950 font-black text-sm rounded-xl transition-all shadow-lg flex items-center justify-center gap-2 cursor-pointer active:scale-95">
                        <span id="btn-icon">🚀</span>
                        <span id="btn-label">ACTIVATE POSE GUARD</span>
                    </button>

                    <!-- Disable Alarm Trigger Button -->
                    <button id="dismiss-alarm-btn" onclick="dismissInfernoAlarm()" class="hidden w-full py-3 bg-gradient-to-r from-red-600 to-amber-600 hover:from-red-500 hover:to-amber-500 text-white font-black text-xs rounded-xl transition-all shadow-[0_0_20px_#ff3300] cursor-pointer animate-bounce">
                        🛑 DISABLE INFERNO ALARM
                    </button>

                    <!-- Timer Bar -->
                    <div class="space-y-1.5">
                        <div class="flex justify-between text-[11px]">
                            <span class="text-slate-400">TIMER:</span>
                            <span id="timer-text" class="text-cyan-400 font-bold">--</span>
                        </div>
                        <div class="w-full bg-slate-900 h-2 rounded-full overflow-hidden border border-slate-800">
                            <div id="timer-bar" class="bg-gradient-to-r from-cyan-400 to-emerald-400 h-full w-0% transition-all duration-100"></div>
                        </div>
                    </div>
                </div>

                <!-- Live State Gauge -->
                <div id="status-deck" class="bg-[#070b14] p-5 rounded-xl border border-slate-800 text-center space-y-2 transition-colors">
                    <span class="text-[10px] text-slate-500 uppercase tracking-widest font-bold" id="status-deck-title">SUBJECT STATUS</span>
                    <div id="risk-gauge" class="text-xl font-black text-emerald-400 tracking-wider">
                        UPRIGHT / SAFE
                    </div>
                </div>

                <!-- Live Telemetry Metrics -->
                <div class="grid grid-cols-2 gap-3 text-xs">
                    <div class="bg-[#070b14] p-3 rounded-xl border border-slate-800 space-y-1" id="metric-card-1">
                        <span class="text-[9px] text-slate-500 block uppercase">Torso Pitch</span>
                        <span id="m-angle" class="text-sm font-bold text-cyan-400">0.0°</span>
                    </div>
                    <div class="bg-[#070b14] p-3 rounded-xl border border-slate-800 space-y-1" id="metric-card-2">
                        <span class="text-[9px] text-slate-500 block uppercase">Pitch Shift</span>
                        <span id="m-pchange" class="text-sm font-bold text-amber-400">0.0%</span>
                    </div>
                </div>
            </div>

            <!-- Dual View Workspaces: Left = Clean Camera, Right = Isolated Vector Overlay Window -->
            <div class="lg:col-span-2 space-y-4 flex flex-col justify-between">
                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                    
                    <!-- Window 1: Clean Camera Stream -->
                    <div id="clean-workspace" class="relative bg-[#02040a] rounded-xl overflow-hidden border border-slate-800 flex items-center justify-center shadow-inner transition-all duration-300" style="height: 420px;">
                        <span class="absolute top-3 left-3 z-30 px-2.5 py-1 text-[9px] font-bold tracking-wider uppercase rounded bg-slate-950/90 text-slate-400 border border-slate-800 backdrop-blur-md">
                            1. CLEAN RAW FEED
                        </span>
                        <video id="webcam-video" autoplay playsinline muted class="absolute inset-0 w-full h-full object-cover transform -scale-x-100"></video>
                    </div>

                    <!-- Window 2: Isolated Vector Overlay Window -->
                    <div id="overlay-workspace" class="relative bg-[#02040a] rounded-xl overflow-hidden border border-cyan-900/50 flex items-center justify-center shadow-inner transition-all duration-300" style="height: 420px;">
                        <span id="overlay-tag" class="absolute top-3 left-3 z-30 px-2.5 py-1 text-[9px] font-bold tracking-wider uppercase rounded bg-slate-950/90 text-cyan-400 border border-cyan-800/50 backdrop-blur-md">
                            2. ISOLATED VECTOR HUD WINDOW
                        </span>
                        <canvas id="skeleton-canvas" class="absolute inset-0 w-full h-full object-cover z-10 transform -scale-x-100"></canvas>
                    </div>

                </div>

                <!-- Dedicated Audio Visualizer Deck -->
                <div id="visualizer-deck" class="bg-[#070b14] border border-slate-800 rounded-xl p-3 h-28 flex flex-col justify-between transition-all">
                    <div class="flex justify-between items-center text-[10px]">
                        <span id="vis-title" class="text-slate-500 font-bold uppercase">AUDIO SPECTRUM VISUALIZER // SLASHER THEME</span>
                        <span id="vis-status" class="text-slate-600">STANDBY</span>
                    </div>
                    <div class="relative w-full h-14 bg-black/80 rounded-lg overflow-hidden border border-slate-900 flex items-end">
                        <canvas id="visualizer-canvas" class="absolute inset-0 w-full h-full"></canvas>
                    </div>
                </div>

                <!-- Dynamic Verdict Banner -->
                <div id="verdict-banner" class="hidden p-4 rounded-xl border text-center font-bold text-sm transition-all"></div>
            </div>
        </div>
    </div>

    <!-- WORKSPACE TEST SUITE MODAL -->
    <div id="test-modal" class="hidden fixed inset-0 bg-black/85 backdrop-blur-md flex items-center justify-center z-50 p-4">
        <div class="bg-[#0b1120] border border-cyan-900/60 rounded-2xl max-w-4xl w-full p-6 space-y-4">
            <div class="flex justify-between items-center pb-2 border-b border-slate-800">
                <h3 class="text-sm font-bold text-cyan-400 uppercase tracking-wider">Aegis Workspace Test Images</h3>
                <button onclick="closeTestSuite()" class="text-slate-400 hover:text-white font-bold text-xl cursor-pointer">&times;</button>
            </div>

            <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
                <button onclick="runAssetTest('fell')" class="p-3 bg-slate-900 hover:bg-slate-800 border border-slate-800 rounded-xl text-left cursor-pointer">
                    <div class="text-xs font-bold text-rose-400">oh no,he fell.png</div>
                    <div class="text-[9px] text-slate-500">Incapacitated / Fallen</div>
                </button>
                <button onclick="runAssetTest('handsome')" class="p-3 bg-slate-900 hover:bg-slate-800 border border-slate-800 rounded-xl text-left cursor-pointer">
                    <div class="text-xs font-bold text-emerald-400">handsome.png</div>
                    <div class="text-[9px] text-slate-500">Upright Subject</div>
                </button>
                <button onclick="runAssetTest('leon')" class="p-3 bg-slate-900 hover:bg-slate-800 border border-slate-800 rounded-xl text-left cursor-pointer">
                    <div class="text-xs font-bold text-cyan-400">LEON.png</div>
                    <div class="text-[9px] text-slate-500">Tactical Stance</div>
                </button>
                <button onclick="runAssetTest('cat')" class="p-3 bg-slate-900 hover:bg-slate-800 border border-slate-800 rounded-xl text-left cursor-pointer">
                    <div class="text-xs font-bold text-amber-400">cute cat.png</div>
                    <div class="text-[9px] text-slate-500">Non-Human Filter</div>
                </button>
            </div>

            <div class="relative bg-black rounded-xl overflow-hidden border border-slate-800 aspect-video flex items-center justify-center">
                <img id="test-output-img" class="w-full h-full object-contain" src="" alt="Test Output">
            </div>

            <div id="test-telemetry-banner" class="p-3 rounded-xl bg-slate-950 border border-slate-800 text-center font-mono text-xs text-slate-400">
                Select an asset above to trigger analysis.
            </div>
        </div>
    </div>

    <script>
        const STATE = { IDLE: 'IDLE', INITIALIZING: 'INITIALIZING', SCANNING: 'SCANNING', STOPPING: 'STOPPING' };
        let currentState = STATE.IDLE;

        let mediaStream = null;
        let pose = null;
        let scanTimer = null;
        let animFrameId = null;
        let fallDetectedInSession = false;
        let alarmTriggered = false;
        let frameCount = 0;
        let lastFpsUpdate = Date.now();
        let lastTelemetryTime = 0;

        let visAnimId = null;
        let fireAnimId = null;

        // Procedural Fire Engine
        const fireCanvas = document.getElementById('fire-canvas');
        const fireCtx = fireCanvas.getContext('2d');
        let fireParticles = [];

        function resizeFireCanvas() {
            fireCanvas.width = window.innerWidth;
            fireCanvas.height = window.innerHeight;
        }
        window.addEventListener('resize', resizeFireCanvas);
        resizeFireCanvas();

        for (let i = 0; i < 90; i++) {
            fireParticles.push({
                x: Math.random() * window.innerWidth,
                y: Math.random() * window.innerHeight + window.innerHeight,
                size: Math.random() * 4 + 1.5,
                speedY: Math.random() * -3 - 2,
                speedX: (Math.random() - 0.5) * 2,
                alpha: Math.random() * 0.8 + 0.2
            });
        }

        function renderProceduralFire() {
            if (!alarmTriggered) return;
            fireAnimId = requestAnimationFrame(renderProceduralFire);
            fireCtx.clearRect(0, 0, fireCanvas.width, fireCanvas.height);

            fireParticles.forEach(p => {
                p.y += p.speedY;
                p.x += p.speedX;
                if (p.y < 0) {
                    p.y = fireCanvas.height + 20;
                    p.x = Math.random() * fireCanvas.width;
                }
                
                fireCtx.fillStyle = `rgba(255, ${Math.floor(Math.random() * 140 + 40)}, 0, ${p.alpha})`;
                fireCtx.beginPath();
                fireCtx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
                fireCtx.fill();
            });
        }

        document.getElementById('view-height-input').addEventListener('input', (e) => {
            const h = parseInt(e.target.value) || 420;
            document.getElementById('clean-workspace').style.height = h + 'px';
            document.getElementById('overlay-workspace').style.height = h + 'px';
        });

        const POSE_CONNECTIONS = [
            [11, 12], [11, 13], [13, 15], [12, 14], [14, 16],
            [11, 23], [12, 24], [23, 24], [23, 25], [24, 26],
            [25, 27], [26, 28], [27, 29], [28, 30], [29, 31], [30, 32]
        ];

        function triggerInfernoAlarm() {
            if (alarmTriggered) return;
            alarmTriggered = true;

            // Transform UI to Full Forsaken Inferno Mode
            document.getElementById('main-panel').className = "w-full max-w-7xl panel-inferno rounded-2xl shadow-2xl p-6 space-y-6 relative z-10 animate-pulse";
            document.getElementById('body-root').className = "bg-[#140301] text-amber-100 p-4 min-h-screen flex flex-col justify-center items-center select-none overflow-x-hidden";
            document.getElementById('header-border').className = "flex flex-col md:flex-row md:items-center justify-between pb-4 border-b border-orange-600 gap-4";
            document.getElementById('app-title').className = "text-2xl font-black bg-gradient-to-r from-orange-500 via-red-500 to-yellow-400 bg-clip-text text-transparent tracking-wider inferno-title";
            document.getElementById('app-subtitle').innerText = "🔥 FORSAKEN SLASHER ALARM ACTIVE // ISOLATED HUD WINDOW";
            document.getElementById('app-subtitle').className = "text-[11px] text-orange-400 font-bold";
            document.getElementById('control-deck').className = "bg-[#1c0502] p-5 rounded-xl border border-orange-600 space-y-4";
            document.getElementById('control-deck-title').className = "text-[10px] text-orange-400 uppercase tracking-widest font-bold";
            document.getElementById('status-deck').className = "bg-[#1c0502] p-5 rounded-xl border border-orange-600 text-center space-y-2";
            document.getElementById('status-deck-title').className = "text-[10px] text-orange-400 uppercase tracking-widest font-bold";
            document.getElementById('metric-card-1').className = "bg-[#1c0502] p-3 rounded-xl border border-orange-600 space-y-1";
            document.getElementById('metric-card-2').className = "bg-[#1c0502] p-3 rounded-xl border border-orange-600 space-y-1";
            
            document.getElementById('clean-workspace').className = "relative bg-black rounded-xl overflow-hidden border border-orange-800 shadow-md flex items-center justify-center transition-all duration-300";
            document.getElementById('overlay-workspace').className = "relative bg-black rounded-xl overflow-hidden border-2 border-orange-500 shadow-[0_0_40px_#ff3300] flex items-center justify-center transition-all duration-300";
            document.getElementById('overlay-tag').className = "absolute top-3 left-3 z-30 px-2.5 py-1 text-[9px] font-bold tracking-wider uppercase rounded bg-red-950 text-orange-300 border border-orange-500 backdrop-blur-md";
            
            document.getElementById('visualizer-deck').className = "bg-[#1c0502] border border-orange-600 rounded-xl p-3 h-28 flex flex-col justify-between shadow-[0_0_20px_rgba(255,50,0,0.5)]";
            document.getElementById('vis-title').className = "text-orange-400 font-bold uppercase";
            document.getElementById('vis-status').className = "text-orange-300 font-bold animate-ping";
            document.getElementById('vis-status').innerText = "LIVE BUMPING";

            document.getElementById('dismiss-alarm-btn').classList.remove('hidden');

            fireCanvas.classList.remove('opacity-0');
            renderProceduralFire();

            const audioElement = document.getElementById('inferno-audio');
            audioElement.play().catch(err => {});

            startVisualizerDeckLoop();
        }

        function dismissInfernoAlarm() {
            alarmTriggered = false;
            const audioElement = document.getElementById('inferno-audio');
            audioElement.pause();
            audioElement.currentTime = 0;

            if (fireAnimId) { cancelAnimationFrame(fireAnimId); fireAnimId = null; }
            if (visAnimId) { cancelAnimationFrame(visAnimId); visAnimId = null; }

            fireCanvas.classList.add('opacity-0');

            document.getElementById('main-panel').className = "w-full max-w-7xl panel-normal rounded-2xl shadow-2xl p-6 space-y-6 relative z-10";
            document.getElementById('body-root').className = "bg-[#03060d] text-slate-100 p-4 min-h-screen flex flex-col justify-center items-center select-none overflow-x-hidden";
            document.getElementById('header-border').className = "flex flex-col md:flex-row md:items-center justify-between pb-4 border-b border-slate-800 gap-4";
            document.getElementById('app-title').className = "text-2xl font-black bg-gradient-to-r from-cyan-400 via-teal-300 to-emerald-400 bg-clip-text text-transparent tracking-wider";
            document.getElementById('app-subtitle').innerText = "Clean Feed + Isolated Vector HUD Overlay Window";
            document.getElementById('app-subtitle').className = "text-[11px] text-slate-400";
            document.getElementById('control-deck').className = "bg-[#070b14] p-5 rounded-xl border border-slate-800 space-y-4";
            document.getElementById('control-deck-title').className = "text-[10px] text-cyan-400 uppercase tracking-widest font-bold";
            document.getElementById('status-deck').className = "bg-[#070b14] p-5 rounded-xl border border-slate-800 text-center space-y-2";
            document.getElementById('status-deck-title').className = "text-[10px] text-slate-500 uppercase tracking-widest font-bold";
            document.getElementById('metric-card-1').className = "bg-[#070b14] p-3 rounded-xl border border-slate-800 space-y-1";
            document.getElementById('metric-card-2').className = "bg-[#070b14] p-3 rounded-xl border border-slate-800 space-y-1";
            
            document.getElementById('clean-workspace').className = "relative bg-[#02040a] rounded-xl overflow-hidden border border-slate-800 flex items-center justify-center shadow-inner transition-all duration-300";
            document.getElementById('overlay-workspace').className = "relative bg-[#02040a] rounded-xl overflow-hidden border border-cyan-900/50 flex items-center justify-center shadow-inner transition-all duration-300";
            document.getElementById('overlay-tag').className = "absolute top-3 left-3 z-30 px-2.5 py-1 text-[9px] font-bold tracking-wider uppercase rounded bg-slate-950/90 text-cyan-400 border border-cyan-800/50 backdrop-blur-md";
            
            document.getElementById('visualizer-deck').className = "bg-[#070b14] border border-slate-800 rounded-xl p-3 h-28 flex flex-col justify-between transition-all";
            document.getElementById('vis-title').className = "text-slate-500 font-bold uppercase";
            document.getElementById('vis-status').className = "text-slate-600";
            document.getElementById('vis-status').innerText = "STANDBY";

            document.getElementById('dismiss-alarm-btn').classList.add('hidden');
            
            const visCanvas = document.getElementById('visualizer-canvas');
            if (visCanvas) {
                const ctx = visCanvas.getContext('2d');
                ctx.clearRect(0, 0, visCanvas.width, visCanvas.height);
            }
        }

        function startVisualizerDeckLoop() {
            const canvas = document.getElementById('visualizer-canvas');
            if (!canvas) return;
            const ctx = canvas.getContext('2d');

            function renderVisFrame() {
                if (!alarmTriggered) {
                    ctx.clearRect(0, 0, canvas.width, canvas.height);
                    return;
                }
                visAnimId = requestAnimationFrame(renderVisFrame);

                if (canvas.width !== canvas.clientWidth || canvas.height !== canvas.clientHeight) {
                    canvas.width = canvas.clientWidth;
                    canvas.height = canvas.clientHeight;
                }

                ctx.clearRect(0, 0, canvas.width, canvas.height);

                const barsCount = 36;
                const barWidth = (canvas.width / barsCount) - 2;
                let x = 0;

                for (let i = 0; i < barsCount; i++) {
                    const randomFactor = Math.sin(Date.now() * 0.012 + i * 0.6) * 0.5 + 0.5;
                    const barHeight = randomFactor * canvas.height * 0.85 + (Math.random() * 12);

                    const grad = ctx.createLinearGradient(0, canvas.height, 0, canvas.height - barHeight);
                    grad.addColorStop(0, '#ff2200');
                    grad.addColorStop(0.5, '#ff8800');
                    grad.addColorStop(1, '#ffff00');

                    ctx.fillStyle = grad;
                    ctx.fillRect(x, canvas.height - barHeight, barWidth, barHeight);

                    x += barWidth + 2;
                }
            }
            renderVisFrame();
        }

        function initMediaPipe() {
            if (typeof Pose === 'undefined') return;
            
            pose = new Pose({
                locateFile: (file) => `https://cdn.jsdelivr.net/npm/@mediapipe/pose/${file}`
            });

            pose.setOptions({
                modelComplexity: 1,
                smoothLandmarks: true,
                minDetectionConfidence: 0.6,
                minTrackingConfidence: 0.6
            });

            pose.onResults(onPoseResults);
        }

        function onPoseResults(results) {
            if (currentState !== STATE.SCANNING) return;

            frameCount++;
            const now = Date.now();
            if (now - lastFpsUpdate >= 1000) {
                document.getElementById('fps-counter').innerText = Math.min(60, frameCount);
                frameCount = 0;
                lastFpsUpdate = now;
            }

            const canvas = document.getElementById('skeleton-canvas');
            if (!canvas) return;

            if (canvas.width !== canvas.clientWidth || canvas.height !== canvas.clientHeight) {
                canvas.width = canvas.clientWidth;
                canvas.height = canvas.clientHeight;
            }

            const ctx = canvas.getContext('2d');
            const w = canvas.width;
            const h = canvas.height;

            ctx.clearRect(0, 0, w, h);

            if (results.poseLandmarks) {
                const lm = results.poseLandmarks;

                let minX = 1.0, minY = 1.0, maxX = 0.0, maxY = 0.0;
                let validPts = 0;

                lm.forEach(pt => {
                    if ((pt.visibility || 1) > 0.35) {
                        minX = Math.min(minX, pt.x);
                        minY = Math.min(minY, pt.y);
                        maxX = Math.max(maxX, pt.x);
                        maxY = Math.max(maxY, pt.y);
                        validPts++;
                    }
                });

                const ls = lm[11], lh = lm[23];
                let angle = 0.0;
                let isDeadOrFallen = false;

                if (ls && lh) {
                    const dx = (lh.x - ls.x) * w;
                    const dy = (lh.y - ls.y) * h;
                    angle = Math.abs(Math.atan2(dx, dy) * (180 / Math.PI));
                    
                    if (angle > 52.0) {
                        isDeadOrFallen = true;
                    }
                }

                if (validPts > 3) {
                    const padX = 20, padY = 20;
                    const bx = Math.max(0, minX * w - padX);
                    const by = Math.max(0, minY * h - padY);
                    const bw = Math.min(w - bx, (maxX - minX) * w + padX * 2);
                    const bh = Math.min(h - by, (maxY - minY) * h + padY * 2);

                    ctx.strokeStyle = isDeadOrFallen ? '#ff2200' : '#10b981';
                    ctx.lineWidth = 3;
                    ctx.strokeRect(bx, by, bw, bh);

                    ctx.fillStyle = isDeadOrFallen ? '#ff2200' : '#10b981';
                    ctx.font = 'bold 12px JetBrains Mono';
                    ctx.fillText(
                        isDeadOrFallen ? '🔥 TARGET INCAPACITATED [INFERNO TRIGGERED]' : '🎯 TARGET LOCK [UPRIGHT]',
                        bx + 6, by + 16
                    );
                }

                ctx.strokeStyle = isDeadOrFallen ? '#ff5500' : '#38bdf8';
                ctx.lineWidth = 2.5;
                POSE_CONNECTIONS.forEach(([i, j]) => {
                    const p1 = lm[i], p2 = lm[j];
                    if (p1 && p2 && (p1.visibility || 1) > 0.35 && (p2.visibility || 1) > 0.35) {
                        ctx.beginPath();
                        ctx.moveTo(p1.x * w, p1.y * h);
                        ctx.lineTo(p2.x * w, p2.y * h);
                        ctx.stroke();
                    }
                });

                ctx.fillStyle = isDeadOrFallen ? '#ffcc00' : '#34d399';
                lm.forEach(pt => {
                    if ((pt.visibility || 1) > 0.35) {
                        ctx.beginPath();
                        ctx.arc(pt.x * w, pt.y * h, 3.5, 0, 2 * Math.PI);
                        ctx.fill();
                    }
                });

                document.getElementById('m-angle').innerText = `${angle.toFixed(1)}°`;
                const stateGauge = document.getElementById('risk-gauge');
                
                if (isDeadOrFallen) {
                    fallDetectedInSession = true;
                    stateGauge.innerText = "🔥 INCAPACITATED / SLASHER DOWN";
                    stateGauge.className = "text-xl font-black text-rose-500 tracking-wider animate-pulse";
                } else {
                    stateGauge.innerText = "UPRIGHT / SAFE";
                    stateGauge.className = "text-xl font-black text-emerald-400 tracking-wider";
                }

                if (now - lastTelemetryTime > 250) {
                    lastTelemetryTime = now;
                    fetch('/api/telemetry', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ angle: angle, state: isDeadOrFallen ? "FALLEN" : "UPRIGHT" })
                    }).catch(() => {});
                }
            }
        }

        async function processFrame() {
            if (currentState !== STATE.SCANNING) return;

            const videoElement = document.getElementById('webcam-video');
            if (videoElement && videoElement.readyState >= 2 && pose) {
                try {
                    await pose.send({ image: videoElement });
                } catch(e) {}
            }

            if (currentState === STATE.SCANNING) {
                animFrameId = requestAnimationFrame(processFrame);
            }
        }

        async function toggleSystemState() {
            if (currentState === STATE.SCANNING) {
                await stopSystem(true);
            } else if (currentState === STATE.IDLE) {
                await startSystem();
            }
        }

        async function startSystem() {
            currentState = STATE.INITIALIZING;
            document.getElementById('verdict-banner').classList.add('hidden');
            updateUIState();

            if (!pose) initMediaPipe();

            const videoElement = document.getElementById('webcam-video');
            fallDetectedInSession = false;

            try {
                mediaStream = await navigator.mediaDevices.getUserMedia({
                    video: { width: 1280, height: 720, frameRate: { ideal: 60 } },
                    audio: false
                });

                videoElement.srcObject = mediaStream;
                await videoElement.play();
            } catch (err) {
                await stopSystem(false);
                alert("Camera Access Error: " + err.message);
                return;
            }

            currentState = STATE.SCANNING;
            updateUIState();

            animFrameId = requestAnimationFrame(processFrame);

            const durationSetting = parseInt(document.getElementById('scan-mode-select').value);
            if (durationSetting > 0) {
                const startTime = Date.now();
                scanTimer = setInterval(async () => {
                    if (currentState !== STATE.SCANNING) {
                        clearInterval(scanTimer);
                        return;
                    }

                    const elapsed = (Date.now() - startTime) / 1000.0;
                    const timeLeft = Math.max(0.0, durationSetting - elapsed);

                    document.getElementById('timer-bar').style.width = `${((durationSetting - timeLeft) / durationSetting) * 100}%`;
                    document.getElementById('timer-text').innerText = `${timeLeft.toFixed(1)}s`;

                    if (timeLeft <= 0) {
                        await stopSystem(true);
                    }
                }, 100);
            } else {
                document.getElementById('timer-text').innerText = "CONTINUOUS";
                document.getElementById('timer-bar').style.width = "100%";
            }
        }

        async function stopSystem(showVerdict = true) {
            currentState = STATE.STOPPING;

            if (scanTimer) { clearInterval(scanTimer); scanTimer = null; }
            if (animFrameId) { cancelAnimationFrame(animFrameId); animFrameId = null; }

            const videoElement = document.getElementById('webcam-video');
            if (videoElement) { videoElement.pause(); videoElement.srcObject = null; }

            if (mediaStream) {
                mediaStream.getTracks().forEach(track => track.stop());
                mediaStream = null;
            }

            const canvas = document.getElementById('skeleton-canvas');
            if (canvas) {
                const ctx = canvas.getContext('2d');
                ctx.clearRect(0, 0, canvas.width, canvas.height);
            }

            currentState = STATE.IDLE;
            updateUIState();

            if (showVerdict) {
                renderVerdictBanner(fallDetectedInSession);
            }
        }

        function updateUIState() {
            const btn = document.getElementById('action-btn');
            const icon = document.getElementById('btn-icon');
            const label = document.getElementById('btn-label');
            const badge = document.getElementById('system-mode-badge');
            const beacon = document.getElementById('status-beacon');

            if (currentState === STATE.SCANNING) {
                btn.className = "w-full py-4 bg-gradient-to-r from-rose-500 to-amber-500 hover:from-rose-400 hover:to-amber-400 text-slate-950 font-black text-sm rounded-xl transition-all shadow-lg flex items-center justify-center gap-2 cursor-pointer active:scale-95";
                icon.innerText = "🛑";
                label.innerText = "STOP SCANNING";
                badge.innerText = "ACTIVE 60FPS";
                badge.className = "px-3 py-1.5 rounded-lg font-bold tracking-wider bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 animate-pulse";
                beacon.className = "w-3.5 h-3.5 rounded-full bg-emerald-400 animate-ping";
            } else {
                btn.className = "w-full py-4 bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-400 hover:to-teal-400 text-slate-950 font-black text-sm rounded-xl transition-all shadow-lg flex items-center justify-center gap-2 cursor-pointer active:scale-95";
                icon.innerText = "🚀";
                label.innerText = "ACTIVATE POSE GUARD";
                badge.innerText = "IDLE";
                badge.className = "px-3 py-1.5 rounded-lg font-bold tracking-wider bg-slate-800 text-slate-400 border border-slate-700";
                beacon.className = "w-3.5 h-3.5 rounded-full bg-slate-500";
                document.getElementById('timer-bar').style.width = "0%";
                document.getElementById('timer-text').innerText = "--";
                document.getElementById('fps-counter').innerText = "60";
            }
        }

        function renderVerdictBanner(isFallen) {
            const banner = document.getElementById('verdict-banner');
            banner.classList.remove('hidden');

            if (isFallen) {
                banner.className = "p-4 rounded-xl border text-center font-black text-sm bg-rose-500/10 text-rose-400 border-rose-500/30 flex items-center justify-center gap-2 animate-pulse";
                banner.innerHTML = "🔥 <span>CRITICAL ALERT: Target Down! Triggering Forsaken Inferno Alarm & Audio Engine.</span>";
                triggerInfernoAlarm();
            } else {
                banner.className = "p-4 rounded-xl border text-center font-black text-sm bg-emerald-500/10 text-emerald-400 border-emerald-500/30 flex items-center justify-center gap-2";
                banner.innerHTML = "✅ <span>VERDICT: Subject Upright & Active. System Standby.</span>";
            }
        }

        function openTestSuite() { document.getElementById('test-modal').classList.remove('hidden'); }
        function closeTestSuite() { document.getElementById('test-modal').classList.add('hidden'); }

        async function runAssetTest(assetKey) {
            const banner = document.getElementById('test-telemetry-banner');
            banner.innerText = "Running analysis on test asset...";

            const res = await fetch(`/api/analyze_asset?key=${assetKey}`);
            const data = await res.json();

            document.getElementById('test-output-img').src = "data:image/jpeg;base64," + data.image;

            const isFallen = data.telemetry.state === "FALLEN" || data.telemetry.status === "FALL_DETECTED";
            banner.innerHTML = `
                STATE: <b class="${isFallen ? 'text-rose-400' : 'text-emerald-400'}">${isFallen ? 'INCAPACITATED / SLASHER DOWN' : 'UPRIGHT'}</b> | 
                PITCH: <b>${data.telemetry.torso_angle}°</b> | 
                RISK: <b>${data.telemetry.risk_level}</b>
            `;

            if (isFallen) {
                triggerInfernoAlarm();
            }
        }
    </script>
</body>
</html>
"""

@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory(os.getcwd(), filename)

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/data')
def get_data():
    return jsonify(latest_telemetry)

@app.route('/api/reset', methods=['POST'])
def reset_data():
    global latest_telemetry
    latest_telemetry = DEFAULT_TELEMETRY.copy()
    return jsonify({"status": "reset"})

@app.route('/api/telemetry', methods=['POST'])
def receive_telemetry():
    global latest_telemetry
    data = request.json or {}
    latest_telemetry.update(data)
    if mqtt_connected:
        try:
            mqtt_client.publish("aegis/telemetry", json.dumps(data), qos=0)
        except Exception:
            pass
    return jsonify({"status": "ok"})

@app.route('/api/analyze_asset')
def analyze_asset():
    key = request.args.get('key', 'fell')
    workspace_assets = getattr(config, 'WORKSPACE_ASSETS', {
        "fell": {"file": "oh no,he fell.png"},
        "handsome": {"file": "handsome.png"},
        "leon": {"file": "LEON.png"},
        "cat": {"file": "cute cat.png"}
    })
    
    asset_info = workspace_assets.get(key, workspace_assets.get('fell', {}))
    file_path = asset_info.get('file', 'oh no,he fell.png')

    if os.path.exists(file_path):
        img = cv2.imread(file_path)
    else:
        img = np.zeros((480, 640, 3), np.uint8)
        cv2.putText(img, f"Asset Missing: {file_path}", (50, 240), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

    if engine:
        hud_frame, telemetry = engine.render_hud_overlay(img)
    else:
        hud_frame = img
        telemetry = DEFAULT_TELEMETRY.copy()
        if key == 'fell':
            telemetry['state'] = 'FALLEN'
            telemetry['status'] = 'FALL_DETECTED'
            telemetry['torso_angle'] = 78.4

    _, encoded_img = cv2.imencode('.jpg', hud_frame)

    return jsonify({
        "image": base64.b64encode(encoded_img).decode('utf-8'),
        "telemetry": telemetry
    })

if __name__ == '__main__':
    host = getattr(config, 'WEB_UI_HOST', '0.0.0.0')
    port = getattr(config, 'WEB_UI_PORT', 4000)
    print(f"🔥 Aegis 60FPS Inferno UI running at http://{host}:{port}")
    app.run(host=host, port=port, debug=False, threaded=True)