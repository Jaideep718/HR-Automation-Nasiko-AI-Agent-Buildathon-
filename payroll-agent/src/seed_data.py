"""
Synthetic data generation for Payroll Automation Agent.
Generates sample employees and attendance records for testing.

Usage:
    python seed_data.py
"""
import os
import sys
import uuid
import random
import logging
from datetime import datetime, date, timedelta
from decimal import Decimal

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Sample data pools
FIRST_NAMES = [
    "Rahul", "Priya", "Amit", "Sneha", "Vikram", "Anjali", "Arjun", "Kavita",
    "Ravi", "Meera", "Sanjay", "Divya", "Aditya", "Neha", "Karan", "Pooja",
    "Rajesh", "Swati", "Nikhil", "Ananya", "Deepak", "Shreya", "Manish", "Ritu",
    "Harsh", "Pallavi", "Ashish", "Megha", "Suresh", "Nisha"
]

LAST_NAMES = [
    "Sharma", "Patel", "Singh", "Kumar", "Reddy", "Verma", "Gupta", "Joshi",
    "Nair", "Rao", "Iyer", "Menon", "Pillai", "Chatterjee", "Banerjee", "Das",
    "Kapoor", "Malhotra", "Mehta", "Shah", "Desai", "Kulkarni", "Patil", "Deshpande",
    "Agarwal", "Mishra", "Saxena", "Tiwari", "Srivastava", "Chauhan"
]

DEPARTMENTS = {
    "Engineering": ["Software Engineer", "Senior Software Engineer", "Tech Lead", "Principal Engineer", "Engineering Manager"],
    "Human Resources": ["HR Executive", "HR Manager", "Talent Acquisition Specialist", "HR Business Partner"],
    "Finance": ["Accountant", "Senior Accountant", "Finance Manager", "Financial Analyst"],
    "Marketing": ["Marketing Executive", "Marketing Manager", "Digital Marketing Specialist", "Brand Manager"],
    "Sales": ["Sales Executive", "Sales Manager", "Business Development Manager", "Regional Sales Head"],
    "Operations": ["Operations Executive", "Operations Manager", "Process Analyst", "Quality Analyst"],
    "IT Support": ["IT Support Specialist", "System Administrator", "Network Engineer", "Help Desk Analyst"],
    "Legal": ["Legal Counsel", "Senior Legal Associate", "Compliance Officer"],
    "Administration": ["Admin Executive", "Office Manager", "Executive Assistant", "Facilities Coordinator"]
}

SALARY_RANGES = {
    "Executive": (25000, 45000),
    "Specialist": (40000, 70000),
    "Analyst": (45000, 75000),
    "Associate": (50000, 80000),
    "Manager": (80000, 150000),
    "Senior": (70000, 120000),
    "Lead": (100000, 180000),
    "Principal": (150000, 250000),
    "Head": (120000, 200000),
    "Director": (180000, 300000),
}

BANK_NAMES = [
    "State Bank of India", "HDFC Bank", "ICICI Bank", "Axis Bank",
    "Punjab National Bank", "Bank of Baroda", "Kotak Mahindra Bank", "Yes Bank"
]


def generate_employee_id():
    """Generate a unique employee ID."""
    return f"EMP{random.randint(10000, 99999)}"


def generate_pan():
    """Generate a sample PAN number."""
    letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    return f"{random.choice(letters)}{random.choice(letters)}{random.choice(letters)}P{random.choice(letters)}{random.randint(1000, 9999)}{random.choice(letters)}"


def generate_bank_account():
    """Generate a sample bank account number."""
    return f"{random.randint(100000000000, 999999999999)}"


def generate_ifsc():
    """Generate a sample IFSC code."""
    codes = ["SBIN", "HDFC", "ICIC", "UTIB", "PUNB", "BARB", "KKBK", "YESB"]
    return f"{random.choice(codes)}0{random.randint(10000, 99999)}"


def get_salary_for_designation(designation: str) -> float:
    """Get appropriate salary range based on designation."""
    for keyword, (min_sal, max_sal) in SALARY_RANGES.items():
        if keyword.lower() in designation.lower():
            return round(random.uniform(min_sal, max_sal), -2)  # Round to nearest 100
    # Default range
    return round(random.uniform(35000, 80000), -2)


def generate_employees(count: int = 30) -> list:
    """Generate sample employee records."""
    employees = []
    used_emails = set()
    
    for i in range(count):
        first_name = random.choice(FIRST_NAMES)
        last_name = random.choice(LAST_NAMES)
        full_name = f"{first_name} {last_name}"
        
        # Generate unique email
        base_email = f"{first_name.lower()}.{last_name.lower()}"
        email = f"{base_email}@company.com"
        counter = 1
        while email in used_emails:
            email = f"{base_email}{counter}@company.com"
            counter += 1
        used_emails.add(email)
        
        department = random.choice(list(DEPARTMENTS.keys()))
        designation = random.choice(DEPARTMENTS[department])
        
        # Random joining date (1-5 years ago)
        days_ago = random.randint(30, 1825)
        date_of_joining = (datetime.now() - timedelta(days=days_ago)).date()
        
        base_salary = get_salary_for_designation(designation)
        
        employee = {
            "employee_id": generate_employee_id(),
            "full_name": full_name,
            "email": email,
            "department": department,
            "designation": designation,
            "date_of_joining": date_of_joining.isoformat(),
            "employment_type": random.choices(
                ["full-time", "part-time", "contract"],
                weights=[85, 10, 5]
            )[0],
            "base_salary": base_salary,
            "hra_percentage": random.choice([30.0, 35.0, 40.0, 45.0, 50.0]),
            "da_percentage": random.choice([5.0, 8.0, 10.0, 12.0]),
            "special_allowance": round(random.uniform(0, base_salary * 0.15), -2),
            "pf_percentage": 12.0,
            "insurance_premium": random.choice([500.0, 750.0, 1000.0, 1500.0]),
            "tax_regime": random.choice(["old", "new"]),
            "bank_account": generate_bank_account(),
            "bank_name": random.choice(BANK_NAMES),
            "ifsc_code": generate_ifsc(),
            "pan_number": generate_pan(),
            "is_active": random.choices([True, False], weights=[95, 5])[0]
        }
        employees.append(employee)
    
    return employees


def generate_attendance_records(employees: list, months: int = 3) -> list:
    """Generate attendance records for employees for the past N months."""
    records = []
    current_date = datetime.now()
    
    for emp in employees:
        if not emp.get("is_active", True):
            continue
            
        for month_offset in range(months):
            # Calculate month and year
            target_date = current_date - timedelta(days=30 * month_offset)
            month = target_date.month
            year = target_date.year
            
            # Calculate working days in the month (assuming 22 working days avg)
            working_days = random.randint(20, 23)
            
            # Most employees have good attendance
            days_present = random.choices(
                [working_days, working_days - 1, working_days - 2, working_days - 3],
                weights=[60, 25, 10, 5]
            )[0]
            
            days_absent = working_days - days_present
            leave_days_paid = min(days_absent, random.randint(0, 2))
            leave_days_unpaid = days_absent - leave_days_paid
            
            # Overtime (some employees work extra hours)
            overtime_hours = random.choices(
                [0, random.uniform(2, 8), random.uniform(8, 20)],
                weights=[70, 20, 10]
            )[0]
            
            record = {
                "record_id": str(uuid.uuid4()),
                "employee_id": emp["employee_id"],
                "month": month,
                "year": year,
                "working_days": working_days,
                "days_present": days_present,
                "days_absent": days_absent,
                "leave_days_paid": leave_days_paid,
                "leave_days_unpaid": leave_days_unpaid,
                "overtime_hours": round(overtime_hours, 2),
                "late_arrivals": random.randint(0, 3)
            }
            records.append(record)
    
    return records


def seed_database():
    """Seed the database with sample data."""
    try:
        from db import supabase
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        logger.info("Please ensure SUPABASE_URL and SUPABASE_KEY are set in .env")
        sys.exit(1)
    
    logger.info("Generating synthetic employee data...")
    employees = generate_employees(30)
    
    logger.info("Generating attendance records...")
    attendance_records = generate_attendance_records(employees, months=3)
    
    # Insert employees
    logger.info(f"Inserting {len(employees)} employees...")
    try:
        # Insert in batches to avoid issues
        batch_size = 10
        for i in range(0, len(employees), batch_size):
            batch = employees[i:i+batch_size]
            result = supabase.table("employees").upsert(batch).execute()
            logger.info(f"  Inserted batch {i//batch_size + 1}")
    except Exception as e:
        logger.error(f"Failed to insert employees: {e}")
        logger.info("\nMake sure you've run the SQL from init_db.py first!")
        sys.exit(1)
    
    # Insert attendance records
    logger.info(f"Inserting {len(attendance_records)} attendance records...")
    try:
        batch_size = 20
        for i in range(0, len(attendance_records), batch_size):
            batch = attendance_records[i:i+batch_size]
            result = supabase.table("attendance_records").upsert(batch).execute()
            logger.info(f"  Inserted batch {i//batch_size + 1}")
    except Exception as e:
        logger.error(f"Failed to insert attendance records: {e}")
        sys.exit(1)
    
    logger.info("\n" + "=" * 60)
    logger.info("✓ Database seeded successfully!")
    logger.info(f"  - {len(employees)} employees created")
    logger.info(f"  - {len(attendance_records)} attendance records created")
    logger.info("=" * 60)
    
    # Show sample employees
    print("\nSample Employees Created:")
    print("-" * 80)
    for emp in employees[:5]:
        print(f"  {emp['employee_id']}: {emp['full_name']} | {emp['department']} | ₹{emp['base_salary']:,.0f}")
    print("  ...")


if __name__ == "__main__":
    seed_database()
