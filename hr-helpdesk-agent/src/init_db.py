"""
Database initialization script for HR Helpdesk Agent.
Verifies Supabase connection and prints the SQL needed to create the tickets table.

Usage:
    python init_db.py
"""
import sys
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    """Verify Supabase connection and ensure escalation_tickets table exists."""
    logger.info("Initializing HR Helpdesk (Supabase)...")

    try:
        from db import supabase, SUPABASE_URL
        from ticket_models import CREATE_TABLE_SQL

        safe_url = SUPABASE_URL[:40] + "..." if len(SUPABASE_URL) > 40 else SUPABASE_URL
        logger.info(f"Connecting to Supabase: {safe_url}")

        # Try a lightweight query to check if the table already exists
        try:
            supabase.table("escalation_tickets").select("ticket_id").limit(1).execute()
            logger.info("✓ escalation_tickets table already exists and is accessible.")
            logger.info("Database initialization complete!")
            return
        except Exception as table_err:
            err_str = str(table_err)
            if "does not exist" in err_str or "42P01" in err_str or "relation" in err_str.lower():
                logger.warning("escalation_tickets table not found.")
            else:
                raise  # Unexpected error — re-raise

        # Table is missing: print creation SQL for the user to run
        print("\n" + "=" * 60)
        print("Table not found. Run this SQL in your Supabase SQL Editor:")
        print("  Supabase Dashboard → SQL Editor → New query → paste & run")
        print("=" * 60)
        print(CREATE_TABLE_SQL)
        print("=" * 60 + "\n")
        sys.exit(1)

    except Exception as e:
        logger.error(f"Initialization failed: {e}")
        logger.error("\nPlease ensure:")
        logger.error("1. SUPABASE_URL and SUPABASE_KEY are set in .env")
        logger.error("2. SUPABASE_KEY is the service_role key (not anon key)")
        logger.error("3. Your Supabase project is active")
        sys.exit(1)


if __name__ == "__main__":
    main()
