from flask import Blueprint, render_template, redirect, url_for, flash, request, session, Response
from . import db
from .models import Employee, Attendance
from .utils import FaceRecognizer, clean_tmp_folder

from datetime import datetime, timedelta, date
import face_recognition
import pickle
import cv2
import numpy as np
import uuid, cv2, os


main_bp = Blueprint("main", __name__)
recognizer = FaceRecognizer()  # single instance

# Login page
@main_bp.route("/")
def index():
    return render_template("login.html")
# Snapshot login with face recognition

@main_bp.route("/login_face", methods=["POST"])
def login_face():
    print("=== /login_face called ===")

    clean_tmp_folder()

    employee, frame, face_loc = recognizer.recognize()

    # Create tmp folder if missing
    tmp_path = os.path.join("app","static", "tmp")
    os.makedirs(tmp_path, exist_ok=True)

    # Save frame preview
    preview_filename = None

    if frame is not None:
        # Draw face rectangle if detected
        if face_loc:
            top, right, bottom, left = face_loc
            top *= 2; right *= 2; bottom *= 2; left *= 2
            cv2.rectangle(frame, (left, top), (right, bottom), (0,255,0), 3)

        preview_filename = f"{uuid.uuid4()}.jpg"
        file_path = os.path.join(tmp_path, preview_filename)
        cv2.imwrite(file_path, frame)

        session["last_capture"] = preview_filename

    # If no employee recognized → go to preview page
    if not employee:
        print("Face not recognized!")
        session.pop("employee_id", None)
        return redirect(url_for("main.face_preview"))

    # Toggle attendance state
    if not employee.status:
        employee.status = "clocked out"

    previous = employee.status
    employee.status = "clocked in" if employee.status == "clocked out" else "clocked out"

    record = Attendance(employee_id=employee.id, status=employee.status)
    db.session.add(record)
    db.session.commit()

    session["employee_id"] = employee.id

    return redirect(url_for("main.face_preview"))


@main_bp.route("/face_preview")
def face_preview():
    img = session.get("last_capture")
    success = "employee_id" in session
    return render_template("face_preview.html", img=img, success=success)
# Employee dashboard
@main_bp.route("/employee_dashboard", methods=["GET", "POST"])
def employee_dashboard():
    employee_id = session.get("employee_id")
    if not employee_id:
        flash("Please log in first")
        return redirect(url_for("main.index"))

    employee = Employee.query.get(employee_id)

    # Latest log
    latest_log = Attendance.query.filter_by(employee_id=employee_id)\
        .order_by(Attendance.id.desc()).first()

    if latest_log and latest_log.status == "clocked in":
        current_status = "Clocked In"
        clock_in_time = latest_log.timestamp
    else:
        current_status = "Clocked Out"
        clock_in_time = None

    expected_clock_out = clock_in_time + timedelta(hours=8) if clock_in_time else None

    # Today's hours
    today = date.today()
    today_logs = Attendance.query.filter(
        Attendance.employee_id == employee_id,
        db.func.date(Attendance.timestamp) == today
    ).order_by(Attendance.timestamp).all()

    today_seconds = 0
    open_clock_in = None

    for log in today_logs:
        if log.status == "clocked in":
            open_clock_in = log.timestamp
        elif log.status == "clocked out" and open_clock_in:
            today_seconds += (log.timestamp - open_clock_in).total_seconds()
            open_clock_in = None

    if open_clock_in:
        today_seconds += (datetime.now() - open_clock_in).total_seconds()

    hours_today = round(today_seconds / 3600, 2)
    earnings_today = round(hours_today * employee.hourly_rate, 2)

    # Date range calculations
    total_hours = 0
    salary = 0
    start_date = end_date = None

    if request.method == "POST":
        start_date_str = request.form.get("start_date")
        end_date_str = request.form.get("end_date")
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d")

        records = Attendance.query.filter(
            Attendance.employee_id == employee.id,
            Attendance.timestamp >= start_date,
            Attendance.timestamp <= end_date
        ).order_by(Attendance.timestamp).all()

        clock_in_dt = None
        for r in records:
            if r.status == "clocked in":
                clock_in_dt = r.timestamp
            elif r.status == "clocked out" and clock_in_dt:
                total_hours += (r.timestamp - clock_in_dt).total_seconds() / 3600
                clock_in_dt = None

        salary = total_hours * employee.hourly_rate

    return render_template(
        "employee_dashboard.html",
        employee=employee,
        current_status=current_status,
        clock_in_time=clock_in_time,
        expected_clock_out=expected_clock_out,
        hours_today=hours_today,
        earnings_today=earnings_today,
        total_hours=round(total_hours, 2),
        salary=round(salary, 2),
        start_date=start_date,
        end_date=end_date
    )

# --- Upload Face Temporary---
@main_bp.route("/upload_face", methods=["GET", "POST"])
def upload_face():
    if request.method == "POST":
        employee_id = request.form.get("employee_id")
        file = request.files.get("face_image")

        if not file:
            flash("No file uploaded")
            return redirect(request.url)

        # Read the image
        image = face_recognition.load_image_file(file)
        encodings = face_recognition.face_encodings(image)

        if not encodings:
            flash("No face detected in the image.")
            return redirect(request.url)

        face_encoding = encodings[0]
        employee = Employee.query.get(employee_id)
        if not employee:
            flash("Employee not found.")
            return redirect(request.url)

        # Store the encoding in database
        employee.face_encoding = pickle.dumps(face_encoding)
        db.session.commit()
        flash("Face uploaded successfully!")
        return redirect(url_for("main.upload_face"))

    employees = Employee.query.all()
    return render_template("upload_face.html", employees=employees)

# --- Admin Login Page ---
@main_bp.route("/admin_login_page")
def admin_login_page():
    return render_template("admin_login.html")


# --- Admin Login ---
@main_bp.route("/admin_login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        if username == "admin" and password == "admin":
            session["admin"] = True
            flash("Admin logged in successfully")
            return redirect(url_for("main.admin_dashboard"))
        else:
            flash("Invalid admin credentials")
            return redirect(url_for("main.admin_login_page"))
    else:
        # Redirect GET requests to login page
        return redirect(url_for("main.admin_login_page"))


# --- Admin Logout ---
@main_bp.route("/admin_logout")
def admin_logout():
    session.pop("admin", None)
    flash("Admin logged out")
    return redirect(url_for("main.admin_login_page"))


# --- Admin Dashboard ---
@main_bp.route("/admin_dashboard")
def admin_dashboard():
    if not session.get("admin"):
        flash("Admin login required")
        return redirect(url_for("main.admin_login_page"))
    return render_template("admin_dashboard.html")


# --- Add Employee ---
@main_bp.route("/add_employee", methods=["POST"])
def add_employee():
    if not session.get("admin"):
        flash("Admin login required")
        return redirect(url_for("main.admin_login_page"))

    name = request.form.get("name")
    rate = float(request.form.get("hourly_rate"))
    new_emp = Employee(name=name, hourly_rate=rate)
    db.session.add(new_emp)
    db.session.commit()
    flash("Employee added successfully")
    return redirect(url_for("main.admin_dashboard"))


# --- Delete Employee ---
@main_bp.route("/delete_employee", methods=["POST"])
def delete_employee():
    if not session.get("admin"):
        flash("Admin login required")
        return redirect(url_for("main.admin_login_page"))

    emp_id = request.form.get("employee_id")
    employee = Employee.query.get(emp_id)

    if employee:
        db.session.delete(employee)
        db.session.commit()
        flash(f"Employee {employee.name} deleted")
    else:
        flash("Employee not found")

    return redirect(url_for("main.admin_dashboard"))


# --- Upload Face ---
@main_bp.route("/upload_face_admin", methods=["POST"])
def upload_face_admin():
    if not session.get("admin"):
        flash("Admin login required")
        return redirect(url_for("main.admin_login_page"))

    emp_id = request.form.get("employee_id")
    file = request.files.get("face_image")

    employee = Employee.query.get(emp_id)
    if not employee:
        flash("Employee not found")
        return redirect(url_for("main.admin_dashboard"))

    try:
        img = face_recognition.load_image_file(file)
        encodings = face_recognition.face_encodings(img)
        if len(encodings) == 0:
            flash("No face detected in image.")
            return redirect(url_for("main.admin_dashboard"))

        # Save first encoding (can be changed to store multiple)
        employee.face_encoding = pickle.dumps(encodings[0])
        db.session.commit()
        flash("Face image uploaded successfully")
    except Exception as e:
        flash(f"Error processing image: {e}")

    return redirect(url_for("main.admin_dashboard"))


# --- View Attendance ---
@main_bp.route("/view_attendance")
def view_attendance():
    if not session.get("admin"):
        flash("Admin login required")
        return redirect(url_for("main.admin_login_page"))

    emp_id = request.args.get("employee_id")
    employee = Employee.query.get(emp_id)
    if not employee:
        flash("Employee not found")
        return redirect(url_for("main.admin_dashboard"))

    records = Attendance.query.filter_by(employee_id=emp_id).order_by(Attendance.timestamp).all()
    return render_template("view_attendance.html", employee=employee, records=records)


# --- Salary Report ---
@main_bp.route("/salary_report", methods=["POST"])
def salary_report():
    if not session.get("admin"):
        flash("Admin login required")
        return redirect(url_for("main.admin_login_page"))

    try:
        start = datetime.strptime(request.form.get("start_date"), "%Y-%m-%d")
        end = datetime.strptime(request.form.get("end_date"), "%Y-%m-%d")
    except Exception:
        flash("Invalid date format")
        return redirect(url_for("main.admin_dashboard"))

    employees = Employee.query.all()
    report = []

    for e in employees:
        records = Attendance.query.filter(
            Attendance.employee_id == e.id,
            Attendance.timestamp >= start,
            Attendance.timestamp <= end
        ).order_by(Attendance.timestamp).all()

        total_hours = 0
        clock_in_time = None

        for r in records:
            if r.status == "clocked in":
                clock_in_time = r.timestamp
            elif r.status == "clocked out" and clock_in_time:
                total_hours += (r.timestamp - clock_in_time).total_seconds() / 3600
                clock_in_time = None

        report.append({
            "name": e.name,
            "hours": round(total_hours, 2),
            "salary": round(total_hours * e.hourly_rate, 2)
        })

    return render_template("salary_report.html", report=report)





