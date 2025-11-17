from datetime import datetime
import pickle
from . import db  # <-- use the one from __init__.py, do NOT redefine it

class Employee(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50))
    face_encoding = db.Column(db.LargeBinary, nullable=True)
    status = db.Column(db.String(20), default="clocked out")
    hourly_rate = db.Column(db.Float, default=10.0)

class Attendance(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employee.id"))
    status = db.Column(db.String(20))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
