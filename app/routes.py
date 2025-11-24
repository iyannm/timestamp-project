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
    print("\n=== /login_face called ===")

    clean_tmp_folder()
    recognizer.start()  # turn camera ON
    # ---------------------------------------
    # RUN FACE RECOGNITION + LIVENESS
    # ---------------------------------------
    employee, frame, face_loc = recognizer.recognize()

    # Prepare tmp folder
    tmp_path = os.path.join("app", "static", "tmp")
    os.makedirs(tmp_path, exist_ok=True)

    preview_filename = None

    # ---------------------------------------
    # SAVE FRAME + DRAW FACE BOX
    # ---------------------------------------
    if frame is not None:
        try:
            preview_filename = f"{uuid.uuid4()}.jpg"
            save_path = os.path.join(tmp_path, preview_filename)
            cv2.imwrite(save_path, frame)

            session["last_capture"] = preview_filename

        except Exception as e:
            print("[ERROR] Failed to save preview frame:", e)

    # ---------------------------------------
    # HANDLE FAILED LOGIN
    # ---------------------------------------
    if employee is None:
        print("❌ Face recognition FAILED or liveness check failed")
        session.pop("employee_id", None)
        return redirect(url_for("main.face_preview"))

    # ---------------------------------------
    # SUCCESS → UPDATE ATTENDANCE
    # ---------------------------------------
    print(f"✔ Recognized employee: {employee.name} (ID={employee.id})")

    # ensure valid starting state
    if not employee.status:
        employee.status = "clocked out"

    previous_status = employee.status
    new_status = "clocked in" if previous_status == "clocked out" else "clocked out"

    employee.status = new_status

    record = Attendance(employee_id=employee.id, status=new_status)
    db.session.add(record)
    db.session.commit()

    session["employee_id"] = employee.id

    print(f"⏱ Attendance toggled: {previous_status} → {new_status}")
    recognizer.release()  # turn camera OFF after recognition
    return redirect(url_for("main.face_preview"))


@main_bp.route("/face_preview")
def face_preview():
    # Get the first captured frame from session
    preview_filename = session.get("last_capture", None)

    # Check if login was successful
    employee_id = session.get("employee_id", None)
    success = employee_id is not None

    return render_template(
        "face_preview.html",
        img=preview_filename,
        success=success
    )


# Employee dashboard
@main_bp.route("/employee_dashboard", methods=["GET", "POST"])
def employee_dashboard():
    employee_id = session.get("employee_id")
    if not employee_id:
        flash("Please log in first")
        return redirect(url_for("main.index"))

    employee = Employee.query.get(employee_id)

    # --- Latest log for status ---
    latest_log = Attendance.query.filter_by(employee_id=employee_id)\
        .order_by(Attendance.id.desc()).first()

    if latest_log and latest_log.status == "clocked in":
        current_status = "Clocked In"
        clock_in_time = latest_log.timestamp
    else:
        current_status = "Clocked Out"
        clock_in_time = None

    expected_clock_out = clock_in_time + timedelta(hours=8) if clock_in_time else None

    # --- Today's hours & earnings ---
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

    # --- Date range calculations ---
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

    # --- Last 7 days for charts ---
    week_labels = []
    week_hours = []
    week_earnings = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        week_labels.append(day.strftime("%a"))
        day_logs = Attendance.query.filter(
            Attendance.employee_id == employee.id,
            db.func.date(Attendance.timestamp) == day
        ).order_by(Attendance.timestamp).all()

        day_seconds = 0
        open_clock_in = None
        for log in day_logs:
            if log.status == "clocked in":
                open_clock_in = log.timestamp
            elif log.status == "clocked out" and open_clock_in:
                day_seconds += (log.timestamp - open_clock_in).total_seconds()
                open_clock_in = None
        if open_clock_in:
            day_seconds += (datetime.now() - open_clock_in).total_seconds()

        hours = round(day_seconds / 3600, 2)
        week_hours.append(hours)
        week_earnings.append(round(hours * employee.hourly_rate, 2))

    # --- Render template ---
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
        end_date=end_date,
        week_labels=week_labels,
        week_hours=week_hours,
        week_earnings=week_earnings
    )



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


# --- Upload Multiple Faces ---
@main_bp.route("/upload_faces_admin", methods=["POST"])
def upload_faces_admin():
    from .models import Employee, EmployeeFace
    import face_recognition, pickle, base64

    if not session.get("admin"):
        flash("Admin login required")
        return redirect(url_for("main.admin_login_page"))

    emp_id = request.form.get("employee_id")
    files = request.files.getlist("face_images")  # support multiple uploads

    employee = Employee.query.get(emp_id)
    if not employee:
        flash("Employee not found")
        return redirect(url_for("main.admin_dashboard"))

    uploaded_count = 0
    for file in files:
        if not file:
            continue

        try:
            # Load image and extract face encodings
            img = face_recognition.load_image_file(file)
            encodings = face_recognition.face_encodings(img)
            if not encodings:
                continue  # skip images with no detectable face

            # Pick the first face (you can loop through all if needed)
            encoding = encodings[0]

            # Serialize encoding and store in EmployeeFace
            raw = pickle.dumps(encoding)
            encoded64 = base64.b64encode(raw).decode("utf-8")

            face_entry = EmployeeFace(employee_id=employee.id, face_encoding=encoded64)
            db.session.add(face_entry)
            uploaded_count += 1

        except Exception as e:
            print(f"[upload_faces_admin] Failed to process file {file.filename}: {e}")
            continue

    if uploaded_count > 0:
        db.session.commit()
        flash(f"Successfully uploaded {uploaded_count} face(s) for {employee.name}")
    else:
        flash("No valid faces were detected in the uploaded images.")

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

    page = int(request.args.get("page", 1))
    per_page = 10

    pagination = Attendance.query.filter_by(employee_id=emp_id)\
        .order_by(Attendance.timestamp.desc())\
        .paginate(page=page, per_page=per_page)

    # Convert SQLAlchemy objects to dicts (FIX)
    records = []
    for r in pagination.items:
        records.append({
            "id": r.id,
            "status": r.status,
            "timestamp": r.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        })

    return render_template(
        "view_attendance.html",
        employee=employee,
        records=records,
        pagination=pagination
    )

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

# --- Edit Employee GET/POST ---
@main_bp.route("/edit_employee/<int:employee_id>", methods=["GET", "POST"])
def edit_employee(employee_id):
    if not session.get("admin"):
        flash("Admin login required")
        return redirect(url_for("main.admin_login_page"))

    employee = Employee.query.get(employee_id)
    if not employee:
        flash("Employee not found")
        return redirect(url_for("main.admin_dashboard"))

    if request.method == "POST":
        # Update employee info
        employee.name = request.form.get("name")
        employee.hourly_rate = float(request.form.get("hourly_rate"))
        db.session.commit()
        flash("Employee updated successfully")
        return redirect(url_for("main.admin_dashboard"))

    # GET request → render edit form
    return render_template("edit_employee.html", employee=employee)




