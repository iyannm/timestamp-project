from datetime import datetime
from . import db

# -----------------------------------------------------------
# EMPLOYEE TABLE
# (now supports MULTIPLE face encodings through relationship)
# -----------------------------------------------------------
class Employee(db.Model):
    __tablename__ = "employee"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)

    # REMOVE this → replaced by EmployeeFace table
    # face_encoding = db.Column(db.LargeBinary, nullable=True)

    status = db.Column(db.String(20), default="clocked out")
    hourly_rate = db.Column(db.Float, default=10.0)

    # Relationship: one employee → many face encodings
    faces = db.relationship(
        "EmployeeFace",
        backref="employee",
        cascade="all, delete-orphan",
        lazy=True
    )

    # (Optional but useful)
    attendances = db.relationship("Attendance", backref="employee", lazy=True)


# -----------------------------------------------------------
# NEW TABLE: MULTIPLE FACE ENCODINGS PER EMPLOYEE
# -----------------------------------------------------------
class EmployeeFace(db.Model):
    __tablename__ = "employee_face"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employee.id"), nullable=False)

    # Base64-pickled encoding is stored as TEXT because it's safest
    face_encoding = db.Column(db.Text, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# -----------------------------------------------------------
# ATTENDANCE LOGS
# -----------------------------------------------------------
class Attendance(db.Model):
    __tablename__ = "attendance"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employee.id"))
    status = db.Column(db.String(20))  # clocked in / out
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
