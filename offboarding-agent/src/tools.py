"""
Tools for the Employee Offboarding Agent.
Handles resignation processing, notice period calculation, exit interviews,
asset return tracking, access revocation, knowledge transfer, and final settlement.
"""
import os
import uuid
import smtplib
import logging
from datetime import datetime, timedelta
from typing import Dict, Any
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from langchain_core.tools import tool
from db import supabase

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# SMTP Configuration
# ---------------------------------------------------------------------------
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
EMAIL_ADDRESS = os.getenv("SMTP_EMAIL")
EMAIL_PASSWORD = os.getenv("SMTP_PASSWORD")
HR_EMAIL = os.getenv("HR_EMAIL", "hr@company.com")
COMPANY_NAME = os.getenv("COMPANY_NAME", "the company")

# ---------------------------------------------------------------------------
# Notice period defaults (days) per level
# ---------------------------------------------------------------------------
NOTICE_PERIOD_DAYS = {
    "intern": 0,
    "junior": 30,
    "mid": 60,
    "senior": 90,
    "lead": 90,
    "manager": 90,
    "director": 90,
    "vp": 90,
}

# ---------------------------------------------------------------------------
# Assets that must be returned
# ---------------------------------------------------------------------------
REQUIRED_ASSETS = {
    "laptop": "Company Laptop",
    "id_card": "Employee ID Card",
    "access_card": "Office Access Card",
    "parking_pass": "Parking Pass",
    "company_phone": "Company Phone (if issued)",
}

# ---------------------------------------------------------------------------
# In-memory cache (synced with Supabase)
# ---------------------------------------------------------------------------
_offboardings: Dict[str, Dict[str, Any]] = {}
_assets: Dict[str, Dict[str, str]] = {}
_exit_interviews: Dict[str, Dict[str, Any]] = {}
_messages: Dict[str, list] = {}


def _send_email(to_email: str, subject: str, body: str):
    """Send an HTML email via SMTP."""
    if not EMAIL_ADDRESS or not EMAIL_PASSWORD:
        logger.warning("SMTP credentials not configured. Email not sent.")
        return
    msg = MIMEMultipart()
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "html"))
    server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
    server.starttls()
    server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
    server.send_message(msg)
    server.quit()


def _save_offboarding_to_db(record: dict):
    supabase.table("offboardings").upsert(record).execute()


def _save_asset_to_db(offboarding_id: str, asset_type: str, status: str):
    supabase.table("offboarding_assets").upsert({
        "offboarding_id": offboarding_id,
        "asset_type": asset_type,
        "status": status,
        "updated_at": datetime.now().isoformat(),
    }, on_conflict="offboarding_id,asset_type").execute()


def _save_exit_interview_to_db(record: dict):
    supabase.table("exit_interviews").upsert(record).execute()


def _save_message_to_db(offboarding_id: str, msg: dict):
    supabase.table("offboarding_messages").insert({
        "offboarding_id": offboarding_id,
        "type": msg["type"],
        "sent_at": msg["sent_at"],
        "to_email": msg.get("to", ""),
        "content": msg.get("content", ""),
    }).execute()


def _load_from_db():
    """Load all offboarding data from Supabase into memory on startup."""
    try:
        result = supabase.table("offboardings").select("*").execute()
        for rec in result.data:
            _offboardings[rec["offboarding_id"]] = rec

        result = supabase.table("offboarding_assets").select("*").execute()
        for a in result.data:
            _assets.setdefault(a["offboarding_id"], {})[a["asset_type"]] = a["status"]

        result = supabase.table("exit_interviews").select("*").execute()
        for ei in result.data:
            _exit_interviews[ei["offboarding_id"]] = ei

        result = supabase.table("offboarding_messages").select("*").execute()
        for m in result.data:
            _messages.setdefault(m["offboarding_id"], []).append({
                "type": m["type"], "sent_at": m["sent_at"],
                "to": m.get("to_email", ""), "content": m.get("content", ""),
            })
    except Exception as e:
        logger.warning(f"Could not load offboarding data from DB (tables may not exist yet): {e}")


_load_from_db()


def _next_offboarding_id() -> str:
    """Generate the next offboarding ID."""
    result = supabase.table("offboardings").select("offboarding_id").order(
        "offboarding_id", desc=True
    ).limit(1).execute()
    db_max = int(result.data[0]["offboarding_id"].split("-")[1]) if result.data else 100
    mem_max = max((int(oid.split("-")[1]) for oid in _offboardings), default=100)
    return f"OFF-{max(db_max, mem_max) + 1}"


# ---------------------------------------------------------------------------
# 1. Initiate Offboarding
# ---------------------------------------------------------------------------
@tool
def initiate_offboarding(
    employee_name: str,
    employee_email: str,
    employee_id: str,
    role: str,
    department: str,
    manager: str,
    resignation_date: str,
    last_working_date: str,
    reason: str,
    level: str = "mid",
) -> str:
    """
    Start the offboarding process for a departing employee.
    Calculates notice period, sets up asset tracking, and notifies relevant parties.

    Args:
        employee_name: Full name of the departing employee
        employee_email: Email address of the employee
        employee_id: The employee's existing ID (e.g. "EMP-1001")
        role: Current job title
        department: Department the employee belongs to
        manager: Reporting manager's name
        resignation_date: Date resignation was submitted (YYYY-MM-DD)
        last_working_date: Agreed last working date (YYYY-MM-DD)
        reason: Reason for leaving (e.g. "personal", "career growth", "relocation", "other")
        level: Employee level for notice period calculation — one of "intern", "junior", "mid", "senior", "lead", "manager", "director", "vp". Defaults to "mid".
    """
    try:
        resign_dt = datetime.strptime(resignation_date, "%Y-%m-%d")
        lwd_dt = datetime.strptime(last_working_date, "%Y-%m-%d")
    except ValueError:
        return "Invalid date format. Use YYYY-MM-DD for both resignation_date and last_working_date."

    level_key = level.lower().strip()
    required_notice = NOTICE_PERIOD_DAYS.get(level_key, 60)
    actual_notice = (lwd_dt - resign_dt).days
    notice_shortfall = max(0, required_notice - actual_notice)

    offboarding_id = _next_offboarding_id()
    record = {
        "offboarding_id": offboarding_id,
        "employee_id": employee_id,
        "employee_name": employee_name,
        "employee_email": employee_email,
        "role": role,
        "department": department,
        "manager": manager,
        "resignation_date": resignation_date,
        "last_working_date": last_working_date,
        "reason": reason,
        "level": level_key,
        "required_notice_days": required_notice,
        "actual_notice_days": actual_notice,
        "notice_shortfall_days": notice_shortfall,
        "status": "initiated",
        "created_at": datetime.now().isoformat(),
    }

    _offboardings[offboarding_id] = record
    _assets[offboarding_id] = {k: "pending" for k in REQUIRED_ASSETS}
    _messages[offboarding_id] = []

    _save_offboarding_to_db(record)
    for asset_type in REQUIRED_ASSETS:
        _save_asset_to_db(offboarding_id, asset_type, "pending")

    notice_info = f"Required notice: {required_notice} days. Actual: {actual_notice} days."
    if notice_shortfall > 0:
        notice_info += f" SHORTFALL: {notice_shortfall} days — recovery/buyout may apply."

    return (
        f"Offboarding initiated successfully.\n"
        f"Offboarding ID: {offboarding_id}\n"
        f"Employee: {employee_name} ({employee_id})\n"
        f"Role: {role} | Department: {department}\n"
        f"Manager: {manager}\n"
        f"Resignation Date: {resignation_date}\n"
        f"Last Working Date: {last_working_date}\n"
        f"Reason: {reason}\n"
        f"{notice_info}\n"
        f"Status: initiated\n"
        f"Assets to return: {len(REQUIRED_ASSETS)}"
    )


# ---------------------------------------------------------------------------
# 2. Send Exit Email
# ---------------------------------------------------------------------------
@tool
def send_exit_notification(offboarding_id: str) -> str:
    """
    Send an exit notification email to the departing employee with details
    about their offboarding timeline and checklist.

    Args:
        offboarding_id: The offboarding case ID (e.g. "OFF-101")
    """
    if offboarding_id not in _offboardings:
        return f"Offboarding case {offboarding_id} not found."

    rec = _offboardings[offboarding_id]
    assets_list = "".join(
        f"<li>{REQUIRED_ASSETS[k]} — <b>{'Returned' if v == 'returned' else 'Pending'}</b></li>"
        for k, v in _assets.get(offboarding_id, {}).items()
    )
    shortfall_note = ""
    if rec.get("notice_shortfall_days", 0) > 0:
        shortfall_note = (
            f"<p style='color:#e74c3c'><b>Notice Shortfall:</b> {rec['notice_shortfall_days']} days. "
            f"HR will discuss recovery or buyout options with you.</p>"
        )

    subject = f"Offboarding Process — {rec['employee_name']}"
    body = (
        f"<p>Dear {rec['employee_name']},</p>"
        f"<p>We have received your resignation effective <b>{rec['resignation_date']}</b>. "
        f"Your last working date is <b>{rec['last_working_date']}</b>.</p>"
        f"{shortfall_note}"
        f"<p><b>Please ensure the following assets are returned before your last day:</b></p>"
        f"<ul>{assets_list}</ul>"
        f"<p>You will be contacted for an exit interview and knowledge transfer handover.</p>"
        f"<p>For any questions, reach out to HR at {HR_EMAIL}.</p>"
        f"<p>We wish you all the best in your future endeavours.</p>"
        f"<p>Best regards,<br><b>HR Team — {COMPANY_NAME}</b></p>"
    )
    _send_email(rec["employee_email"], subject, body)
    _messages[offboarding_id].append({
        "type": "exit_notification",
        "sent_at": datetime.now().isoformat(),
        "to": rec["employee_email"],
    })
    _save_message_to_db(offboarding_id, _messages[offboarding_id][-1])

    return f"Exit notification email sent to {rec['employee_email']}."


# ---------------------------------------------------------------------------
# 3. Track / Return Assets
# ---------------------------------------------------------------------------
@tool
def track_assets(offboarding_id: str) -> str:
    """
    Check the return status of all company assets for a departing employee.

    Args:
        offboarding_id: The offboarding case ID (e.g. "OFF-101")
    """
    if offboarding_id not in _offboardings:
        return f"Offboarding case {offboarding_id} not found."

    assets = _assets.get(offboarding_id, {})
    lines = [f"Asset Return Status for {_offboardings[offboarding_id]['employee_name']}:", "=" * 50]
    returned = 0
    for key, label in REQUIRED_ASSETS.items():
        status = assets.get(key, "pending")
        icon = "[✓]" if status == "returned" else "[✗]"
        lines.append(f"  {icon} {label}: {status}")
        if status == "returned":
            returned += 1
    lines.append(f"\n{returned}/{len(REQUIRED_ASSETS)} assets returned.")
    return "\n".join(lines)


@tool
def update_asset_status(offboarding_id: str, asset_type: str, status: str = "returned") -> str:
    """
    Mark a company asset as returned or lost.

    Args:
        offboarding_id: The offboarding case ID (e.g. "OFF-101")
        asset_type: Asset to update — one of "laptop", "id_card", "access_card", "parking_pass", "company_phone"
        status: New status — "returned" or "lost". Defaults to "returned".
    """
    if offboarding_id not in _offboardings:
        return f"Offboarding case {offboarding_id} not found."
    if asset_type not in REQUIRED_ASSETS:
        return f"Unknown asset type '{asset_type}'. Valid: {', '.join(REQUIRED_ASSETS.keys())}"
    if status not in ("returned", "lost", "pending"):
        return f"Invalid status '{status}'. Use 'returned', 'lost', or 'pending'."

    _assets.setdefault(offboarding_id, {})[asset_type] = status
    _save_asset_to_db(offboarding_id, asset_type, status)
    return f"Asset '{REQUIRED_ASSETS[asset_type]}' for {offboarding_id} marked as {status}."


# ---------------------------------------------------------------------------
# 4. Schedule Exit Interview
# ---------------------------------------------------------------------------
@tool
def schedule_exit_interview(
    offboarding_id: str,
    interview_date: str,
    interviewer_name: str,
    interviewer_email: str,
) -> str:
    """
    Schedule an exit interview for the departing employee and notify them via email.

    Args:
        offboarding_id: The offboarding case ID (e.g. "OFF-101")
        interview_date: Date for the exit interview (YYYY-MM-DD)
        interviewer_name: Name of the HR person conducting the interview
        interviewer_email: Email of the interviewer
    """
    if offboarding_id not in _offboardings:
        return f"Offboarding case {offboarding_id} not found."

    try:
        datetime.strptime(interview_date, "%Y-%m-%d")
    except ValueError:
        return "Invalid date format. Use YYYY-MM-DD."

    rec = _offboardings[offboarding_id]
    interview = {
        "offboarding_id": offboarding_id,
        "interview_date": interview_date,
        "interviewer_name": interviewer_name,
        "interviewer_email": interviewer_email,
        "status": "scheduled",
        "created_at": datetime.now().isoformat(),
    }
    _exit_interviews[offboarding_id] = interview
    _save_exit_interview_to_db(interview)

    subject = f"Exit Interview Scheduled — {rec['employee_name']}"
    body = (
        f"<p>Dear {rec['employee_name']},</p>"
        f"<p>Your exit interview has been scheduled for <b>{interview_date}</b> "
        f"with <b>{interviewer_name}</b> ({interviewer_email}).</p>"
        f"<p>The interview is a confidential conversation to gather your feedback "
        f"and ensure a smooth transition.</p>"
        f"<p>Best regards,<br><b>HR Team</b></p>"
    )
    _send_email(rec["employee_email"], subject, body)

    # Also notify the interviewer
    interviewer_body = (
        f"<p>Hi {interviewer_name},</p>"
        f"<p>An exit interview has been scheduled with <b>{rec['employee_name']}</b> "
        f"({rec['role']}, {rec['department']}) for <b>{interview_date}</b>.</p>"
        f"<p>Reason for departure: {rec['reason']}</p>"
        f"<p>Best regards,<br><b>HR Automation</b></p>"
    )
    _send_email(interviewer_email, f"Exit Interview: {rec['employee_name']} on {interview_date}", interviewer_body)

    _messages[offboarding_id].append({
        "type": "exit_interview_scheduled",
        "sent_at": datetime.now().isoformat(),
        "to": rec["employee_email"],
        "content": f"Interview on {interview_date} with {interviewer_name}",
    })
    _save_message_to_db(offboarding_id, _messages[offboarding_id][-1])

    return (
        f"Exit interview scheduled for {rec['employee_name']} on {interview_date} "
        f"with {interviewer_name}. Both parties notified via email."
    )


# ---------------------------------------------------------------------------
# 5. Revoke Access
# ---------------------------------------------------------------------------
@tool
def revoke_access(offboarding_id: str) -> str:
    """
    Mark all system access as revoked for the departing employee and notify IT/HR.
    This updates the offboarding status and sends a notification email to HR.

    Args:
        offboarding_id: The offboarding case ID (e.g. "OFF-101")
    """
    if offboarding_id not in _offboardings:
        return f"Offboarding case {offboarding_id} not found."

    rec = _offboardings[offboarding_id]
    rec["access_revoked"] = True
    rec["access_revoked_at"] = datetime.now().isoformat()
    _save_offboarding_to_db(rec)

    subject = f"Access Revocation — {rec['employee_name']} ({rec['employee_id']})"
    body = (
        f"<p>Access has been revoked for the following departing employee:</p>"
        f"<ul>"
        f"<li><b>Name:</b> {rec['employee_name']}</li>"
        f"<li><b>Employee ID:</b> {rec['employee_id']}</li>"
        f"<li><b>Role:</b> {rec['role']}</li>"
        f"<li><b>Department:</b> {rec['department']}</li>"
        f"<li><b>Last Working Date:</b> {rec['last_working_date']}</li>"
        f"</ul>"
        f"<p>Please ensure all account access (email, VPN, internal tools, repos) "
        f"is disabled by end of their last working day.</p>"
        f"<p>— HR Automation</p>"
    )
    _send_email(HR_EMAIL, subject, body)

    _messages[offboarding_id].append({
        "type": "access_revoked",
        "sent_at": datetime.now().isoformat(),
        "to": HR_EMAIL,
    })
    _save_message_to_db(offboarding_id, _messages[offboarding_id][-1])

    return f"Access revocation flagged for {rec['employee_name']}. HR/IT notified at {HR_EMAIL}."


# ---------------------------------------------------------------------------
# 6. Assign Knowledge Transfer
# ---------------------------------------------------------------------------
@tool
def assign_knowledge_transfer(
    offboarding_id: str,
    successor_name: str,
    successor_email: str,
    handover_deadline: str,
) -> str:
    """
    Assign a knowledge transfer task to the departing employee and notify both parties.

    Args:
        offboarding_id: The offboarding case ID (e.g. "OFF-101")
        successor_name: Name of the person taking over responsibilities
        successor_email: Email of the successor
        handover_deadline: Deadline for completing the handover (YYYY-MM-DD)
    """
    if offboarding_id not in _offboardings:
        return f"Offboarding case {offboarding_id} not found."

    try:
        datetime.strptime(handover_deadline, "%Y-%m-%d")
    except ValueError:
        return "Invalid date format. Use YYYY-MM-DD."

    rec = _offboardings[offboarding_id]
    rec["kt_successor"] = successor_name
    rec["kt_successor_email"] = successor_email
    rec["kt_deadline"] = handover_deadline
    _save_offboarding_to_db(rec)

    # Notify departing employee
    subject_emp = f"Knowledge Transfer — Handover to {successor_name}"
    body_emp = (
        f"<p>Dear {rec['employee_name']},</p>"
        f"<p>As part of your offboarding, please complete a knowledge transfer handover "
        f"to <b>{successor_name}</b> ({successor_email}) by <b>{handover_deadline}</b>.</p>"
        f"<p><b>Handover checklist:</b></p>"
        f"<ul>"
        f"<li>Document all ongoing projects and their status</li>"
        f"<li>Share access to relevant repositories, docs, and dashboards</li>"
        f"<li>Walk through critical processes and runbooks</li>"
        f"<li>Introduce key stakeholders and contacts</li>"
        f"</ul>"
        f"<p>Best regards,<br><b>HR Team</b></p>"
    )
    _send_email(rec["employee_email"], subject_emp, body_emp)

    # Notify successor
    subject_suc = f"Knowledge Transfer from {rec['employee_name']}"
    body_suc = (
        f"<p>Hi {successor_name},</p>"
        f"<p>You have been assigned as the successor for <b>{rec['employee_name']}</b> "
        f"({rec['role']}, {rec['department']}), whose last working day is <b>{rec['last_working_date']}</b>.</p>"
        f"<p>Please coordinate with them to complete the handover by <b>{handover_deadline}</b>.</p>"
        f"<p>Best regards,<br><b>HR Team</b></p>"
    )
    _send_email(successor_email, subject_suc, body_suc)

    _messages[offboarding_id].append({
        "type": "knowledge_transfer_assigned",
        "sent_at": datetime.now().isoformat(),
        "to": rec["employee_email"],
        "content": f"KT to {successor_name} by {handover_deadline}",
    })
    _save_message_to_db(offboarding_id, _messages[offboarding_id][-1])

    return (
        f"Knowledge transfer assigned.\n"
        f"Departing: {rec['employee_name']} → Successor: {successor_name}\n"
        f"Deadline: {handover_deadline}\n"
        f"Both parties notified via email."
    )


# ---------------------------------------------------------------------------
# 7. Notify HR (Final Settlement)
# ---------------------------------------------------------------------------
@tool
def notify_hr_final_settlement(offboarding_id: str) -> str:
    """
    Notify HR to process the final settlement for the departing employee.
    Includes notice period shortfall, asset status, and pending items.

    Args:
        offboarding_id: The offboarding case ID (e.g. "OFF-101")
    """
    if offboarding_id not in _offboardings:
        return f"Offboarding case {offboarding_id} not found."

    rec = _offboardings[offboarding_id]
    assets = _assets.get(offboarding_id, {})
    pending_assets = [REQUIRED_ASSETS[k] for k, v in assets.items() if v != "returned"]
    lost_assets = [REQUIRED_ASSETS[k] for k, v in assets.items() if v == "lost"]

    settlement_notes = []
    if rec.get("notice_shortfall_days", 0) > 0:
        settlement_notes.append(
            f"Notice shortfall: {rec['notice_shortfall_days']} days — calculate buyout deduction."
        )
    if lost_assets:
        settlement_notes.append(f"Lost assets (deduct from settlement): {', '.join(lost_assets)}")
    if pending_assets:
        settlement_notes.append(f"Pending asset returns: {', '.join(pending_assets)}")

    notes_html = "".join(f"<li>{n}</li>" for n in settlement_notes) if settlement_notes else "<li>No deductions or pending items.</li>"

    subject = f"Final Settlement Required — {rec['employee_name']} ({rec['employee_id']})"
    body = (
        f"<p>The following employee's offboarding is ready for final settlement:</p>"
        f"<ul>"
        f"<li><b>Name:</b> {rec['employee_name']}</li>"
        f"<li><b>Employee ID:</b> {rec['employee_id']}</li>"
        f"<li><b>Last Working Date:</b> {rec['last_working_date']}</li>"
        f"<li><b>Reason:</b> {rec['reason']}</li>"
        f"</ul>"
        f"<p><b>Settlement Notes:</b></p><ul>{notes_html}</ul>"
        f"<p>Please process the final settlement accordingly.</p>"
        f"<p>— HR Automation</p>"
    )
    _send_email(HR_EMAIL, subject, body)

    rec["status"] = "settlement_pending"
    _save_offboarding_to_db(rec)

    _messages[offboarding_id].append({
        "type": "final_settlement_requested",
        "sent_at": datetime.now().isoformat(),
        "to": HR_EMAIL,
    })
    _save_message_to_db(offboarding_id, _messages[offboarding_id][-1])

    return (
        f"HR notified for final settlement of {rec['employee_name']}.\n"
        f"Notice shortfall: {rec.get('notice_shortfall_days', 0)} days\n"
        f"Pending assets: {len(pending_assets)}\n"
        f"Lost assets: {len(lost_assets)}\n"
        f"Status updated to: settlement_pending"
    )


# ---------------------------------------------------------------------------
# 8. Get Full Offboarding Status
# ---------------------------------------------------------------------------
@tool
def get_offboarding_status(offboarding_id: str) -> str:
    """
    Get a comprehensive summary of the offboarding case including timeline,
    assets, exit interview, knowledge transfer, and settlement status.

    Args:
        offboarding_id: The offboarding case ID (e.g. "OFF-101")
    """
    if offboarding_id not in _offboardings:
        return f"Offboarding case {offboarding_id} not found."

    rec = _offboardings[offboarding_id]
    assets = _assets.get(offboarding_id, {})
    interview = _exit_interviews.get(offboarding_id)
    msgs = _messages.get(offboarding_id, [])

    lines = [
        f"Offboarding Status — {rec['employee_name']}",
        "=" * 55,
        f"Offboarding ID: {rec['offboarding_id']}",
        f"Employee ID: {rec['employee_id']}",
        f"Role: {rec['role']} | Department: {rec['department']}",
        f"Manager: {rec['manager']}",
        f"Resignation: {rec['resignation_date']} | Last Day: {rec['last_working_date']}",
        f"Reason: {rec['reason']}",
        f"Level: {rec['level']}",
        f"Notice: {rec['actual_notice_days']} of {rec['required_notice_days']} days"
        + (f" (SHORTFALL: {rec['notice_shortfall_days']}d)" if rec.get("notice_shortfall_days", 0) > 0 else ""),
        f"Status: {rec['status']}",
        "",
        "Assets:",
    ]
    for key, label in REQUIRED_ASSETS.items():
        status = assets.get(key, "pending")
        icon = "[✓]" if status == "returned" else ("[!]" if status == "lost" else "[✗]")
        lines.append(f"  {icon} {label}: {status}")

    lines.append("")
    if interview:
        lines.append(f"Exit Interview: {interview['interview_date']} with {interview['interviewer_name']} ({interview['status']})")
    else:
        lines.append("Exit Interview: Not scheduled")

    if rec.get("kt_successor"):
        lines.append(f"Knowledge Transfer: → {rec['kt_successor']} (deadline: {rec.get('kt_deadline', 'N/A')})")
    else:
        lines.append("Knowledge Transfer: Not assigned")

    lines.append(f"Access Revoked: {'Yes' if rec.get('access_revoked') else 'No'}")
    lines.append(f"Communications sent: {len(msgs)}")

    return "\n".join(lines)
