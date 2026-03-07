"""
Supabase client configuration for HR Helpdesk Agent.
Connects to Supabase via HTTPS REST API — no direct PostgreSQL connection needed.
This approach works through institutional firewalls and proxies.
"""
import os
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "").strip()

if not SUPABASE_URL:
    raise ValueError(
        "SUPABASE_URL is not set in .env. "
        "Get it from Supabase Dashboard → Project Settings → API → Project URL"
    )
if not SUPABASE_KEY:
    raise ValueError(
        "SUPABASE_KEY is not set in .env. "
        "Get it from Supabase Dashboard → Project Settings → API → service_role key"
    )

from supabase import create_client, Client

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def check_db_connection() -> bool:
    """
    Verify Supabase connection by attempting a lightweight query.
    Returns True if connection is successful, False otherwise.
    """
    try:
        supabase.table("escalation_tickets").select("ticket_id").limit(1).execute()
        return True
    except Exception:
        return False
