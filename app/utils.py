import cv2
import face_recognition
import pickle
import base64
import numpy as np
import os
import time

from .models import Employee, EmployeeFace


class FaceRecognizer:
    def __init__(self, camera_index=0, tolerance=0.45):
        self.camera_index = camera_index
        self.tolerance = tolerance

        # Memory storage (multiple encodings)
        self.known_encodings = []      # list of numpy arrays
        self.known_employees = []      # list of Employee objects
        self.encodings_loaded = False  # safe lazy DB loading

        print(f"[FaceRecognizer] Initialized with camera {camera_index}, tolerance={tolerance}")

    # ----------------------------------------------------------------------
    # LOAD MULTIPLE FACE ENCODINGS PER EMPLOYEE
    # ----------------------------------------------------------------------
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
            # Load all face images for this employee
            for f in emp.faces:   # Employee.faces relationship
                try:
                    raw = base64.b64decode(f.face_encoding)
                    encoding = pickle.loads(raw)

                    self.known_encodings.append(encoding)
                    self.known_employees.append(emp)

                except Exception as e:
                    print(f"[FaceRecognizer] Failed to decode encoding for {emp.name}:", e)

        self.encodings_loaded = True
        print(f"[FaceRecognizer] Loaded {len(self.known_encodings)} total encodings")

    # ----------------------------------------------------------------------
    # CAPTURE FRAME
    # ----------------------------------------------------------------------
    def capture_frame(self):
        cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
        if not cap.isOpened():
            return None
        ret, frame = cap.read()
        cap.release()
        if not ret or frame is None:
            return None
        return frame

    # ----------------------------------------------------------------------
    # BLINK / LIVENESS CHECK
    # ----------------------------------------------------------------------
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

    # ----------------------------------------------------------------------
    # MULTI-FRAME VERIFICATION
    # ----------------------------------------------------------------------
    def verify_identity(self, required_frames=5, min_matches=3):
        matches = 0
        detected_loc = None
        final_emp = None
        samples = 0

        while samples < required_frames:
            frame = self.capture_frame()
            if frame is None:
                samples += 1
                continue

            resized = cv2.resize(frame, (0, 0), fx=0.75, fy=0.75)
            rgb = resized[:, :, ::-1]

            locs = face_recognition.face_locations(rgb)
            encs = face_recognition.face_encodings(rgb, locs)

            if not encs:
                samples += 1
                continue

            captured_encoding = encs[0]
            detected_loc = locs[0]

            best_match = None
            best_dist = 999

            # Compare against ALL saved face encodings
            for known_enc, emp in zip(self.known_encodings, self.known_employees):
                dist = face_recognition.face_distance([known_enc], captured_encoding)[0]
                if dist < best_dist:
                    best_dist = dist
                    best_match = emp

            if best_dist < self.tolerance:
                matches += 1
                final_emp = best_match

            samples += 1
            time.sleep(0.15)

        if matches >= min_matches:
            return final_emp, detected_loc

        return None, detected_loc

    # ----------------------------------------------------------------------
    # MAIN RECOGNITION PIPELINE
    # ----------------------------------------------------------------------
    def recognize(self):
        # Safe lazy load NOW (inside request context)
        self.load_encodings()

        # 1. Liveness: Blink detection
        print("[FaceRecognizer] Checking for blink...")
        blinked = False

        for _ in range(10):
            frame = self.capture_frame()
            if frame is None:
                continue

            rgb = frame[:, :, ::-1]

            if self.is_blinking(rgb):
                blinked = True
                print("[FaceRecognizer] Blink detected")
                break

            time.sleep(0.1)

        if not blinked:
            print("[FaceRecognizer] Liveness failed: No blink detected")
            return None, None, None

        # 2. Identity verification
        print("[FaceRecognizer] Running identity matching...")
        emp, loc = self.verify_identity()

        final_frame = self.capture_frame()
        return emp, final_frame, loc

# ----------------------------------------------------------------------
# CLEAN TMP FOLDER
# ----------------------------------------------------------------------
def clean_tmp_folder():
    tmp_path = os.path.join("app", "static", "tmp")
    if not os.path.exists(tmp_path):
        return

    for f in os.listdir(tmp_path):
        try:
            os.remove(os.path.join(tmp_path, f))
        except:
            pass
