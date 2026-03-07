from langchain_core.tools import tool
from supabase import create_client
from dotenv import load_dotenv
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

# ✅ Fix #9: Load environment variables from .env file
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


def send_email(to_email: str, subject: str, message: str) -> bool:
    """
    Send email notification to employee.
    ✅ Fix #8: Returns True/False so callers know if email succeeded.
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
    ✅ Fix #1 & #5: Single shared helper that always returns pending requests
    in a consistent, stable order (ordered by created_at ascending).
    Both view and approve/reject by number use this same function,
    so the numbering shown to HR always matches what the tools act on.
    """
    response = (
        supabase.table("leave_requests")
        .select("id, days, employee_email, employees(name), created_at")
        .eq("status", "pending")
        .order("created_at", desc=False)
        .execute()
    )
    return response.data or []


# ------------------------------------------------
# VIEW LEAVE REQUESTS
# ------------------------------------------------

@tool
def view_leave_requests() -> str:
    """
    Show all pending leave requests including employee name and email.
    Requests are numbered in a stable order (oldest first) so that
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
        result += f"{i}. {name.title()} ({email}) – {days} day(s)\n"

    return result


# ------------------------------------------------
# APPROVE LEAVE BY NAME
# ------------------------------------------------

@tool
def approve_leave(employee: str) -> str:
    """
    Approve a leave request using employee name.
    If multiple employees share the same name, the system will ask HR
    to choose the request number from the pending list.
    """
    employee = employee.lower()

    # ✅ Fix #3: Use ilike for case-insensitive name matching
    response = (
        supabase.table("leave_requests")
        .select("id, days, employee_email, employees(name)")
        .eq("status", "pending")
        .execute()
    )

    matches = [
        r for r in response.data
        if r["employees"]["name"].lower() == employee
    ]

    if not matches:
        return f"No pending leave request for {employee.title()}."

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

    # Multiple matches — ask HR to pick by number
    result = f"Multiple employees named {employee.title()} have pending leave requests:\n"
    for i, r in enumerate(matches, start=1):
        result += f"{i}. {r['employees']['name'].title()} ({r['employee_email']}) – {r['days']} day(s)\n"
    result += "\nPlease view all pending requests with their numbers and specify which request number to approve."
    return result


# ------------------------------------------------
# APPROVE BY NUMBER
# ------------------------------------------------

@tool
def approve_leave_by_number(number: int) -> str:
    """
    Approve a leave request using the numbered request list previously shown.
    Example: 'approve request 2'.
    Numbers match the list shown by view_leave_requests.
    """
    # ✅ Fix #1 & #2: Use the same stable fetch so numbering is consistent;
    # no redundant second DB query — all data is already in the first fetch.
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
    Reject a leave request using employee name.
    If multiple employees share the same name, HR will be asked
    to select the request number.
    """
    employee = employee.lower()

    response = (
        supabase.table("leave_requests")
        .select("id, days, employee_email, employees(name)")
        .eq("status", "pending")
        .execute()
    )

    matches = [
        r for r in response.data
        if r["employees"]["name"].lower() == employee
    ]

    if not matches:
        return f"No pending leave request for {employee.title()}."

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

    result = f"Multiple employees named {employee.title()} have pending leave requests:\n"
    for i, r in enumerate(matches, start=1):
        result += f"{i}. {r['employees']['name'].title()} ({r['employee_email']}) – {r['days']} day(s)\n"
    result += "\nPlease view all pending requests with their numbers and specify which request number to reject."
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
    # ✅ Fix #2 & #6: Single fetch, no redundant second query
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
# ATTENDANCE
# ------------------------------------------------

@tool
def track_working_days(employee: str) -> str:
    """Get the number of working days recorded for an employee."""
    # ✅ Fix #3: Use ilike for case-insensitive name matching
    emp = supabase.table("employees") \
        .select("*") \
        .ilike("name", employee.strip()) \
        .execute()

    if not emp.data:
        return f"Employee '{employee.title()}' not found."

    return f"{emp.data[0]['name'].title()} has worked {emp.data[0]['working_days']} day(s) this month."


@tool
def monitor_absenteeism(employee: str) -> str:
    """Check how many days an employee has been absent."""
    # ✅ Fix #3: Use ilike for case-insensitive name matching
    emp = supabase.table("employees") \
        .select("*") \
        .ilike("name", employee.strip()) \
        .execute()

    if not emp.data:
        return f"Employee '{employee.title()}' not found."

    return f"{emp.data[0]['name'].title()} has been absent {emp.data[0]['absent_days']} day(s) this month."


# ------------------------------------------------
# REPORTS
# ------------------------------------------------

@tool
def get_attendance_report() -> str:
    """Generate a full attendance report for all employees."""
    employees = supabase.table("employees").select("*").execute().data

    if not employees:
        return "No employee records found."

    report = "Attendance Report:\n"
    report += f"{'Employee':<20} {'Working Days':>12} {'Absent Days':>12} {'Attendance %':>13}\n"
    report += "-" * 60 + "\n"

    for e in employees:
        # ✅ Fix #4: Guard against division by zero
        if TOTAL_WORKING_DAYS > 0:
            rate = (e["working_days"] / TOTAL_WORKING_DAYS) * 100
        else:
            rate = 0.0
        report += (
            f"{e['name'].title():<20} {e['working_days']:>12} "
            f"{e['absent_days']:>12} {rate:>12.1f}%\n"
        )

    return report


@tool
def detect_absenteeism() -> str:
    """Detect employees with poor attendance (absent > 3 days or attendance rate < 80%)."""
    employees = supabase.table("employees").select("*").execute().data

    if not employees:
        return "No employee records found."

    alerts = []
    for e in employees:
        # ✅ Fix #4: Guard against division by zero
        if TOTAL_WORKING_DAYS > 0:
            attendance_rate = (e["working_days"] / TOTAL_WORKING_DAYS) * 100
        else:
            attendance_rate = 0.0

        if e["absent_days"] > 3 or attendance_rate < 80:
            alerts.append(
                f"⚠ {e['name'].title()} → Absent: {e['absent_days']} day(s) | "
                f"Attendance: {attendance_rate:.1f}%"
            )

    if not alerts:
        return "✅ No absenteeism alerts. All employees have good attendance."

    return "Absenteeism Alerts:\n" + "\n".join(alerts)


@tool
def hr_summary() -> str:
    """
    Generate HR dashboard summary including employee stats,
    leave request counts, and absenteeism overview.
    ✅ Fix #7: Expanded to be a genuinely useful dashboard.
    """
    employees = supabase.table("employees").select("*").execute().data

    all_leaves = supabase.table("leave_requests").select("status").execute().data
    pending   = sum(1 for l in all_leaves if l["status"] == "pending")
    approved  = sum(1 for l in all_leaves if l["status"] == "approved")
    rejected  = sum(1 for l in all_leaves if l["status"] == "rejected")

    # Absenteeism stats
    flagged = []
    total_absent = 0
    for e in employees:
        total_absent += e.get("absent_days", 0)
        if TOTAL_WORKING_DAYS > 0:
            rate = (e["working_days"] / TOTAL_WORKING_DAYS) * 100
        else:
            rate = 0.0
        if e.get("absent_days", 0) > 3 or rate < 80:
            flagged.append(e["name"].title())

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

📊 Attendance (this month, out of {TOTAL_WORKING_DAYS} working days)
   Avg Absent Days     : {avg_absent:.1f}
   Employees Flagged   : {len(flagged)}
"""

    if flagged:
        summary += "   Flagged Employees  : " + ", ".join(flagged) + "\n"
    else:
        summary += "   Flagged Employees  : None ✅\n"

    summary += f"\n   Generated At       : {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"

    return summary
