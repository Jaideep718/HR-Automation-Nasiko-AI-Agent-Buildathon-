from supabase import create_client
from dotenv import load_dotenv
from datetime import datetime
import os

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ----------------------------
# Clear old data
# ----------------------------

supabase.table("leave_requests").delete().neq("id", 0).execute()
supabase.table("employees").delete().neq("email", "").execute()

print("Old rows deleted")

# ----------------------------
# Insert employees
# ----------------------------

employees = [
    {"name": "alice", "working_days": 18, "absent_days": 2, "email": "alice@company.com"},
    {"name": "bob", "working_days": 17, "absent_days": 4, "email": "bob@company.com"},
    {"name": "charlie", "working_days": 20, "absent_days": 1, "email": "charlie@company.com"},
    {"name": "rishi", "working_days": 19, "absent_days": 0, "email": "mc23bt003@iitdh.ac.in"},
    {"name": "srinivas", "working_days": 21, "absent_days": 1, "email": "mc23bt004@iitdh.ac.in"},
    {"name": "jaideep", "working_days": 16, "absent_days": 3, "email": "mc23bt005@iitdh.ac.in"},
    {"name": "rishi", "working_days": 20, "absent_days": 0, "email": "dksrishi007@gmail.com"}
]

supabase.table("employees").insert(employees).execute()

print("Employees inserted")

# ----------------------------
# Insert leave requests
# ----------------------------

leave_requests = [
    {"employee_email": "alice@company.com", "days": 2, "status": "pending","created_at": datetime.utcnow().isoformat()},
    {"employee_email": "bob@company.com", "days": 1, "status": "pending","created_at": datetime.utcnow().isoformat()},
    {"employee_email": "dksrishi007@gmail.com", "days": 2, "status": "pending","created_at": datetime.utcnow().isoformat()},
    {"employee_email": "mc23bt003@iitdh.ac.in", "days": 1, "status": "pending","created_at": datetime.utcnow().isoformat()}
]

supabase.table("leave_requests").insert(leave_requests).execute()

print("Leave requests inserted")

print("Database seeded successfully.")