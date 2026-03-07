"""
Supabase database client and helper functions.
All tables live in Supabase (PostgreSQL). Files go to Supabase Storage.

Required env vars:
  SUPABASE_URL   — project URL  (e.g. https://xyz.supabase.co)
  SUPABASE_KEY   — service-role key (or anon key with proper RLS)
"""
import os
from datetime import datetime
from supabase import create_client, Client

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
STORAGE_BUCKET = os.getenv("SUPABASE_STORAGE_BUCKET", "onboarding-docs")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("SUPABASE_URL and SUPABASE_KEY environment variables are required.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


# ---------------------------------------------------------------------------
# Ensure storage bucket exists
# ---------------------------------------------------------------------------
def _ensure_bucket():
    """Create the storage bucket if it doesn't already exist."""
    try:
        supabase.storage.create_bucket(STORAGE_BUCKET, options={"public": False})
        # Bucket was just created successfully
    except Exception as create_err:
        err_msg = str(create_err).lower()
        # Swallow "already exists" — bucket was created previously, all good
        if "already exist" in err_msg or "duplicate" in err_msg:
            return
        # Creation failed for another reason — verify the bucket is actually accessible
        try:
            supabase.storage.get_bucket(STORAGE_BUCKET)
        except Exception:
            raise RuntimeError(
                f"Storage bucket '{STORAGE_BUCKET}' does not exist and could not be created.\n"
                f"Creation error: {create_err}\n"
                f"Fix: Supabase Dashboard -> Storage -> New Bucket -> name it '{STORAGE_BUCKET}'.\n"
                f"Also ensure SUPABASE_KEY is the service-role key, not the anon key."
            )


_ensure_bucket()


# ---------------------------------------------------------------------------
# Seeding helpers — insert defaults if tables are empty
# ---------------------------------------------------------------------------
def _seed_defaults():
    """Insert default orientation events and HR tasks if tables are empty."""
    existing = supabase.table("orientation_templates").select("id").limit(1).execute()
    if not existing.data:
        supabase.table("orientation_templates").insert([
            {"event": "HR Orientation", "start_time": "09:00 AM", "end_time": "11:00 AM", "duration": "2 hours", "sort_order": 1},
            {"event": "Team Introduction", "start_time": "11:00 AM", "end_time": "12:00 PM", "duration": "1 hour", "sort_order": 2},
            {"event": "IT Setup & Systems Access", "start_time": "02:00 PM", "end_time": "03:30 PM", "duration": "1.5 hours", "sort_order": 3},
            {"event": "Manager 1:1 Meeting", "start_time": "04:00 PM", "end_time": "05:00 PM", "duration": "1 hour", "sort_order": 4},
        ]).execute()

    existing = supabase.table("hr_tasks").select("id").limit(1).execute()
    if not existing.data:
        supabase.table("hr_tasks").insert([
            {"task": "Create email account", "sort_order": 1},
            {"task": "Create system access credentials", "sort_order": 2},
            {"task": "Prepare laptop / workstation", "sort_order": 3},
            {"task": "Issue employee ID badge", "sort_order": 4},
            {"task": "Add to payroll system", "sort_order": 5},
        ]).execute()


_seed_defaults()
