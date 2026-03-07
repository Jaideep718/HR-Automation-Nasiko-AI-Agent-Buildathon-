from langchain_core.tools import tool
from supabase import create_client
from dotenv import load_dotenv
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

# Load environment variables from .env file
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Supabase credentials not found in environment variables")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")

TOTAL_WORKING_DAYS = 22


# ------------------------------------------------
# HELPERS
# ------------------------------------------------

def send_email(to_email: str, subject: str, message: str) -> bool:
    """
    Send email notification to employee.
    Returns True/False so callers know if email succeeded.
    """
    try:
        msg = MIMEMultipart()
        msg["From"] = EMAIL_USER
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(message, "plain"))

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASS)
        server.sendmail(EMAIL_USER, to_email, msg.as_string())
        server.quit()
        return True

    except Exception as e:
        print(f"Email sending failed: {e}")
        return False


def fetch_pending_requests() -> list:
    """
    Shared helper — returns pending leave requests in stable order (oldest first).
    Both view and approve/reject-by-number use this so numbering is always consistent.
    """
    response = (
        supabase.table("leave_requests")
        .select("id, days, employee_email, employees(name, email), created_at")
        .eq("status", "pending")
        .order("created_at", desc=False)
        .execute()
    )
    return response.data or []


def format_duplicate_employees(matches: list) -> str:
    """
    Format duplicate-named employees into a numbered list for HR disambiguation.
    Uses email as the unique identifier since it is the primary key.
    """
    result = ""
    for i, e in enumerate(matches, start=1):
        result += (
            f"  {i}. Email: {e['email']}"
            f" | Working Days: {e.get('working_days', 'N/A')}"
            f" | Absent Days: {e.get('absent_days', 'N/A')}\n"
        )
    result += "\nPlease reply with the employee's email to proceed."
    return result


def lookup_employees_by_name(name: str) -> list:
    """Case-insensitive employee lookup by name. Returns all matches."""
    response = (
        supabase.table("employees")
        .select("name, email, working_days, absent_days")
        .ilike("name", name.strip())
        .execute()
    )
    return response.data or []


def lookup_employee_by_email(email: str) -> dict | None:
    """Fetch a single employee record by email (primary key). Returns None if not found."""
    response = (
        supabase.table("employees")
        .select("name, email, working_days, absent_days")
        .eq("email", email.strip().lower())
        .execute()
    )
    return response.data[0] if response.data else None


# ------------------------------------------------
# VIEW LEAVE REQUESTS
# ------------------------------------------------

@tool
def view_leave_requests() -> str:
    """
    Show all pending leave requests including employee name and email.
    Requests are numbered in stable order (oldest first) so that
    approve/reject by number works reliably.
    """
    requests = fetch_pending_requests()

    if not requests:
        return "No pending leave requests."

    result = "Pending Leave Requests:\n"
    for i, r in enumerate(requests, start=1):
        name = r["employees"]["name"]
        days = r["days"]
        email = r["employee_email"]
        result += f"  {i}. {name.title()} ({email}) – {days} day(s)\n"

    return result


# ------------------------------------------------
# APPROVE LEAVE BY NAME
# ------------------------------------------------

@tool
def approve_leave(employee: str) -> str:
    """
    Approve a pending leave request by employee name.
    If multiple employees share the same name, HR will be shown
    the numbered pending list and asked to pick a request number.
    """
    employee = employee.lower()

    response = (
        supabase.table("leave_requests")
        .select("id, days, employee_email, employees(name, email)")
        .eq("status", "pending")
        .execute()
    )

    matches = [
        r for r in response.data
        if r["employees"]["name"].lower() == employee
    ]

    if not matches:
        return f"No pending leave request found for '{employee.title()}'."

    if len(matches) == 1:
        r = matches[0]
        leave_id = r["id"]
        email = r["employee_email"]
        name = r["employees"]["name"]
        days = r["days"]

        supabase.table("leave_requests") \
            .update({"status": "approved"}) \
            .eq("id", leave_id) \
            .execute()

        message = f"""Hello {name.title()},

Your leave request has been APPROVED.

Leave Days: {days}
Decision Date: {datetime.now().strftime("%Y-%m-%d")}

Regards,
HR Department"""

        sent = send_email(email, "Leave Request Approved", message)
        note = "" if sent else " (Note: email notification could not be sent)"
        return f"Leave approved for {name.title()}.{note}"

    result = f"Multiple employees named '{employee.title()}' have pending leave requests:\n"
    for i, r in enumerate(matches, start=1):
        result += f"  {i}. {r['employees']['name'].title()} ({r['employee_email']}) – {r['days']} day(s)\n"
    result += "\nPlease run 'view leave requests' to see the full numbered list, then specify the request number to approve."
    return result


# ------------------------------------------------
# APPROVE BY NUMBER
# ------------------------------------------------

@tool
def approve_leave_by_number(number: int) -> str:
    """
    Approve a leave request using the numbered list shown by view_leave_requests.
    Example: 'approve request 2'.
    """
    requests = fetch_pending_requests()

    if not requests:
        return "No pending leave requests found."

    if number < 1 or number > len(requests):
        return f"Invalid request number. Please choose between 1 and {len(requests)}."

    r = requests[number - 1]
    leave_id = r["id"]
    name = r["employees"]["name"]
    email = r["employee_email"]
    days = r["days"]

    supabase.table("leave_requests") \
        .update({"status": "approved"}) \
        .eq("id", leave_id) \
        .execute()

    message = f"""Hello {name.title()},

Your leave request has been APPROVED.

Leave Days: {days}
Decision Date: {datetime.now().strftime("%Y-%m-%d")}

Regards,
HR Department"""

    sent = send_email(email, "Leave Request Approved", message)
    note = "" if sent else " (Note: email notification could not be sent)"
    return f"Leave approved for {name.title()}.{note}"


# ------------------------------------------------
# REJECT LEAVE BY NAME
# ------------------------------------------------

@tool
def reject_leave(employee: str, reason: str = "Not specified") -> str:
    """
    Reject a pending leave request by employee name.
    If multiple employees share the same name, HR will be asked
    to select the request number.
    """
    employee = employee.lower()

    response = (
        supabase.table("leave_requests")
        .select("id, days, employee_email, employees(name, email)")
        .eq("status", "pending")
        .execute()
    )

    matches = [
        r for r in response.data
        if r["employees"]["name"].lower() == employee
    ]

    if not matches:
        return f"No pending leave request found for '{employee.title()}'."

    if len(matches) == 1:
        r = matches[0]
        leave_id = r["id"]
        email = r["employee_email"]
        name = r["employees"]["name"]
        days = r["days"]

        supabase.table("leave_requests") \
            .update({"status": "rejected"}) \
            .eq("id", leave_id) \
            .execute()

        message = f"""Hello {name.title()},

Your leave request has been REJECTED.

Leave Days: {days}
Reason: {reason}
Decision Date: {datetime.now().strftime("%Y-%m-%d")}

Regards,
HR Department"""

        sent = send_email(email, "Leave Request Rejected", message)
        note = "" if sent else " (Note: email notification could not be sent)"
        return f"Leave rejected for {name.title()}.{note}"

    result = f"Multiple employees named '{employee.title()}' have pending leave requests:\n"
    for i, r in enumerate(matches, start=1):
        result += f"  {i}. {r['employees']['name'].title()} ({r['employee_email']}) – {r['days']} day(s)\n"
    result += "\nPlease run 'view leave requests' to see the full numbered list, then specify the request number to reject."
    return result


# ------------------------------------------------
# REJECT BY NUMBER
# ------------------------------------------------

@tool
def reject_leave_by_number(number: int, reason: str = "Not specified") -> str:
    """
    Reject a leave request using the numbered list shown by view_leave_requests.
    Example: 'reject request 1 because project deadline'.
    """
    requests = fetch_pending_requests()

    if not requests:
        return "No pending leave requests found."

    if number < 1 or number > len(requests):
        return f"Invalid request number. Please choose between 1 and {len(requests)}."

    r = requests[number - 1]
    leave_id = r["id"]
    name = r["employees"]["name"]
    email = r["employee_email"]
    days = r["days"]

    supabase.table("leave_requests") \
        .update({"status": "rejected"}) \
        .eq("id", leave_id) \
        .execute()

    message = f"""Hello {name.title()},

Your leave request has been REJECTED.

Leave Days: {days}
Reason: {reason}
Decision Date: {datetime.now().strftime("%Y-%m-%d")}

Regards,
HR Department"""

    sent = send_email(email, "Leave Request Rejected", message)
    note = "" if sent else " (Note: email notification could not be sent)"
    return f"Leave rejected for {name.title()}.{note}"


# ------------------------------------------------
# TRACK WORKING DAYS — BY NAME
# ------------------------------------------------

@tool
def track_working_days(employee: str) -> str:
    """
    Get the number of working days recorded for an employee by name.
    If multiple employees share the same name, a disambiguation list
    is shown with their emails. HR can then use track_working_days_by_email.
    """
    matches = lookup_employees_by_name(employee)

    if not matches:
        return f"Employee '{employee.title()}' not found."

    if len(matches) > 1:
        result = f"Multiple employees named '{employee.title()}' found:\n"
        result += format_duplicate_employees(matches)
        return result

    e = matches[0]
    return (
        f"{e['name'].title()} ({e['email']}) has worked {e['working_days']} day(s) "
        f"out of {TOTAL_WORKING_DAYS} this month."
    )


# ------------------------------------------------
# TRACK WORKING DAYS — BY EMAIL  (duplicate-name fallback)
# ------------------------------------------------

@tool
def track_working_days_by_email(employee_email: str) -> str:
    """
    Get working days for a specific employee using their email (primary key).
    Use this after track_working_days returns multiple employees with the same name.
    Example: 'check working days for rishi@company.com'
    """
    e = lookup_employee_by_email(employee_email)

    if not e:
        return f"No employee found with email '{employee_email}'."

    return (
        f"{e['name'].title()} ({e['email']}) has worked {e['working_days']} day(s) "
        f"out of {TOTAL_WORKING_DAYS} this month."
    )


# ------------------------------------------------
# MONITOR ABSENTEEISM — BY NAME
# ------------------------------------------------

@tool
def monitor_absenteeism(employee: str) -> str:
    """
    Check how many days an employee has been absent, looked up by name.
    If multiple employees share the same name, a disambiguation list
    is shown with their emails. HR can then use monitor_absenteeism_by_email.
    """
    matches = lookup_employees_by_name(employee)

    if not matches:
        return f"Employee '{employee.title()}' not found."

    if len(matches) > 1:
        result = f"Multiple employees named '{employee.title()}' found:\n"
        result += format_duplicate_employees(matches)
        return result

    e = matches[0]
    rate = (e["working_days"] / TOTAL_WORKING_DAYS) * 100 if TOTAL_WORKING_DAYS > 0 else 0.0

    return (
        f"{e['name'].title()} ({e['email']}) has been absent {e['absent_days']} day(s) "
        f"this month (Attendance rate: {rate:.1f}%)."
    )


# ------------------------------------------------
# MONITOR ABSENTEEISM — BY EMAIL  (duplicate-name fallback)
# ------------------------------------------------

@tool
def monitor_absenteeism_by_email(employee_email: str) -> str:
    """
    Check absence days for a specific employee using their email (primary key).
    Use this after monitor_absenteeism returns multiple employees with the same name.
    Example: 'check absences for rishi.k@company.com'
    """
    e = lookup_employee_by_email(employee_email)

    if not e:
        return f"No employee found with email '{employee_email}'."

    rate = (e["working_days"] / TOTAL_WORKING_DAYS) * 100 if TOTAL_WORKING_DAYS > 0 else 0.0

    return (
        f"{e['name'].title()} ({e['email']}) has been absent {e['absent_days']} day(s) "
        f"this month (Attendance rate: {rate:.1f}%)."
    )


# ------------------------------------------------
# REPORTS
# ------------------------------------------------

@tool
def get_attendance_report() -> str:
    """Generate a full attendance report for all employees."""
    employees = supabase.table("employees") \
        .select("name, email, working_days, absent_days") \
        .execute().data

    if not employees:
        return "No employee records found."

    report = "Attendance Report:\n"
    report += f"{'Employee':<22} {'Email':<30} {'Working Days':>13} {'Absent Days':>12} {'Attendance %':>13}\n"
    report += "-" * 95 + "\n"

    for e in employees:
        rate = (e["working_days"] / TOTAL_WORKING_DAYS) * 100 if TOTAL_WORKING_DAYS > 0 else 0.0
        report += (
            f"{e['name'].title():<22} {e['email']:<30} {e['working_days']:>13} "
            f"{e['absent_days']:>12} {rate:>12.1f}%\n"
        )

    return report


@tool
def detect_absenteeism() -> str:
    """Detect employees with poor attendance (absent > 3 days or attendance rate < 80%)."""
    employees = supabase.table("employees") \
        .select("name, email, working_days, absent_days") \
        .execute().data

    if not employees:
        return "No employee records found."

    alerts = []
    for e in employees:
        rate = (e["working_days"] / TOTAL_WORKING_DAYS) * 100 if TOTAL_WORKING_DAYS > 0 else 0.0
        if e["absent_days"] > 3 or rate < 80:
            alerts.append(
                f"  ⚠  {e['name'].title()} ({e['email']}) "
                f"→ Absent: {e['absent_days']} day(s) | Attendance: {rate:.1f}%"
            )

    if not alerts:
        return "✅ No absenteeism alerts. All employees have good attendance."

    return "Absenteeism Alerts:\n" + "\n".join(alerts)


@tool
def hr_summary() -> str:
    """
    Generate HR dashboard summary including workforce stats,
    leave request counts, and absenteeism overview.
    """
    employees = supabase.table("employees") \
        .select("name, email, working_days, absent_days") \
        .execute().data

    all_leaves = supabase.table("leave_requests").select("status").execute().data

    pending  = sum(1 for l in all_leaves if l["status"] == "pending")
    approved = sum(1 for l in all_leaves if l["status"] == "approved")
    rejected = sum(1 for l in all_leaves if l["status"] == "rejected")

    flagged = []
    total_absent = 0
    for e in employees:
        total_absent += e.get("absent_days", 0)
        rate = (e["working_days"] / TOTAL_WORKING_DAYS) * 100 if TOTAL_WORKING_DAYS > 0 else 0.0
        if e.get("absent_days", 0) > 3 or rate < 80:
            flagged.append(f"{e['name'].title()} ({e['email']})")

    avg_absent = (total_absent / len(employees)) if employees else 0

    summary = f"""
╔══════════════════════════════════╗
       HR DASHBOARD SUMMARY
╚══════════════════════════════════╝

👥 Workforce
   Total Employees     : {len(employees)}

📋 Leave Requests
   Pending             : {pending}
   Approved            : {approved}
   Rejected            : {rejected}
   Total               : {len(all_leaves)}

📊 Attendance  (this month, out of {TOTAL_WORKING_DAYS} working days)
   Avg Absent Days     : {avg_absent:.1f}
   Employees Flagged   : {len(flagged)}
"""

    if flagged:
        summary += "   Flagged             :\n"
        for f in flagged:
            summary += f"     • {f}\n"
    else:
        summary += "   Flagged Employees  : None ✅\n"

    summary += f"\n   Generated At       : {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"

    return summary