"""
Supabase database client for the Offboarding Agent.

Required env vars:
  SUPABASE_URL   — project URL  (e.g. https://xyz.supabase.co)
  SUPABASE_KEY   — service-role key
"""
import os
from supabase import create_client, Client

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("SUPABASE_URL and SUPABASE_KEY environment variables are required.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
