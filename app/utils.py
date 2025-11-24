import cv2
import face_recognition
import pickle
import base64
import numpy as np
import os
import time

from .models import Employee, EmployeeFace

class FaceRecognizer:
    def __init__(self, camera_index=0, tolerance=0.45, resize_factor=0.75, detection_model="hog"):
        self.camera_index = camera_index
        self.tolerance = tolerance
        self.resize_factor = resize_factor
        self.detection_model = detection_model

        # Memory storage
        self.known_encodings = []
        self.known_employees = []
        self.known_encodings_np = None
        self.encodings_loaded = False

        print(f"[FaceRecognizer] Initialized with camera {camera_index}, tolerance={tolerance}")

    # --------------------------------
    # Load all encodings into RAM
    # --------------------------------
    def load_encodings(self):
        if self.encodings_loaded:
            return

        print("[FaceRecognizer] Loading employee encodings into RAM...")
        try:
            employees = Employee.query.all()
        except Exception as e:
            print("[FaceRecognizer] ERROR: DB not ready:", e)
            return

        self.known_encodings = []
        self.known_employees = []

        for emp in employees:
            for f in emp.faces:
                try:
                    raw = base64.b64decode(f.face_encoding)
                    encoding = pickle.loads(raw)
                    self.known_encodings.append(encoding)
                    self.known_employees.append(emp)
                except Exception as e:
                    print(f"[FaceRecognizer] Failed to decode encoding for {emp.name}:", e)

        if self.known_encodings:
            self.known_encodings_np = np.array(self.known_encodings)

        self.encodings_loaded = True
        print(f"[FaceRecognizer] Loaded {len(self.known_encodings)} total encodings")

    # --------------------------------
    # Capture a single frame
    # --------------------------------
    def capture_frame(self):
        cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
        if not cap.isOpened():
            return None
        ret, frame = cap.read()
        cap.release()
        if not ret:
            return None
        return frame

    # --------------------------------
    # Simple blink/liveness check
    # --------------------------------
    def is_blinking(self, frame):
        try:
            landmarks = face_recognition.face_landmarks(frame)
            if not landmarks:
                return False

            left = landmarks[0]["left_eye"]
            right = landmarks[0]["right_eye"]

            def ear(eye):
                A = np.linalg.norm(np.array(eye[1]) - np.array(eye[5]))
                B = np.linalg.norm(np.array(eye[2]) - np.array(eye[4]))
                C = np.linalg.norm(np.array(eye[0]) - np.array(eye[3]))
                return (A + B) / (2.0 * C)

            EAR = (ear(left) + ear(right)) / 2
            return EAR < 0.19

        except Exception:
            return False

    # --------------------------------
    # Multi-frame verification
    # --------------------------------
    def verify_identity(self, required_frames=3, min_matches=2):
        matches = 0
        detected_loc = None
        final_emp = None
        samples = 0

        while samples < required_frames:
            frame = self.capture_frame()
            if frame is None:
                samples += 1
                continue

            resized = cv2.resize(frame, (0, 0), fx=self.resize_factor, fy=self.resize_factor)
            rgb = resized[:, :, ::-1]

            locs = face_recognition.face_locations(rgb, model=self.detection_model)
            encs = face_recognition.face_encodings(rgb, locs)

            if not encs:
                samples += 1
                continue

            captured_encoding = encs[0]
            detected_loc = locs[0]

            # Vectorized distance check
            distances = face_recognition.face_distance(self.known_encodings_np, captured_encoding)
            best_idx = np.argmin(distances)
            best_dist = distances[best_idx]

            if best_dist < self.tolerance:
                matches += 1
                final_emp = self.known_employees[best_idx]

            samples += 1
            time.sleep(0.05)

        if matches >= min_matches:
            return final_emp, detected_loc

        return None, detected_loc

    # --------------------------------
    # Main recognition pipeline
    # --------------------------------
    def recognize(self):
        self.load_encodings()

        # Blink/liveness check (optional, minimal frames)
        print("[FaceRecognizer] Checking for blink/liveness...")
        blinked = False
        for _ in range(2):
            frame = self.capture_frame()
            if frame is None:
                continue
            rgb = frame[:, :, ::-1]
            if self.is_blinking(rgb):
                blinked = True
                print("[FaceRecognizer] Blink detected")
                break
            time.sleep(0.05)

        if not blinked:
            print("[FaceRecognizer] Liveness failed: No blink detected")
            return None, None, None

        # Identity verification
        print("[FaceRecognizer] Running identity matching...")
        emp, loc = self.verify_identity()

        final_frame = self.capture_frame()
        return emp, final_frame, loc

# --------------------------------
# Clean temporary folder
# --------------------------------
def clean_tmp_folder():
    tmp_path = os.path.join("app", "static", "tmp")
    if not os.path.exists(tmp_path):
        return
    for f in os.listdir(tmp_path):
        try:
            os.remove(os.path.join(tmp_path, f))
        except:
            pass
