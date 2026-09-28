import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
import math
import time
import os
from ultralytics import YOLO
import configuration as config

class AegisCyberEngine:
    def __init__(self):
        print("⚡ [AEGIS V6 CORE] Booting Dual-Vision Tactical Engine...")
        
        # 1. Primary Joint Skeleton Engine: YOLOv8-Pose
        print("📦 Loading YOLOv8-Pose Primary Skeleton Engine...")
        self.yolo_model = YOLO('yolov8n-pose.pt')
        
        # 2. Target Lock ROI Bounding Engine: MediaPipe Tasks API
        print("🎯 Initializing MediaPipe Target Bounding Engine (Tasks API)...")
        self.mp_enabled = False
        task_path = 'pose_landmarker.task'
        
        if os.path.exists(task_path):
            try:
                base_options = python.BaseOptions(model_asset_path=task_path)
                options = vision.PoseLandmarkerOptions(
                    base_options=base_options,
                    running_mode=vision.RunningMode.IMAGE
                )
                self.landmarker = vision.PoseLandmarker.create_from_options(options)
                self.mp_enabled = True
                print("✅ MediaPipe PoseLandmarker Task loaded successfully!")
            except Exception as e:
                print(f"⚠️ MediaPipe Task Init Warning: {e}")
        else:
            print(f"⚠️ '{task_path}' missing from root directory. Will derive target boxes from YOLO.")

    def _calc_angle(self, p1, p2):
        """Calculates vertical pitch angle relative to gravity axis."""
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        return math.degrees(math.atan2(abs(dx), abs(dy) + 1e-6))

    def _draw_cyber_brackets(self, img, pt1, pt2, color, thickness=2, r=15):
        """Renders futuristic tactical corner brackets around target ROI."""
        x1, y1 = int(pt1[0]), int(pt1[1])
        x2, y2 = int(pt2[0]), int(pt2[1])

        # Top-Left Corner
        cv2.line(img, (x1, y1), (x1 + r, y1), color, thickness)
        cv2.line(img, (x1, y1), (x1, y1 + r), color, thickness)
        # Top-Right Corner
        cv2.line(img, (x2, y1), (x2 - r, y1), color, thickness)
        cv2.line(img, (x2, y1), (x2, y1 + r), color, thickness)
        # Bottom-Left Corner
        cv2.line(img, (x1, y2), (x1 + r, y2), color, thickness)
        cv2.line(img, (x1, y2), (x1, y2 - r), color, thickness)
        # Bottom-Right Corner
        cv2.line(img, (x2, y2), (x2 - r, y2), color, thickness)
        cv2.line(img, (x2, y2), (x2, y2 - r), color, thickness)

    def render_hud_overlay(self, frame):
        """
        Processes frame through Dual-Engine pipeline:
        - MediaPipe Tasks API: Generates target ROI bounding boxes using pose_landmarker.task.
        - YOLOv8-Pose: Constructs skeletal joint keypoints and computes fall dynamics.
        - Cyber HUD: Overlay live status ('FALLEN' vs 'AWAKE') directly onto video feed.
        """
        h, w, _ = frame.shape
        hud_frame = frame.copy()

        state = "AWAKE"
        risk_level = "NOMINAL"
        torso_angle = 0.0
        confidence = 0.0
        target_detected = False
        bbox = None

        # --- PHASE 1: MediaPipe Tasks Target Bounding Box ---
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        if self.mp_enabled:
            try:
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
                detection_result = self.landmarker.detect(mp_image)
                
                if detection_result.pose_landmarks and len(detection_result.pose_landmarks) > 0:
                    lms = detection_result.pose_landmarks[0]
                    xs = [lm.x * w for lm in lms if lm.visibility > 0.3]
                    ys = [lm.y * h for lm in lms if lm.visibility > 0.3]

                    if xs and ys:
                        pad = 20
                        x1, y1 = max(0, int(min(xs)) - pad), max(0, int(min(ys)) - pad)
                        x2, y2 = min(w, int(max(xs)) + pad), min(h, int(max(ys)) + pad)
                        bbox = (x1, y1, x2, y2)
                        target_detected = True
            except Exception as e:
                pass

        # --- PHASE 2: YOLOv8 Pose Joints Engine ---
        yolo_res = self.yolo_model(frame, verbose=False)[0]

        if len(yolo_res.keypoints) > 0:
            kpts = yolo_res.keypoints.data[0].cpu().numpy()
            
            # Fallback Bounding Box from YOLO if MediaPipe missed
            if bbox is None and len(yolo_res.boxes) > 0:
                b = yolo_res.boxes.xyxy[0].cpu().numpy()
                bbox = (int(b[0]), int(b[1]), int(b[2]), int(b[3]))
                target_detected = True

            # COCO Keypoints: 5=L_Shoulder, 6=R_Shoulder, 11=L_Hip, 12=R_Hip
            if len(kpts) >= 13:
                l_s, r_s = kpts[5], kpts[6]
                l_h, r_h = kpts[11], kpts[12]

                if l_s[2] > 0.3 and r_s[2] > 0.3 and l_h[2] > 0.3 and r_h[2] > 0.3:
                    mid_s = ((l_s[0] + r_s[0]) / 2, (l_s[1] + r_s[1]) / 2)
                    mid_h = ((l_h[0] + r_h[0]) / 2, (l_h[1] + r_h[1]) / 2)
                    
                    torso_angle = self._calc_angle(mid_s, mid_h)
                    confidence = float((l_s[2] + r_s[2] + l_h[2] + r_h[2]) / 4.0)

                    bbox_h = (bbox[3] - bbox[1]) if bbox else (mid_h[1] - mid_s[1])
                    bbox_w = (bbox[2] - bbox[0]) if bbox else 100
                    aspect_ratio = bbox_w / max(1.0, bbox_h)

                    if torso_angle > config.FALL_TORSO_ANGLE_THRESHOLD or aspect_ratio > config.FALL_ASPECT_RATIO_THRESHOLD:
                        state = "FALLEN"
                        risk_level = "CRITICAL"
                    else:
                        state = "AWAKE"
                        risk_level = "NOMINAL"

            # Draw Cyber Skeleton Joints
            SKELETON_CONNECTIONS = [
                (5,6), (5,7), (7,9), (6,8), (8,10),        # Arms
                (5,11), (6,12), (11,12),                  # Torso
                (11,13), (13,15), (12,14), (14,16)        # Legs
            ]

            line_color = (0, 71, 255) if state == "FALLEN" else (154, 255, 0)
            joint_color = (0, 0, 255) if state == "FALLEN" else (0, 255, 180)

            for kp1, kp2 in SKELETON_CONNECTIONS:
                if kpts[kp1][2] > 0.3 and kpts[kp2][2] > 0.3:
                    pt1 = (int(kpts[kp1][0]), int(kpts[kp1][1]))
                    pt2 = (int(kpts[kp2][0]), int(kpts[kp2][1]))
                    cv2.line(hud_frame, pt1, pt2, line_color, 2, cv2.LINE_AA)

            for kp in kpts:
                if kp[2] > 0.3:
                    pt = (int(kp[0]), int(kp[1]))
                    cv2.circle(hud_frame, pt, 4, joint_color, -1, cv2.LINE_AA)
                    cv2.circle(hud_frame, pt, 7, line_color, 1, cv2.LINE_AA)

        # --- PHASE 3: Render Tactical HUD Overlays ---
        status_color = (0, 0, 255) if state == "FALLEN" else (0, 255, 154)

        # 1. Target Lock Box
        if bbox:
            self._draw_cyber_brackets(hud_frame, (bbox[0], bbox[1]), (bbox[2], bbox[3]), status_color, 2, 20)
            tag = "MP::TARGET_LOCK" if self.mp_enabled else "YOLO::TARGET_LOCK"
            cv2.putText(hud_frame, tag, (bbox[0], max(20, bbox[1] - 8)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.4, status_color, 1, cv2.LINE_AA)

        # 2. In-Camera HUD Banner Box
        cv2.rectangle(hud_frame, (10, 10), (280, 85), (10, 14, 23), -1)
        cv2.rectangle(hud_frame, (10, 10), (280, 85), status_color, 1)

        cv2.putText(hud_frame, f"STATE: [{state}]", (20, 35),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.65, status_color, 2, cv2.LINE_AA)
        
        cv2.putText(hud_frame, f"PITCH: {torso_angle:.1f}deg | RISK: {risk_level}", (20, 58),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.38, (200, 220, 240), 1, cv2.LINE_AA)

        cv2.putText(hud_frame, "YOLOv8-Pose + MediaPipe Tasks", (20, 75),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.32, (120, 150, 180), 1, cv2.LINE_AA)

        telemetry = {
            "state": state,
            "risk_level": risk_level,
            "torso_angle": round(torso_angle, 1),
            "confidence": round(confidence * 100, 1),
            "target_detected": target_detected
        }

        return hud_frame, telemetry

if __name__ == "__main__":
    engine = AegisCyberEngine()
    print("🚀 Aegis Tactical Engine Online.")