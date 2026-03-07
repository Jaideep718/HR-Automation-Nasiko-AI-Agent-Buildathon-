"""
Tools for the Employee Onboarding Agent.
Handles employee profile creation, document tracking,
orientation scheduling, communications, and HR notifications.
"""
from datetime import datetime
from typing import Dict, Any
from langchain_core.tools import tool

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import BatchHttpRequest

SCOPES = ["https://www.googleapis.com/auth/calendar"]
# ---------------------------------------------------------------------------
# SMTP Email Configuration
# ---------------------------------------------------------------------------
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
EMAIL_ADDRESS = os.getenv("SMTP_EMAIL")
EMAIL_PASSWORD = os.getenv("SMTP_PASSWORD")
UPLOAD_BASE_URL = os.getenv("UPLOAD_BASE_URL", "http://localhost:5000/onboarding/upload")
HR_EMAIL = os.getenv("HR_EMAIL", "hr@company.com")
TIMEZONE = os.getenv("TIMEZONE", "Asia/Kolkata")
COMPANY_NAME = os.getenv("COMPANY_NAME", "the company")

def send_email_smtp(to_email: str, subject: str, body: str):
    """
    Send an email using SMTP.
    """

    msg = MIMEMultipart()
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = to_email
    msg["Subject"] = subject

    msg.attach(MIMEText(body, "html"))

    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
    except Exception as e:
        raise Exception(f"SMTP email sending failed: {str(e)}")
# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
VALID_DOCS = {
    "id_proof": "Government ID Proof",
    "bank_details": "Bank Account Details",
    "offer_letter": "Signed Offer Letter",
    "background": "Academic/Previous Job Docs",
}

# ---------------------------------------------------------------------------
# In-memory data stores (fast cache — synced with DB)
# ---------------------------------------------------------------------------
_employees: Dict[str, Dict[str, Any]] = {}
_documents: Dict[str, Dict[str, str]] = {}
_schedules: Dict[str, list] = {}
_messages: Dict[str, list] = {}

REMINDER_DAYS = int(os.getenv("REMINDER_DAYS", "3"))

# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------
from db import supabase, STORAGE_BUCKET


def _save_employee_to_db(profile: dict):
    supabase.table("employees").upsert({
        "employee_id": profile["employee_id"],
        "name": profile["name"],
        "email": profile["email"],
        "role": profile["role"],
        "department": profile["department"],
        "manager": profile["manager"],
        "start_date": profile["start_date"],
        "location": profile["location"],
        "status": profile.get("status", "pending"),
        "created_at": profile["created_at"],
    }).execute()


def _save_document_to_db(employee_id: str, doc_type: str, status: str):
    supabase.table("documents").upsert({
        "employee_id": employee_id,
        "document_type": doc_type,
        "status": status,
        "updated_at": datetime.now().isoformat(),
    }, on_conflict="employee_id,document_type").execute()


def _save_schedule_to_db(employee_id: str, events: list):
    rows = []
    for e in events:
        rows.append({
            "employee_id": employee_id,
            "event": e["event"],
            "time": e["time"],
            "end_time": e.get("end", ""),
            "duration": e["duration"],
            "date": e["date"],
        })
    supabase.table("schedules").insert(rows).execute()


def _save_message_to_db(employee_id: str, msg: dict):
    supabase.table("messages").insert({
        "employee_id": employee_id,
        "type": msg["type"],
        "sent_at": msg["sent_at"],
        "to_email": msg.get("to", ""),
        "content": msg.get("content", ""),
        "urgency": msg.get("urgency", ""),
    }).execute()


def _load_from_db():
    """Load all data from Supabase into in-memory caches on startup."""
    # Employees
    result = supabase.table("employees").select("*").execute()
    for emp in result.data:
        _employees[emp["employee_id"]] = {
            "employee_id": emp["employee_id"], "name": emp["name"], "email": emp["email"],
            "role": emp["role"], "department": emp["department"], "manager": emp["manager"],
            "start_date": emp["start_date"], "location": emp["location"], "status": emp["status"],
            "created_at": emp["created_at"],
        }
    # Documents
    result = supabase.table("documents").select("*").execute()
    for doc in result.data:
        _documents.setdefault(doc["employee_id"], {})[doc["document_type"]] = doc["status"]
    # Schedules
    result = supabase.table("schedules").select("*").execute()
    for sch in result.data:
        _schedules.setdefault(sch["employee_id"], []).append({
            "time": sch["time"], "end": sch["end_time"], "event": sch["event"],
            "duration": sch["duration"], "date": sch["date"],
        })
    # Messages
    result = supabase.table("messages").select("*").execute()
    for msg in result.data:
        _messages.setdefault(msg["employee_id"], []).append({
            "type": msg["type"], "sent_at": msg["sent_at"],
            "to": msg["to_email"] or "", "content": msg["content"] or "",
        })


# Load persisted data into memory on import
_load_from_db()


def send_document_reminder(employee_id: str) -> str:
    """Send a reminder email to an employee about pending documents."""
    if employee_id not in _employees:
        return f"Employee {employee_id} not found."

    emp = _employees[employee_id]
    docs = _documents.get(employee_id, {})
    pending = [VALID_DOCS[k] for k, v in docs.items() if v != "uploaded"]

    if not pending:
        return f"No pending documents for {employee_id}."

    days_left = _days_until_start(emp["start_date"])
    upload_link = f"{UPLOAD_BASE_URL}?employee_id={employee_id}"

    subject = f"Reminder: {len(pending)} document(s) still pending - {emp['name']}"
    doc_list = ''.join(f'<li>{d}</li>' for d in pending)
    if days_left <= 7:
        days_display = '<span style="color:red">' + str(days_left) + ' days left</span>'
    else:
        days_display = str(days_left) + ' days left'
    body = (
        f"<p>Hi {emp['name']},</p>"
        f"<p>This is a friendly reminder that the following documents are still pending:</p>"
        f"<ul>{doc_list}</ul>"
        f"<p>Your start date is <b>{emp['start_date']}</b> "
        f"({days_display}).</p>"
        f"<p>Please upload them <a href='{upload_link}' style='color: #1a73e8; font-weight: bold;'>here</a>.</p>"
        f"<p>Best regards,<br><b>HR Team</b></p>"
    )

    send_email_smtp(emp["email"], subject, body)

    _messages[employee_id].append({
        "type": "document_reminder",
        "sent_at": datetime.now().isoformat(),
        "to": emp["email"],
        "pending_docs": pending,
    })
    _save_message_to_db(employee_id, _messages[employee_id][-1])

    return f"Reminder sent to {emp['email']} for {len(pending)} pending document(s)."

def get_calendar_service():

    creds = None
    base_dir = os.path.dirname(os.path.abspath(__file__))
    token_path = os.path.join(base_dir, "token.json")
    creds_path = os.path.join(base_dir, "credentials.json")

    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    if not creds or not creds.valid:

        flow = InstalledAppFlow.from_client_secrets_file(
            creds_path, SCOPES
        )

        creds = flow.run_local_server(port=0)

        with open(token_path, "w") as token:
            token.write(creds.to_json())

    service = build("calendar", "v3", credentials=creds)

    return service

def _validate_date(date_str: str) -> datetime:
    """Validate and parse a YYYY-MM-DD date string."""
    return datetime.strptime(date_str, "%Y-%m-%d")


def _days_until_start(start_date: str) -> int:
    """Return number of days from today until the start date."""
    start = _validate_date(start_date)
    return (start - datetime.now()).days


def _next_employee_id() -> str:
    """Generate the next employee ID — takes max of DB and in-memory to handle batch creation safely."""
    result = supabase.table("employees").select("employee_id").order(
        "employee_id", desc=True
    ).limit(1).execute()
    db_max = int(result.data[0]["employee_id"].split("-")[1]) if result.data else 1000
    mem_max = max((int(eid.split("-")[1]) for eid in _employees), default=1000)
    return f"EMP-{max(db_max, mem_max) + 1}"


# ---------------------------------------------------------------------------
# 1. Create Employee Profile
# ---------------------------------------------------------------------------
@tool
def create_employee_profile(
    name: str,
    email: str,
    role: str,
    department: str,
    manager: str,
    start_date: str,
    location: str,
) -> str:
    """
    Create a new employee profile in the onboarding system when a candidate is hired.

    Args:
        name: Full name of the employee (e.g. "Rahul Sharma")
        email: Email address of the employee
        role: Job title / role (e.g. "Software Engineer")
        department: Department the employee belongs to
        manager: Name of the reporting manager
        start_date: Joining date in YYYY-MM-DD format
        location: Office location (e.g. "Bangalore")
    """
    try:
        try:
            _validate_date(start_date)
        except ValueError:
            return f"Invalid start_date format '{start_date}'. Expected YYYY-MM-DD (e.g. 2026-07-01)."

        employee_id = _next_employee_id()
        profile = {
            "employee_id": employee_id,
            "name": name,
            "email": email,
            "role": role,
            "department": department,
            "manager": manager,
            "start_date": start_date,
            "location": location,
            "status": "pending",
            "created_at": datetime.now().isoformat(),
        }
        _employees[employee_id] = profile

        _documents[employee_id] = {k: "pending" for k in VALID_DOCS}
        _schedules[employee_id] = []
        _messages[employee_id] = []

        # Persist to DB — single batched upsert for all document types
        _save_employee_to_db(profile)
        supabase.table("documents").upsert([
            {"employee_id": employee_id, "document_type": doc_type, "status": "pending"}
            for doc_type in VALID_DOCS
        ]).execute()

        return (
            f"Employee profile created successfully.\n"
            f"Employee ID: {employee_id}\n"
            f"Name: {name}\n"
            f"Role: {role}\n"
            f"Department: {department}\n"
            f"Manager: {manager}\n"
            f"Start Date: {start_date}\n"
            f"Location: {location}\n"
            f"Status: pending"
        )
    except Exception as e:
        return f"Error creating employee profile: {str(e)}"


# ---------------------------------------------------------------------------
# 2. Send Welcome Email
# ---------------------------------------------------------------------------
@tool
def send_welcome_email(employee_id: str) -> str:
    """
    Compose and send a welcome email to the new employee with their first-day schedule.

    Args:
        employee_id: The unique employee ID (e.g. "EMP-1001")
    """
    try:
        if employee_id not in _employees:
            return f"Employee {employee_id} not found."

        emp = _employees[employee_id]
        upload_link = f"{UPLOAD_BASE_URL}?employee_id={employee_id}"
        schedule = _schedules.get(employee_id, [])

        if schedule:
            schedule_text = "\nYour first day schedule:\n"
            for event in schedule:
                schedule_text += f"  {event['time']} - {event['event']}\n"
        else:
            schedule_text = (
                "\nYour first-day schedule will be shared once your orientation is confirmed.\n"
            )
        subject = f"Welcome to the Team, {emp['name']}!"
        body = (
            f"<p>Hi {emp['name']},</p>"
            f"<p>We are excited to have you join us as a <b>{emp['role']}</b> in the "
            f"<b>{emp['department']}</b> team at <b>{emp['location']}</b>!</p>"
            f"<p>Your start date is <b>{emp['start_date']}</b>. "
            f"Your reporting manager will be <b>{emp['manager']}</b>.</p>"
        )
        if schedule:
            body += (
                f"<p><b>Your first day schedule:</b><br>"
                f"{''.join(f'{e["time"]} - {e["event"]}<br>' for e in schedule)}"
                f"</p>"
            )
        else:
            body += "<p><i>Your first-day schedule will be shared once your orientation is confirmed.</i></p>"
        doc_list = ''.join(f'{i+1}. {label}<br>' for i, (_, label) in enumerate(VALID_DOCS.items()))
        body += (
            f"<p>Before your first day, please upload the required documents "
            f"<a href='{upload_link}' style='color: #1a73e8; font-weight: bold;'>here</a>.</p>"
            f"<p><b>Required documents:</b><br>{doc_list}</p>"
            f"<p>If you have any questions, feel free to reach out to HR.</p>"
            f"<p>Best regards,<br><b>HR Team</b></p>"
        )

        send_email_smtp(emp["email"], subject, body)
        _messages[employee_id].append({
            "type": "welcome_email",
            "sent_at": datetime.now().isoformat(),
            "to": emp["email"]
        })
        _save_message_to_db(employee_id, _messages[employee_id][-1])

        return f"Welcome email successfully sent to {emp['email']}."
    except Exception as e:
        return f"Error sending welcome email: {str(e)}"


# ---------------------------------------------------------------------------
# 3. Request Documents
# ---------------------------------------------------------------------------
@tool
def request_documents(employee_id: str) -> str:
    """
    Send a document request to the employee listing all required documents and their current status.

    Args:
        employee_id: The unique employee ID (e.g. "EMP-1001")
    """
    try:
        if employee_id not in _employees:
            return f"Employee {employee_id} not found."

        emp = _employees[employee_id]
        docs = _documents.get(employee_id, {})

        lines = [
            f"Document Request for {emp['name']}",
            "=" * 40,
            "",
            "Please upload the following documents:",
        ]

        pending_count = 0
        for key, label in VALID_DOCS.items():
            status = docs.get(key, "pending")
            icon = "[done]" if status == "uploaded" else "[pending]"
            lines.append(f"  {icon} {label}: {status}")
            if status != "uploaded":
                pending_count += 1

        if pending_count == 0:
            lines.append("\nAll documents have been uploaded!")
        else:
            lines.append(f"\n{pending_count} document(s) still pending.")
            lines.append(f"Please upload before your start date: {emp['start_date']}")

        message = "\n".join(lines)

        _messages[employee_id].append({
            "type": "documents_requested",
            "sent_at": datetime.now().isoformat(),
            "to": emp["email"],
            "content": message,
        })
        _save_message_to_db(employee_id, _messages[employee_id][-1])

        return message
    except Exception as e:
        return f"Error requesting documents: {str(e)}"


# ---------------------------------------------------------------------------
# 4. Track Documents
# ---------------------------------------------------------------------------
@tool
def track_documents(employee_id: str) -> str:
    """
    Check and return the current status of all required documents for an employee.

    Args:
        employee_id: The unique employee ID (e.g. "EMP-1001")
    """
    try:
        if employee_id not in _employees:
            return f"Employee {employee_id} not found."

        emp = _employees[employee_id]
        docs = _documents.get(employee_id, {})

        lines = [f"Document Status for {emp['name']} ({employee_id})", "-" * 40]
        pending = []
        for key, label in VALID_DOCS.items():
            status = docs.get(key, "pending")
            icon = "[done]" if status == "uploaded" else "[pending]"
            lines.append(f"  {icon} {label}: {status}")
            if status != "uploaded":
                pending.append(label)

        if pending:
            lines.append(f"\nMissing: {', '.join(pending)}")
        else:
            lines.append("\nAll documents uploaded.")

        return "\n".join(lines)
    except Exception as e:
        return f"Error tracking documents: {str(e)}"


# ---------------------------------------------------------------------------
# 5. Update Document Status
# ---------------------------------------------------------------------------
@tool
def update_document_status(employee_id: str, document_name: str, status: str) -> str:
    """
    Update the upload status of a specific document for an employee.

    Args:
        employee_id: The unique employee ID (e.g. "EMP-1001")
        document_name: Document key - one of: id_proof, bank_details, offer_letter, background
        status: New status - one of: pending, uploaded
    """
    try:
        if employee_id not in _employees:
            return f"Employee {employee_id} not found."

        if document_name not in VALID_DOCS:
            return f"Invalid document name '{document_name}'. Valid options: {', '.join(sorted(VALID_DOCS))}"

        valid_statuses = {"pending", "uploaded"}
        if status not in valid_statuses:
            return f"Invalid status '{status}'. Valid options: {', '.join(sorted(valid_statuses))}"

        _documents[employee_id][document_name] = status
        _save_document_to_db(employee_id, document_name, status)

        return f"Document '{document_name}' for {_employees[employee_id]['name']} updated to '{status}'."
    except Exception as e:
        return f"Error updating document status: {str(e)}"


# ---------------------------------------------------------------------------
# 6. Schedule Orientation
# ---------------------------------------------------------------------------
@tool
def schedule_orientation(employee_id: str) -> str:
    """
    Create and return the first-day orientation schedule for an employee,
    including HR orientation, team introduction, IT setup, and manager meeting.
    """

    try:
        if employee_id not in _employees:
            return f"Employee {employee_id} not found."

        if employee_id in _schedules and _schedules[employee_id]:
            return f"Orientation already scheduled for {_employees[employee_id]['name']}."

        # Only allow scheduling after all documents are uploaded
        docs = _documents.get(employee_id, {})
        pending = [VALID_DOCS[k] for k, v in docs.items() if v != "uploaded"]
        if pending:
            return (f"Cannot schedule orientation yet. {len(pending)} document(s) still pending: "
                    f"{', '.join(pending)}. Orientation will be auto-scheduled once all documents are uploaded.")

        emp = _employees[employee_id]
        start = emp["start_date"]

        # Load orientation events from DB
        result = supabase.table("orientation_templates").select("*").order("sort_order").execute()
        templates = result.data

        schedule = []
        for t in templates:
            event_name = t["event"]
            # Personalize manager meeting
            if "manager" in event_name.lower() and "1:1" in event_name.lower():
                event_name = f"1:1 Meeting with {emp['manager']}"
            schedule.append({
                "time": t["start_time"],
                "end": t["end_time"],
                "event": event_name,
                "duration": t["duration"],
                "date": start,
            })

        _schedules[employee_id] = schedule
        _save_schedule_to_db(employee_id, schedule)

        service = get_calendar_service()
        batch = service.new_batch_http_request()

        for s in schedule:
            start_dt = datetime.strptime(
                f"{s['date']} {s['time']}", "%Y-%m-%d %I:%M %p"
            ).isoformat()
            end_dt = datetime.strptime(
                f"{s['date']} {s['end']}", "%Y-%m-%d %I:%M %p"
            ).isoformat()
            event = {
                "summary": s["event"],
                "location": emp["location"],
                "description": f"Onboarding event for {emp['name']}",
                "start": {"dateTime": start_dt, "timeZone": TIMEZONE},
                "end": {"dateTime": end_dt, "timeZone": TIMEZONE},
                "attendees": [{"email": emp["email"]}, {"email": HR_EMAIL}],
            }
            batch.add(service.events().insert(
                calendarId="primary", body=event, sendUpdates="all"
            ))

        # Single HTTP request for all 4 calendar events
        batch.execute()

        lines = [
            f"Orientation Schedule for {emp['name']}",
            f"Date: {start}",
            "=" * 45,
        ]

        for s in schedule:
            lines.append(f"  {s['time']} - {s['event']} ({s['duration']})")

        lines.append(f"\nAll events scheduled for {start} at {emp['location']} office.")

        _messages[employee_id].append({
            "type": "orientation_confirmed",
            "sent_at": datetime.now().isoformat(),
            "to": emp["email"],
        })
        _save_message_to_db(employee_id, _messages[employee_id][-1])

        return "\n".join(lines)

    except Exception as e:
        return f"Error scheduling orientation: {str(e)}"

# ---------------------------------------------------------------------------
# 7. Notify HR
# ---------------------------------------------------------------------------
@tool
def notify_hr(employee_id: str) -> str:
    """
    Notify HR to create accounts and prepare resources for the new employee.
    Lists pending account creation tasks and detects urgency based on
    days remaining until start date.

    Args:
        employee_id: The unique employee ID (e.g. "EMP-1001")
    """
    try:
        if employee_id not in _employees:
            return f"Employee {employee_id} not found."

        emp = _employees[employee_id]
        docs = _documents.get(employee_id, {})
        pending_docs = [VALID_DOCS[k] for k, v in docs.items() if v != "uploaded"]

        days_left = _days_until_start(emp["start_date"])
        if days_left <= 0:
            urgency = "CRITICAL - Start date has PASSED"
        elif days_left <= 2:
            urgency = f"CRITICAL - Only {days_left} day(s) left"
        elif days_left <= 7:
            urgency = f"URGENT - {days_left} days left"
        else:
            urgency = f"On Track - {days_left} days left"

        lines = [
            "HR NOTIFICATION - Account Creation Request",
            "=" * 50,
            f"Employee: {emp['name']} ({employee_id})",
            f"Role: {emp['role']}",
            f"Department: {emp['department']}",
            f"Manager: {emp['manager']}",
            f"Start Date: {emp['start_date']}",
            f"Time Remaining: {urgency}",
            "",
            "Please complete the following:",
        ]

        # Load HR tasks from DB
        result = supabase.table("hr_tasks").select("*").order("sort_order").execute()
        for t in result.data:
            lines.append(f"  [ ] {t['task']}")

        if pending_docs:
            lines.append(f"\nMissing Documents ({len(pending_docs)}):")
            for d in pending_docs:
                lines.append(f"  - {d}")

        if days_left <= 2:
            lines.append("\nESCALATION: Immediate action required!")
        else:
            lines.append("\nPlease complete before the employee's start date.")

        notification = "\n".join(lines)

        _messages[employee_id].append({
            "type": "hr_notification",
            "sent_at": datetime.now().isoformat(),
            "urgency": urgency,
            "content": notification,
        })
        _save_message_to_db(employee_id, _messages[employee_id][-1])

        return notification
    except Exception as e:
        return f"Error notifying HR: {str(e)}"


# ---------------------------------------------------------------------------
# 8. Get Onboarding Status
# ---------------------------------------------------------------------------
@tool
def get_onboarding_status(employee_id: str) -> str:
    """
    Retrieve a comprehensive onboarding status summary for an employee,
    including profile, document status, orientation schedule, and messages sent.

    Args:
        employee_id: The unique employee ID (e.g. "EMP-1001")
    """
    try:
        if employee_id not in _employees:
            return f"Employee {employee_id} not found."

        emp = _employees[employee_id]
        docs = _documents.get(employee_id, {})
        schedule = _schedules.get(employee_id, [])
        msgs = _messages.get(employee_id, [])

        lines = [
            f"Onboarding Status - {emp['name']} ({employee_id})",
            "=" * 50,
            f"Role: {emp['role']} | Department: {emp['department']}",
            f"Manager: {emp['manager']} | Start Date: {emp['start_date']}",
            f"Location: {emp['location']} | Status: {emp['status']}",
            "",
        ]

        # Update status based on progress
        uploaded = sum(1 for v in docs.values() if v == "uploaded")
        total = len(docs)
        if uploaded == total and schedule:
            emp["status"] = "ready"
            _save_employee_to_db(emp)

        # Documents summary
        lines.append(f"Documents: {uploaded}/{total} uploaded")
        for k, v in docs.items():
            icon = "[done]" if v == "uploaded" else "[pending]"
            lines.append(f"   {icon} {VALID_DOCS.get(k, k)}: {v}")

        # Schedule
        if schedule:
            lines.append(f"\nFirst-Day Schedule ({emp['start_date']}):")
            for s in schedule:
                lines.append(f"   {s['time']} - {s['event']}")
        else:
            lines.append("\nOrientation: Not yet scheduled")

        # Messages sent
        lines.append(f"\nMessages sent: {len(msgs)}")
        for m in msgs:
            lines.append(f"   - {m['type']} at {m['sent_at'][:19]}")

        return "\n".join(lines)
    except Exception as e:
        return f"Error getting onboarding status: {str(e)}"
