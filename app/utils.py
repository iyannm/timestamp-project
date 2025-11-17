import cv2
import face_recognition
import pickle
from .models import Employee
import os


class FaceRecognizer:
    def __init__(self, camera_index=0):
        self.camera_index = camera_index
        print(f"[FaceRecognizer] Initialized with camera index {self.camera_index}")

    def capture_frame(self):
        print("[FaceRecognizer] Capturing frame...")
        cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
        if not cap.isOpened():
            print("[FaceRecognizer] Cannot open webcam")
            return None

        ret, frame = cap.read()
        cap.release()

        if not ret or frame is None:
            print("[FaceRecognizer] Failed to capture frame")
            return None

        print("[FaceRecognizer] Frame captured successfully")
        return frame

    def recognize(self):
        """Return employee (or None), full-size frame, and face location."""
        frame = self.capture_frame()
        if frame is None:
            return None, None, None

        small_frame = cv2.resize(frame, (0, 0), fx=0.5, fy=0.5)
        rgb_frame = small_frame[:, :, ::-1]

        face_locations = face_recognition.face_locations(rgb_frame)
        face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)
        print(f"[FaceRecognizer] Detected {len(face_encodings)} face(s)")

        if not face_encodings:
            return None, frame, None

        captured_encoding = face_encodings[0]
        face_loc = face_locations[0]  # (top, right, bottom, left)

        employees = Employee.query.all()
        for emp in employees:
            if not emp.face_encoding:
                continue

            try:
                known = pickle.loads(emp.face_encoding)
            except:
                continue

            if face_recognition.compare_faces([known], captured_encoding)[0]:
                return emp, frame, face_loc

        return None, frame, face_loc


def clean_tmp_folder():
    tmp_path = os.path.join("app","static", "tmp")
    if not os.path.exists(tmp_path):
        return

    for f in os.listdir(tmp_path):
        file_path = os.path.join(tmp_path, f)
        try:
            if os.path.isfile(file_path):
                os.remove(file_path)
        except:
            pass