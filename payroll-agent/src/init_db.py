"""
Database initialization script for Payroll Automation Agent.
Verifies Supabase connection and prints the SQL needed to create tables.

Usage:
    python init_db.py
"""
import sys
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    """Verify Supabase connection and ensure payroll tables exist."""
    logger.info("Initializing Payroll Automation Agent (Supabase)...")

    try:
        from db import supabase, SUPABASE_URL
        from payroll_models import CREATE_TABLES_SQL

        safe_url = SUPABASE_URL[:40] + "..." if len(SUPABASE_URL) > 40 else SUPABASE_URL
        logger.info(f"Connecting to Supabase: {safe_url}")

        # Check if tables exist
        tables_exist = {
            'employees': False,
            'attendance_records': False,
            'payroll_records': False,
            'payslips': False
        }
        
        for table_name in tables_exist.keys():
            try:
                supabase.table(table_name).select("*").limit(1).execute()
                tables_exist[table_name] = True
                logger.info(f"✓ {table_name} table exists and is accessible.")
            except Exception as table_err:
                err_str = str(table_err)
                if "does not exist" in err_str or "42P01" in err_str or "relation" in err_str.lower():
                    logger.warning(f"✗ {table_name} table not found.")
                else:
                    logger.warning(f"? {table_name} check error: {err_str[:100]}")
        
        # If all tables exist, we're done
        if all(tables_exist.values()):
            logger.info("\n✓ All payroll tables already exist!")
            logger.info("Database initialization complete!")
            logger.info("\nTo seed sample data, run: python seed_data.py")
            return
        
        # Some tables missing: print creation SQL
        missing_tables = [t for t, exists in tables_exist.items() if not exists]
        print("\n" + "=" * 70)
        print(f"Tables not found: {', '.join(missing_tables)}")
        print("Run this SQL in your Supabase SQL Editor:")
        print("  Supabase Dashboard → SQL Editor → New query → paste & run")
        print("=" * 70)
        print(CREATE_TABLES_SQL)
        print("=" * 70)
        print("\nAfter creating the tables, run 'python seed_data.py' to populate sample data.")
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
