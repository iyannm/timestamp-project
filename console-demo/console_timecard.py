import random
from datetime import datetime, timedelta

# -----------------------------
# Pre-filled Data Structures
# -----------------------------

# Employees
employees = {
    "E001": {"name": "Alice", "status": "clocked out", "rate": 15},
    "E002": {"name": "Bob", "status": "clocked out", "rate": 20},
    "E003": {"name": "Charlie", "status": "clocked out", "rate": 18},
    "E004": {"name": "Diana", "status": "clocked out", "rate": 22}
}

# Attendance logs with simulated timestamps (last 3 days)
attendance = {
    "E001": [
        {"status": "clocked in", "time": datetime.now() - timedelta(days=3, hours=8)},
        {"status": "clocked out", "time": datetime.now() - timedelta(days=3, hours=0)},
        {"status": "clocked in", "time": datetime.now() - timedelta(days=2, hours=9)},
        {"status": "clocked out", "time": datetime.now() - timedelta(days=2, hours=1)},
    ],
    "E002": [
        {"status": "clocked in", "time": datetime.now() - timedelta(days=3, hours=7, minutes=30)},
        {"status": "clocked out", "time": datetime.now() - timedelta(days=3, hours=-0, minutes=-30)},
        {"status": "clocked in", "time": datetime.now() - timedelta(days=1, hours=10)},
        {"status": "clocked out", "time": datetime.now() - timedelta(days=1, hours=2)},
    ],
    "E003": [
        {"status": "clocked in", "time": datetime.now() - timedelta(days=2, hours=8)},
        {"status": "clocked out", "time": datetime.now() - timedelta(days=2, hours=0)},
    ],
    "E004": [
        {"status": "clocked in", "time": datetime.now() - timedelta(days=3, hours=9)},
        {"status": "clocked out", "time": datetime.now() - timedelta(days=3, hours=1)},
    ]
}


# -----------------------------
# Core Functions
# -----------------------------
def generate_code():
    """Generate random 4-digit code."""
    return str(random.randint(1000, 9999))


def clock_in(employee_id, code_entered, current_code):
    """Handles clock in/out toggling."""
    if employee_id not in employees:
        print("Invalid employee ID!\n")
        return
    if code_entered != current_code:
        print("Incorrect code!\n")
        return

    emp = employees[employee_id]
    timestamp = datetime.now()

    # Toggle status
    if emp["status"] == "clocked out":
        emp["status"] = "clocked in"
    else:
        emp["status"] = "clocked out"

    attendance[employee_id].append({"status": emp["status"], "time": timestamp})
    print(f"{emp['name']} is now {emp['status']} at {timestamp}\n")


def calculate_hours(employee_id, start_date=None, end_date=None):
    """Calculate worked hours within date range."""
    records = attendance.get(employee_id, [])
    total_seconds = 0
    in_time = None

    for entry in records:
        time = entry["time"]
        if start_date and time < start_date:
            continue
        if end_date and time > end_date:
            continue
        if entry["status"] == "clocked in":
            in_time = time
        elif entry["status"] == "clocked out" and in_time:
            total_seconds += (time - in_time).total_seconds()
            in_time = None

    return total_seconds / 3600


def calculate_salary(employee_id, start_date=None, end_date=None):
    """Calculate salary within date range."""
    hours = calculate_hours(employee_id, start_date, end_date)
    rate = employees[employee_id]["rate"]
    return hours * rate


def display_summary(employee_id, start_date=None, end_date=None):
    """Display hours and salary for employee."""
    hours = calculate_hours(employee_id, start_date, end_date)
    salary = calculate_salary(employee_id, start_date, end_date)
    emp_name = employees[employee_id]['name']
    print(f"\nSummary for {emp_name}:")
    print(f"Hours worked: {hours:.2f}")
    print(f"Total salary: ${salary:.2f}\n")


# -----------------------------
# Admin Functions
# -----------------------------
def add_employee():
    emp_id = input("Enter new employee ID: ").strip()
    if emp_id in employees:
        print("Employee ID already exists!\n")
        return
    name = input("Enter employee name: ")
    rate = float(input("Enter hourly rate: "))
    employees[emp_id] = {"name": name, "status": "clocked out", "rate": rate}
    attendance[emp_id] = []
    print(f"Added employee {name} ({emp_id}) with rate ${rate}/hr\n")


def delete_employee():
    emp_id = input("Enter employee ID to delete: ").strip()
    if emp_id in employees:
        del employees[emp_id]
        attendance.pop(emp_id, None)
        print(f"Employee {emp_id} deleted.\n")
    else:
        print("Invalid employee ID!\n")


def view_employee_logs():
    emp_id = input("Enter employee ID to view logs: ").strip()
    if emp_id not in employees:
        print("Invalid employee ID!\n")
        return

    print(f"\nAttendance records for {employees[emp_id]['name']}:")
    for entry in attendance[emp_id]:
        print(f"{entry['time']} - {entry['status']}")
    print()


def view_total_salary_by_range():
    print("\nEnter date range (YYYY-MM-DD)")
    start_str = input("Start date: ")
    end_str = input("End date: ")
    try:
        start_date = datetime.strptime(start_str, "%Y-%m-%d")
        end_date = datetime.strptime(end_str, "%Y-%m-%d") + timedelta(days=1)
    except ValueError:
        print("Invalid date format!\n")
        return

    print("\nTotal salary by employee:")
    for emp_id, data in employees.items():
        salary = calculate_salary(emp_id, start_date, end_date)
        print(f"{data['name']}: ${salary:.2f}")
    print()


def update_hourly_rate():
    emp_id = input("Enter employee ID to update rate: ").strip()
    if emp_id not in employees:
        print("Invalid employee ID!\n")
        return
    new_rate = float(input("Enter new hourly rate: "))
    employees[emp_id]['rate'] = new_rate
    print(f"Updated {employees[emp_id]['name']}'s rate to ${new_rate}/hr\n")


# -----------------------------
# Menus
# -----------------------------
def employee_menu(current_code):
    while True:
        print("\n--- EMPLOYEE MENU ---")
        print("1. Clock In/Out")
        print("2. View Hours/Salary")
        print("3. Back to Main Menu")
        choice = input("Select option: ")

        if choice == "1":
            emp_id = input("Enter Employee ID: ")
            code = input("Enter random code: ")
            clock_in(emp_id, code, current_code)
        elif choice == "2":
            emp_id = input("Enter Employee ID: ")
            if emp_id in employees:
                display_summary(emp_id)
            else:
                print("Invalid Employee ID!\n")
        elif choice == "3":
            break
        else:
            print("Invalid choice.\n")


def admin_menu():
    while True:
        print("\n--- ADMIN MENU ---")
        print("1. Add Employee")
        print("2. Delete Employee")
        print("3. View Employee Logs")
        print("4. View Total Salary by Date Range")
        print("5. Update Hourly Rate")
        print("6. Back to Main Menu")
        choice = input("Select option: ")

        if choice == "1":
            add_employee()
        elif choice == "2":
            delete_employee()
        elif choice == "3":
            view_employee_logs()
        elif choice == "4":
            view_total_salary_by_range()
        elif choice == "5":
            update_hourly_rate()
        elif choice == "6":
            break
        else:
            print("Invalid choice.\n")


# -----------------------------
# Main Program
# -----------------------------
if __name__ == "__main__":
    current_code = generate_code()
    print(f"Current random code: {current_code}\n")

    while True:
        print("=== TIME CARD SYSTEM ===")
        print("1. Employee Mode")
        print("2. Admin Mode")
        print("3. Generate New Code")
        print("4. Exit")
        choice = input("Select option: ")

        if choice == "1":
            employee_menu(current_code)
        elif choice == "2":
            admin_menu()
        elif choice == "3":
            current_code = generate_code()
            print(f"New random code: {current_code}\n")
        elif choice == "4":
            print("Exiting...")
            break
        else:
            print("Invalid option.\n")
