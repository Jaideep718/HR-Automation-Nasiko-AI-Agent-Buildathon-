"""
Database initialization script for the Employee Offboarding Agent.
Run the SQL below in Supabase Dashboard → SQL Editor → New Query.

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
    "offboardings",
    "offboarding_assets",
    "exit_interviews",
    "offboarding_messages",
]

CREATE_TABLES_SQL = """
-- Run this in Supabase Dashboard → SQL Editor → New Query

CREATE TABLE IF NOT EXISTS offboardings (
    offboarding_id TEXT PRIMARY KEY,
    employee_id TEXT NOT NULL,
    employee_name TEXT NOT NULL,
    employee_email TEXT NOT NULL,
    role TEXT NOT NULL,
    department TEXT NOT NULL,
    manager TEXT NOT NULL,
    resignation_date TEXT NOT NULL,
    last_working_date TEXT NOT NULL,
    reason TEXT DEFAULT 'not specified',
    level TEXT DEFAULT 'mid',
    required_notice_days INTEGER DEFAULT 60,
    actual_notice_days INTEGER DEFAULT 0,
    notice_shortfall_days INTEGER DEFAULT 0,
    status TEXT DEFAULT 'initiated',
    access_revoked BOOLEAN DEFAULT FALSE,
    access_revoked_at TIMESTAMPTZ,
    kt_successor TEXT,
    kt_successor_email TEXT,
    kt_deadline TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS offboarding_assets (
    id BIGSERIAL PRIMARY KEY,
    offboarding_id TEXT NOT NULL REFERENCES offboardings(offboarding_id),
    asset_type TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(offboarding_id, asset_type)
);

CREATE TABLE IF NOT EXISTS exit_interviews (
    id BIGSERIAL PRIMARY KEY,
    offboarding_id TEXT NOT NULL REFERENCES offboardings(offboarding_id) UNIQUE,
    interview_date TEXT NOT NULL,
    interviewer_name TEXT NOT NULL,
    interviewer_email TEXT NOT NULL,
    status TEXT DEFAULT 'scheduled',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS offboarding_messages (
    id BIGSERIAL PRIMARY KEY,
    offboarding_id TEXT NOT NULL REFERENCES offboardings(offboarding_id),
    type TEXT NOT NULL,
    sent_at TIMESTAMPTZ DEFAULT now(),
    to_email TEXT,
    content TEXT
);
"""


def main():
    from db import supabase

    logger.info("Checking Supabase connection...")
    try:
        supabase.table("offboardings").select("offboarding_id").limit(1).execute()
        logger.info("✅ Connected to Supabase successfully.")
    except Exception as e:
        logger.error(f"❌ Could not connect to Supabase: {e}")
        logger.info("\nPlease run the following SQL in Supabase SQL Editor:\n")
        print(CREATE_TABLES_SQL)
        sys.exit(1)

    all_ok = True
    for table in REQUIRED_TABLES:
        try:
            supabase.table(table).select("*").limit(1).execute()
            logger.info(f"  ✅ Table '{table}' exists")
        except Exception:
            logger.error(f"  ❌ Table '{table}' NOT FOUND")
            all_ok = False

    if not all_ok:
        logger.info("\nCreate missing tables with:\n")
        print(CREATE_TABLES_SQL)
        sys.exit(1)
    else:
        logger.info("\n✅ All offboarding tables are ready!")


if __name__ == "__main__":
    main()
