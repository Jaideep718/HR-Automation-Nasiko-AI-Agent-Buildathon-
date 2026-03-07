"""
Tools for the HR Helpdesk Agent.
Provides HR policy lookup, escalation, and ticket management capabilities.
Policies are stored in Pinecone and retrieved via RAG (see rag_policies.py).
Escalation tickets are stored in PostgreSQL database.
"""
import os
import re
import glob
import uuid
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from typing import Dict, List, Any
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

# SMTP Configuration - Set these environment variables
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", "hr-helpdesk@company.com")
SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "HR Helpdesk")

_EMAIL_REGEX = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

# Used to validate a single string is exactly a valid email (fullmatch)
_EMAIL_VALIDATOR = re.compile(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$")

# Patterns like "my email is john@x.com", "email: john@x.com", "reach me at john@x.com"
_CONTEXTUAL_EMAIL_RE = re.compile(
    r"(?:my\s+email(?:\s+(?:address\s+)?is)?|email\s*(?:address)?\s*[:=]|reach\s+me\s+at|contact\s+me\s+at|send\s+(?:it\s+)?to)"
    r"\s*([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})",
    re.IGNORECASE,
)

# Optional domain whitelist – set ALLOWED_EMAIL_DOMAINS env var as comma-separated
# e.g. "company.com,corp.com".  Leave empty to allow any domain.
_ALLOWED_DOMAINS = [
    d.strip().lower()
    for d in os.getenv("ALLOWED_EMAIL_DOMAINS", "").split(",")
    if d.strip()
]


def _is_domain_allowed(email: str) -> bool:
    """Return True if the email's domain is in the whitelist (or whitelist is empty)."""
    if not _ALLOWED_DOMAINS:
        return True
    domain = email.rsplit("@", 1)[-1].lower()
    return domain in _ALLOWED_DOMAINS


def extract_email_from_text(text: str) -> str:
    """Extract the best email address from *text*.

    Strategy:
      1. Prefer an email preceded by a clear contextual phrase
         ("my email is …", "email: …", "reach me at …").
      2. Fall back to the first bare email found in the text.
      3. If a domain whitelist is configured, only return emails
         whose domain matches.
    Returns '' if no valid email is found.
    """
    if not text:
        return ""

    # 1. Try contextual match first
    ctx = _CONTEXTUAL_EMAIL_RE.search(text)
    if ctx:
        candidate = ctx.group(1)
        if _is_domain_allowed(candidate):
            return candidate

    # 2. Fall back to all bare emails, pick the first allowed one
    for match in _EMAIL_REGEX.finditer(text):
        candidate = match.group(0)
        if _is_domain_allowed(candidate):
            return candidate

    return ""


def send_ticket_email(
    to_email: str,
    ticket_id: str,
    employee_name: str,
    issue_description: str,
    priority: str,
    category: str,
    expected_response: str
) -> bool:
    """
    Send an email notification with ticket details using SMTP.
    
    Returns:
        True if email was sent successfully, False otherwise
    """
    if not SMTP_USER or not SMTP_PASSWORD:
        logger.warning("SMTP credentials not configured. Email not sent.")
        return False
    
    try:
        # Create the email message
        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"HR Ticket Created - {ticket_id}"
        msg["From"] = f"{SMTP_FROM_NAME} <{SMTP_FROM_EMAIL}>"
        msg["To"] = to_email
        
        # Plain text version
        text_content = f"""
HR Helpdesk - Ticket Confirmation
==================================

Dear {employee_name},

Your HR support ticket has been successfully created. Below are the details:

Ticket Information:
-------------------
Ticket ID: {ticket_id}
Employee Name: {employee_name}
Category: {category.title()}
Priority: {priority.title()}
Status: Open
Expected Response Time: {expected_response}

Issue Description:
------------------
{issue_description}

What happens next:
------------------
1. An HR representative will review your case
2. HR will reach out within the expected response time
3. You can check ticket status anytime using your ticket ID: {ticket_id}

For urgent matters, please call HR directly at (555) 123-4567

Best regards,
HR Helpdesk Team
hr@company.com
"""
        
        # HTML version
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background-color: #2c3e50; color: white; padding: 20px; text-align: center; }}
        .content {{ padding: 20px; background-color: #f9f9f9; }}
        .ticket-box {{ background-color: white; border: 1px solid #ddd; padding: 20px; margin: 15px 0; border-radius: 5px; }}
        .field {{ margin: 10px 0; }}
        .label {{ font-weight: bold; color: #2c3e50; }}
        .value {{ color: #555; }}
        .priority-urgent {{ color: #e74c3c; font-weight: bold; }}
        .priority-high {{ color: #e67e22; font-weight: bold; }}
        .priority-medium {{ color: #f39c12; }}
        .priority-low {{ color: #27ae60; }}
        .footer {{ text-align: center; padding: 20px; color: #777; font-size: 12px; }}
        .next-steps {{ background-color: #ecf0f1; padding: 15px; border-radius: 5px; margin-top: 15px; }}
        .ticket-id {{ font-size: 24px; color: #2c3e50; font-weight: bold; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎫 HR Helpdesk</h1>
            <p>Ticket Confirmation</p>
        </div>
        <div class="content">
            <p>Dear <strong>{employee_name}</strong>,</p>
            <p>Your HR support ticket has been successfully created. Below are the details:</p>
            
            <div class="ticket-box">
                <div class="field">
                    <span class="label">🎫 Ticket ID:</span>
                    <span class="ticket-id">{ticket_id}</span>
                </div>
                <div class="field">
                    <span class="label">👤 Employee Name:</span>
                    <span class="value">{employee_name}</span>
                </div>
                <div class="field">
                    <span class="label">📋 Category:</span>
                    <span class="value">{category.title()}</span>
                </div>
                <div class="field">
                    <span class="label">🔴 Priority:</span>
                    <span class="value priority-{priority.lower()}">{priority.title()}</span>
                </div>
                <div class="field">
                    <span class="label">📝 Status:</span>
                    <span class="value">Open</span>
                </div>
                <div class="field">
                    <span class="label">⏱️ Expected Response:</span>
                    <span class="value">{expected_response}</span>
                </div>
            </div>
            
            <div class="ticket-box">
                <div class="label">📄 Issue Description:</div>
                <p class="value">{issue_description}</p>
            </div>
            
            <div class="next-steps">
                <h3>What happens next:</h3>
                <ol>
                    <li>An HR representative will review your case</li>
                    <li>HR will reach out within the expected response time</li>
                    <li>You can check ticket status anytime using your ticket ID</li>
                </ol>
            </div>
            
            <p style="margin-top: 20px;">
                <strong>For urgent matters:</strong> Call HR directly at (555) 123-4567
            </p>
        </div>
        <div class="footer">
            <p>Best regards,<br>HR Helpdesk Team<br>hr@company.com</p>
        </div>
    </div>
</body>
</html>
"""
        
        # Attach both versions
        msg.attach(MIMEText(text_content, "plain"))
        msg.attach(MIMEText(html_content, "html"))
        
        # Connect to SMTP server and send
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
        
        logger.info(f"Email sent successfully to {to_email} for ticket {ticket_id}")
        return True
        
    except smtplib.SMTPAuthenticationError as e:
        logger.error(f"SMTP authentication failed for user '{SMTP_USER}': {e}. "
                     f"Ensure SMTP_USER is the full Gmail address (e.g. yourname@gmail.com) "
                     f"and SMTP_PASSWORD is a valid Gmail App Password.")
        return False
    except smtplib.SMTPException as e:
        logger.error(f"SMTP error sending email to {to_email}: {e}")
        return False
    except Exception as e:
        logger.error(f"Failed to send email to {to_email}: {e}")
        return False


# Import RAG policy query function; fails gracefully if Pinecone is unavailable
try:
    from rag_policies import query_policy
    _RAG_AVAILABLE = True
    _RAG_ERROR = ""
except Exception as _e:
    _RAG_AVAILABLE = False
    _RAG_ERROR = str(_e)

# Import RAG FAQ query function; fails gracefully if Pinecone FAQ index is unavailable
try:
    from rag_faqs import query_faq
    _FAQ_RAG_AVAILABLE = True
    _FAQ_RAG_ERROR = ""
except Exception as _faq_e:
    _FAQ_RAG_AVAILABLE = False
    _FAQ_RAG_ERROR = str(_faq_e)

# Import Supabase client; fails gracefully if not configured
try:
    from db import supabase
    _DB_AVAILABLE = True
    _DB_ERROR = ""
except Exception as _db_e:
    _DB_AVAILABLE = False
    _DB_ERROR = str(_db_e)
    logger.warning(f"Supabase connection unavailable: {_DB_ERROR}")


@tool
def search_hr_policy(query: str) -> str:
    """
    Search HR policies based on a keyword or topic.
    Use this tool when employees ask about company policies, benefits, leave,
    remote work, expenses, onboarding, performance reviews, code of conduct, or resignation.
    Policies are retrieved from a Pinecone vector database using RAG.

    Args:
        query: The policy topic or keyword to search for (e.g., "leave", "remote work", "benefits")
    """
    if not _RAG_AVAILABLE:
        return (
            f"Policy search is temporarily unavailable ({_RAG_ERROR}). "
            "Please contact HR directly at hr@company.com or call (555) 123-4567."
        )
    try:
        return query_policy(query)
    except Exception as e:
        return f"Error searching policies: {str(e)}. Please contact HR directly at hr@company.com."


@tool
def get_faq_answer(question_topic: str) -> str:
    """
    Get quick answers to frequently asked HR questions using a Pinecone-backed RAG system.
    Use this for common questions about passwords, payroll, vacation balance, org chart,
    HR contact information, holiday schedules, benefits, or onboarding.

    Args:
        question_topic: The question or topic to look up (e.g., "how do I reset my password?",
                        "when is payday?", "how much vacation do I have?")
    """
    if not _FAQ_RAG_AVAILABLE:
        return (
            f"FAQ search is temporarily unavailable ({_FAQ_RAG_ERROR}). "
            "Please contact HR directly at hr@company.com or call (555) 123-4567."
        )
    try:
        return query_faq(question_topic)
    except Exception as e:
        return f"Error retrieving FAQ answer: {str(e)}. Please contact HR directly at hr@company.com."


@tool
def escalate_to_hr(
    issue_description: str,
    employee_name: str,
    employee_email: str,
    priority: str = "medium",
    category: str = "general"
) -> str:
    """
    Escalate a complex HR issue that requires human intervention.
    Use this when the issue is complex, sensitive, or cannot be resolved with existing policies.
    Examples: disputes, complaints, special accommodations, complex leave situations, grievances.
    Tickets are stored in PostgreSQL database for persistence and tracking.
    A confirmation email will be sent to the employee with ticket details.

    IMPORTANT: You MUST collect all three required fields from the user BEFORE calling this tool.
    Do NOT call this tool if any field is missing or unknown.
    - employee_name: must be the employee's real full name (not "unknown" or a placeholder)
    - employee_email: must be a valid email address like user@example.com (not "N/A" or a placeholder)
    - issue_description: must be a detailed description, at least one full sentence
    If any field is missing, ask the user for it first.

    Args:
        issue_description: Detailed description of the issue to escalate (required, at least one sentence)
        employee_name: Full name of the employee raising the issue (required)
        employee_email: Valid email address of the employee, e.g. jane@company.com (required)
        priority: Priority level - "low", "medium", "high", or "urgent"
        category: Issue category - "general", "benefits", "leave", "complaint", "payroll", "accommodation", "other"
    """
    if not _DB_AVAILABLE:
        return (
            f"Escalation system is temporarily unavailable ({_DB_ERROR}). "
            "Please contact HR directly at hr@company.com or call (555) 123-4567."
        )
    
    try:
        # ===== Validate all required fields =====
        missing_fields = []

        if not employee_name or not employee_name.strip():
            missing_fields.append("your full name")

        if not issue_description or not issue_description.strip() or len(issue_description.strip()) < 10:
            missing_fields.append("a detailed description of your issue (at least a sentence)")

        # Validate that employee_email is an actual email address (not a placeholder)
        resolved_email = ""
        if employee_email and employee_email.strip():
            if _EMAIL_VALIDATOR.match(employee_email.strip()):
                resolved_email = employee_email.strip()
        # If still empty, try extracting from the description as a last resort
        if not resolved_email:
            resolved_email = extract_email_from_text(issue_description)
        if not resolved_email:
            missing_fields.append("your email address (e.g. yourname@company.com)")

        if missing_fields:
            return (
                "To create an escalation ticket, I still need the following information:\n"
                + "\n".join(f"- {f}" for f in missing_fields)
                + "\n\nPlease provide these details so I can proceed."
            )

        employee_email = resolved_email

        # Validate priority
        valid_priorities = ["low", "medium", "high", "urgent"]
        if priority.lower() not in valid_priorities:
            priority = "medium"
        
        # Validate category
        valid_categories = ["general", "benefits", "leave", "complaint", "payroll", "accommodation", "other"]
        if category.lower() not in valid_categories:
            category = "general"
        
        # Generate ticket ID
        ticket_id = f"HR-{datetime.now().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"
        expected_response = "4 hours" if priority.lower() == "urgent" else "24-48 hours"
        
        # Create ticket in Supabase via REST API
        ticket_data = {
            "ticket_id": ticket_id,
            "employee_name": employee_name,
            "issue_description": issue_description,
            "priority": priority.lower(),
            "category": category.lower(),
            "status": "open",
            "assigned_to": "HR Team",
            "expected_response": expected_response,
            "contact_email": employee_email
        }
        supabase.table("escalation_tickets").insert(ticket_data).execute()
        
        # Send confirmation email only if we have a valid recipient
        email_sent = False
        if employee_email:
            email_sent = send_ticket_email(
                to_email=employee_email,
                ticket_id=ticket_id,
                employee_name=employee_name,
                issue_description=issue_description,
                priority=priority.lower(),
                category=category.lower(),
                expected_response=expected_response
            )
        
        # Build response message
        if email_sent:
            email_status = "📧 A confirmation email has been sent to your email address."
        else:
            email_status = "⚠️ Email notification could not be sent. Please save your ticket ID."
        
        response = f"""
**Issue Escalated Successfully**

🎫 **Ticket ID:** {ticket_id}
👤 **Employee:** {employee_name}
📧 **Email:** {employee_email}
📋 **Category:** {category.title()}
🔴 **Priority:** {priority.title()}
📝 **Status:** Open

**Expected Response Time:** {expected_response}

{email_status}

Your issue has been forwarded to the HR team. They will contact you via email or phone.

**What happens next:**
1. An HR representative will review your case
2. Check your email for ticket confirmation details
3. HR will reach out within the expected response time
4. You can check ticket status anytime using the ticket ID

**For urgent matters:** Call HR directly at (555) 123-4567
"""
        logger.info(f"Created escalation ticket {ticket_id} for {employee_name}")
        return response
        
    except Exception as e:
        logger.error(f"Error creating escalation ticket: {e}")
        return f"Error creating escalation ticket: {str(e)}. Please contact HR directly at hr@company.com or call (555) 123-4567."


@tool
def check_ticket_status(ticket_id: str) -> str:
    """
    Check the status of an existing HR escalation ticket from the database.
    
    Args:
        ticket_id: The ticket ID to check (e.g., "HR-20260307-ABC12345")
    """
    if not _DB_AVAILABLE:
        return (
            f"Ticket lookup is temporarily unavailable ({_DB_ERROR}). "
            "Please contact HR directly at hr@company.com or call (555) 123-4567."
        )
    
    try:
        ticket_id_upper = ticket_id.strip().upper()
        
        response = supabase.table("escalation_tickets").select("*").eq(
            "ticket_id", ticket_id_upper
        ).execute()
        
        if response.data:
            ticket = response.data[0]
            created_at = ticket.get("created_at", "N/A")
            updated_at = ticket.get("updated_at", "N/A")
            # Trim timestamps to readable format if they are ISO strings
            if created_at and created_at != "N/A":
                created_at = created_at[:19].replace("T", " ")
            if updated_at and updated_at != "N/A":
                updated_at = updated_at[:19].replace("T", " ")
            
            response_text = f"""
**Ticket Status**

🎫 **Ticket ID:** {ticket['ticket_id']}
👤 **Employee:** {ticket['employee_name']}
📋 **Category:** {str(ticket.get('category', 'N/A')).title()}
🔴 **Priority:** {str(ticket.get('priority', 'N/A')).title()}
📝 **Status:** {str(ticket.get('status', 'N/A')).title()}
🕐 **Created:** {created_at}
🔄 **Last Updated:** {updated_at}
👥 **Assigned To:** {ticket.get('assigned_to', 'HR Team')}

**Expected Response:** {ticket.get('expected_response', '24-48 hours')}
"""
            if ticket.get('status') in ['resolved', 'closed'] and ticket.get('resolution'):
                response_text += f"\n📋 **Resolution:** {ticket['resolution']}\n"
            
            response_text += "\nFor questions about this ticket, contact HR at hr@company.com referencing your ticket ID."
            return response_text
        else:
                return f"Ticket '{ticket_id}' not found. Please verify the ticket ID and try again. If you need to create a new escalation, I can help you with that."
            
    except Exception as e:
        logger.error(f"Error checking ticket status: {e}")
        return f"Error checking ticket status: {str(e)}. Please contact HR directly at hr@company.com."


@tool
def list_hr_policy_topics() -> str:
    """
    List all available HR policy topics stored in the database.
    Use this when the employee wants to know what policies are available.
    Topics are derived from the documents ingested into the Pinecone vector database.
    """
    try:
        policies_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "policies")
        pdf_files = glob.glob(os.path.join(policies_dir, "**", "*.pdf"), recursive=True)
        txt_files = glob.glob(os.path.join(policies_dir, "**", "*.txt"), recursive=True)
        all_files = sorted(pdf_files + txt_files)

        faqs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "faqs")
        faq_files = glob.glob(os.path.join(faqs_dir, "*.txt"))
        faq_topics = [
            f"- **{os.path.splitext(os.path.basename(f))[0].replace('_', ' ').replace('-', ' ').title()}**"
            for f in sorted(faq_files)
        ]

        if not all_files:
            policy_section = (
                "No policy documents are currently loaded in the database. "
                "Please contact HR at hr@company.com for policy information."
            )
        else:
            policy_section = (
                "**Available HR Policy Topics:**\n\n"
                + "\n".join([
                    f"- **{os.path.splitext(os.path.basename(f))[0].replace('_', ' ').replace('-', ' ').title()}**"
                    for f in all_files
                ])
            )

        if not faq_topics:
            faq_section = "No FAQ topics are currently loaded."
        else:
            faq_section = "**Quick FAQ Topics:**\n\n" + "\n".join(faq_topics)

        return (
            policy_section
            + "\n\n"
            + faq_section
            + "\n\nTo get detailed information about any topic, just ask! For example:\n"
            + '- "What is the leave policy?"\n'
            + '- "Tell me about remote work guidelines"\n'
            + '- "How does expense reimbursement work?"'
        )
    except Exception as e:
        return f"Error listing policy topics: {str(e)}. Please contact HR directly at hr@company.com."
