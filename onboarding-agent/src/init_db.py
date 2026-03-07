"""
Database initialization script for the Employee Onboarding Agent.
Verifies Supabase connection and checks that all required tables and
the storage bucket exist.

Usage:
    python src/init_db.py
"""
import sys
import os
import logging
from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

REQUIRED_TABLES = [
    "employees",
    "documents",
    "schedules",
    "orientation_templates",
    "hr_tasks",
    "messages",
]

CREATE_TABLES_SQL = """
-- Run this in Supabase Dashboard → SQL Editor → New Query

CREATE TABLE IF NOT EXISTS employees (
    employee_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    role TEXT NOT NULL,
    department TEXT NOT NULL,
    manager TEXT NOT NULL,
    start_date TEXT NOT NULL,
    location TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS documents (
    id BIGSERIAL PRIMARY KEY,
    employee_id TEXT NOT NULL,
    document_type TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    file_name TEXT,
    storage_path TEXT,
    updated_at TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT documents_emp_doc_unique UNIQUE (employee_id, document_type)
);

-- If the documents table already exists without the unique constraint, run this separately:
-- ALTER TABLE documents ADD CONSTRAINT documents_emp_doc_unique UNIQUE (employee_id, document_type);

CREATE TABLE IF NOT EXISTS schedules (
    id BIGSERIAL PRIMARY KEY,
    employee_id TEXT NOT NULL,
    event TEXT NOT NULL,
    time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    duration TEXT NOT NULL,
    date TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS orientation_templates (
    id BIGSERIAL PRIMARY KEY,
    event TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    duration TEXT NOT NULL,
    sort_order INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS hr_tasks (
    id BIGSERIAL PRIMARY KEY,
    task TEXT NOT NULL,
    sort_order INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS messages (
    id BIGSERIAL PRIMARY KEY,
    employee_id TEXT NOT NULL,
    type TEXT NOT NULL,
    sent_at TIMESTAMPTZ DEFAULT now(),
    to_email TEXT,
    content TEXT,
    urgency TEXT
);
"""


def check_env():
    missing = [v for v in ("SUPABASE_URL", "SUPABASE_KEY") if not os.getenv(v)]
    if missing:
        logger.error(f"Missing env vars: {', '.join(missing)}")
        logger.error("Set them in your .env file and try again.")
        sys.exit(1)


def check_tables(supabase):
    missing = []
    for table in REQUIRED_TABLES:
        try:
            supabase.table(table).select("*").limit(1).execute()
            logger.info(f"  ✓ {table}")
        except Exception as e:
            err = str(e)
            if "does not exist" in err or "42P01" in err or "relation" in err.lower():
                logger.warning(f"  ✗ {table} — NOT FOUND")
                missing.append(table)
            else:
                logger.error(f"  ✗ {table} — unexpected error: {e}")
                missing.append(table)
    return missing


def check_storage(supabase, bucket):
    try:
        supabase.storage.from_(bucket).list()
        logger.info(f"  ✓ Storage bucket '{bucket}'")
        return True
    except Exception as e:
        logger.warning(f"  ✗ Storage bucket '{bucket}' — {e}")
        return False


def main():
    logger.info("=" * 55)
    logger.info("  Employee Onboarding Agent — Supabase Connection Check")
    logger.info("=" * 55)

    # 1. Env vars
    check_env()

    # 2. Connect
    try:
        from db import supabase, SUPABASE_URL, STORAGE_BUCKET
        safe_url = SUPABASE_URL[:40] + "..." if len(SUPABASE_URL) > 40 else SUPABASE_URL
        logger.info(f"\nConnected to: {safe_url}")
    except Exception as e:
        logger.error(f"Failed to connect to Supabase: {e}")
        sys.exit(1)

    # 3. Tables
    logger.info("\nChecking tables:")
    missing_tables = check_tables(supabase)

    # 4. Storage bucket
    logger.info("\nChecking storage:")
    bucket_ok = check_storage(supabase, STORAGE_BUCKET)

    # 5. Summary
    logger.info("\n" + "=" * 55)
    if not missing_tables and bucket_ok:
        logger.info("  All checks passed. Database is ready!")
        logger.info("=" * 55)
    else:
        if missing_tables:
            logger.error(f"  Missing tables: {', '.join(missing_tables)}")
            logger.error("  Run the following SQL in Supabase SQL Editor:")
            print(CREATE_TABLES_SQL)
        if not bucket_ok:
            logger.error(f"  Create a storage bucket named '{STORAGE_BUCKET}' in:")
            logger.error("  Supabase Dashboard → Storage → New Bucket")
        logger.info("=" * 55)
        sys.exit(1)


if __name__ == "__main__":
    main()
