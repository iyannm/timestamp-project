import cv2
import face_recognition
import pickle
import base64
import numpy as np
import os
import time
from .models import Employee, EmployeeFace

class FaceRecognizer:
    def __init__(self, camera_index=0, tolerance=0.45, min_process_time=2.5):
        self.camera_index = camera_index
        self.tolerance = tolerance
        self.min_process_time = min_process_time
        self.known_encodings = []
        self.known_employees = []
        self.encodings_loaded = False
        self.cap = None

    # ----------------------
    # Camera control
    # ----------------------
    def start(self):
        if self.cap is None or not self.cap.isOpened():
            self.cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
            if not self.cap.isOpened():
                print("[FaceRecognizer] Failed to open camera")
            else:
                print("[FaceRecognizer] Camera started")

    def release(self):
        if self.cap is not None and self.cap.isOpened():
            self.cap.release()
            print("[FaceRecognizer] Camera released")
        self.cap = None

    # ----------------------
    # Load encodings
    # ----------------------
    def load_encodings(self):
        if self.encodings_loaded:
            return
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
                    print(f"[FaceRecognizer] Failed to decode {emp.name}: {e}")

        self.encodings_loaded = True
        print(f"[FaceRecognizer] Loaded {len(self.known_encodings)} encodings")

    # ----------------------
    # Capture frame
    # ----------------------
    def capture_frame(self):
        if self.cap is None or not self.cap.isOpened():
            return None
        ret, frame = self.cap.read()
        return frame if ret else None

    # ----------------------
    # Identity verification
    # ----------------------
    def verify_identity(self, frame):
        rgb = frame[:, :, ::-1]
        locs = face_recognition.face_locations(rgb)
        encs = face_recognition.face_encodings(rgb, locs)
        if not encs:
            return None, None, None

        captured_encoding = encs[0]
        detected_loc = locs[0]

        employee = None
        if self.known_encodings:
            distances = face_recognition.face_distance(self.known_encodings, captured_encoding)
            min_idx = np.argmin(distances)
            if distances[min_idx] < self.tolerance:
                employee = self.known_employees[min_idx]

        return employee, detected_loc, locs

    # ----------------------
    # Recognition pipeline
    # ----------------------
    def recognize(self):
        self.load_encodings()
        start_time = time.time()
        employee = None
        detected_loc = None
        first_frame = None

        while time.time() - start_time < self.min_process_time:
            frame = self.capture_frame()
            if frame is None:
                continue

            if first_frame is None:
                first_frame = frame.copy()  # save first frame

            if employee is None:
                emp, loc, locs = self.verify_identity(frame)
                if emp:
                    employee = emp
                    detected_loc = loc

        # Draw rectangle on the first_frame if face detected
        if detected_loc and first_frame is not None:
            top, right, bottom, left = detected_loc
            cv2.rectangle(first_frame, (left, top), (right, bottom), (0, 255, 0), 3)

        return employee, first_frame, detected_loc

# ----------------------
# Clean temporary folder
# ----------------------
def clean_tmp_folder():
    tmp_path = os.path.join("app", "static", "tmp")
    if os.path.exists(tmp_path):
        for f in os.listdir(tmp_path):
            try:
                os.remove(os.path.join(tmp_path, f))
            except:
                pass
