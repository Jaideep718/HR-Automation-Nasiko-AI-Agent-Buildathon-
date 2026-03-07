"""
Tools for the Payroll Automation Agent.
Provides payroll calculation, payslip generation, and reporting capabilities.
"""
import os
import uuid
import logging
from datetime import datetime, date
from typing import Dict, List, Any, Optional
from decimal import Decimal, ROUND_HALF_UP
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

# Try to initialize database connection
_DB_AVAILABLE = False
_DB_ERROR = None

try:
    from db import supabase, check_db_connection
    _DB_AVAILABLE = check_db_connection()
except Exception as e:
    _DB_ERROR = str(e)

# Tax slabs for New Tax Regime (FY 2025-26)
NEW_TAX_SLABS = [
    (300000, 0.00),      # 0-3L: No tax
    (700000, 0.05),      # 3L-7L: 5%
    (1000000, 0.10),     # 7L-10L: 10%
    (1200000, 0.15),     # 10L-12L: 15%
    (1500000, 0.20),     # 12L-15L: 20%
    (float('inf'), 0.30) # Above 15L: 30%
]

# Tax slabs for Old Tax Regime
OLD_TAX_SLABS = [
    (250000, 0.00),      # 0-2.5L: No tax
    (500000, 0.05),      # 2.5L-5L: 5%
    (1000000, 0.20),     # 5L-10L: 20%
    (float('inf'), 0.30) # Above 10L: 30%
]

MONTH_NAMES = {
    1: "January", 2: "February", 3: "March", 4: "April",
    5: "May", 6: "June", 7: "July", 8: "August",
    9: "September", 10: "October", 11: "November", 12: "December"
}


def calculate_income_tax(annual_income: float, tax_regime: str = "new") -> float:
    """Calculate income tax based on annual income and tax regime."""
    slabs = NEW_TAX_SLABS if tax_regime.lower() == "new" else OLD_TAX_SLABS
    
    tax = 0.0
    remaining_income = annual_income
    prev_limit = 0
    
    for limit, rate in slabs:
        if remaining_income <= 0:
            break
        taxable_in_slab = min(remaining_income, limit - prev_limit)
        tax += taxable_in_slab * rate
        remaining_income -= taxable_in_slab
        prev_limit = limit
    
    # Add 4% health and education cess
    tax = tax * 1.04
    
    return round(tax, 2)


def calculate_monthly_tax(annual_income: float, tax_regime: str = "new") -> float:
    """Calculate monthly income tax deduction (TDS)."""
    annual_tax = calculate_income_tax(annual_income, tax_regime)
    return round(annual_tax / 12, 2)


@tool
def get_employee_details(employee_id: str) -> str:
    """
    Retrieve employee details including salary structure.
    
    Args:
        employee_id: The unique employee ID (e.g., EMP12345)
    
    Returns:
        Employee details including name, department, salary structure, and deduction settings.
    """
    if not _DB_AVAILABLE:
        return f"Database connection unavailable: {_DB_ERROR}"
    
    try:
        result = supabase.table("employees").select("*").eq("employee_id", employee_id).execute()
        
        if not result.data:
            return f"Employee with ID '{employee_id}' not found."
        
        emp = result.data[0]
        
        # Calculate derived values
        base = float(emp['base_salary'])
        hra = base * float(emp['hra_percentage']) / 100
        da = base * float(emp['da_percentage']) / 100
        special = float(emp.get('special_allowance', 0))
        gross = base + hra + da + special
        
        return f"""
📋 **Employee Details**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
**ID:** {emp['employee_id']}
**Name:** {emp['full_name']}
**Email:** {emp['email']}
**Department:** {emp['department']}
**Designation:** {emp['designation']}
**Date of Joining:** {emp['date_of_joining']}
**Employment Type:** {emp['employment_type'].title()}
**Status:** {'Active' if emp['is_active'] else 'Inactive'}

💰 **Salary Structure (Monthly)**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Base Salary: ₹{base:,.2f}
• HRA ({emp['hra_percentage']}%): ₹{hra:,.2f}
• DA ({emp['da_percentage']}%): ₹{da:,.2f}
• Special Allowance: ₹{special:,.2f}
• **Gross Salary:** ₹{gross:,.2f}

📉 **Deduction Settings**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• PF Contribution: {emp['pf_percentage']}%
• Insurance Premium: ₹{emp['insurance_premium']}
• Tax Regime: {emp['tax_regime'].title()}

🏦 **Bank Details**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Bank: {emp.get('bank_name', 'Not provided')}
• Account: {emp.get('bank_account', 'Not provided')[-4:].rjust(len(emp.get('bank_account', '****')), '*') if emp.get('bank_account') else 'Not provided'}
• PAN: {emp.get('pan_number', 'Not provided')}
"""
    except Exception as e:
        logger.error(f"Error fetching employee details: {e}")
        return f"Error retrieving employee details: {str(e)}"


@tool
def list_employees(department: Optional[str] = None, active_only: bool = True) -> str:
    """
    List all employees, optionally filtered by department.
    
    Args:
        department: Filter by department name (e.g., Engineering, Finance). Leave empty for all.
        active_only: If True, only show active employees.
    
    Returns:
        List of employees with basic details.
    """
    if not _DB_AVAILABLE:
        return f"Database connection unavailable: {_DB_ERROR}"
    
    try:
        query = supabase.table("employees").select("employee_id, full_name, department, designation, base_salary, is_active")
        
        if department:
            query = query.ilike("department", f"%{department}%")
        
        if active_only:
            query = query.eq("is_active", True)
        
        result = query.order("department").execute()
        
        if not result.data:
            return "No employees found matching the criteria."
        
        # Group by department
        by_dept = {}
        for emp in result.data:
            dept = emp['department']
            if dept not in by_dept:
                by_dept[dept] = []
            by_dept[dept].append(emp)
        
        output = f"👥 **Employee List** ({len(result.data)} employees)\n"
        output += "━" * 50 + "\n\n"
        
        for dept, employees in sorted(by_dept.items()):
            output += f"**{dept}** ({len(employees)} employees)\n"
            for emp in employees:
                status = "✓" if emp['is_active'] else "✗"
                output += f"  {status} {emp['employee_id']}: {emp['full_name']} - {emp['designation']} (₹{float(emp['base_salary']):,.0f})\n"
            output += "\n"
        
        return output
    except Exception as e:
        logger.error(f"Error listing employees: {e}")
        return f"Error listing employees: {str(e)}"


@tool
def calculate_payroll(employee_id: str, month: int, year: int, overtime_hours: float = 0.0, bonus: float = 0.0) -> str:
    """
    Calculate payroll for a specific employee for a given month.
    
    Args:
        employee_id: The employee ID
        month: Month (1-12)
        year: Year (e.g., 2026)
        overtime_hours: Additional overtime hours to consider
        bonus: Any bonus amount to include
    
    Returns:
        Detailed payroll calculation showing earnings, deductions, and net salary.
    """
    if not _DB_AVAILABLE:
        return f"Database connection unavailable: {_DB_ERROR}"
    
    if month < 1 or month > 12:
        return "Invalid month. Please provide a value between 1 and 12."
    
    try:
        # Get employee details
        emp_result = supabase.table("employees").select("*").eq("employee_id", employee_id).execute()
        
        if not emp_result.data:
            return f"Employee with ID '{employee_id}' not found."
        
        emp = emp_result.data[0]
        
        if not emp['is_active']:
            return f"Employee {emp['full_name']} is not active. Cannot process payroll."
        
        # Get attendance record for the month
        att_result = supabase.table("attendance_records").select("*").eq("employee_id", employee_id).eq("month", month).eq("year", year).execute()
        
        attendance = att_result.data[0] if att_result.data else None
        
        # Base calculations
        base_salary = float(emp['base_salary'])
        hra = base_salary * float(emp['hra_percentage']) / 100
        da = base_salary * float(emp['da_percentage']) / 100
        special_allowance = float(emp.get('special_allowance', 0))
        
        # Attendance-based calculations
        working_days = 22  # Default
        effective_days = working_days
        unpaid_leave_days = 0
        att_overtime = 0.0
        
        if attendance:
            working_days = attendance['working_days']
            unpaid_leave_days = attendance.get('leave_days_unpaid', 0)
            effective_days = attendance['days_present'] + attendance.get('leave_days_paid', 0)
            att_overtime = float(attendance.get('overtime_hours', 0))
        
        # Per-day salary for deductions
        per_day_salary = (base_salary + hra + da) / working_days
        unpaid_leave_deduction = per_day_salary * unpaid_leave_days
        
        # Overtime calculation (1.5x hourly rate)
        total_overtime = att_overtime + overtime_hours
        hourly_rate = base_salary / (working_days * 8)
        overtime_pay = total_overtime * hourly_rate * 1.5
        
        # Gross salary
        gross_salary = base_salary + hra + da + special_allowance + overtime_pay + bonus
        
        # Deductions
        pf_deduction = base_salary * float(emp['pf_percentage']) / 100
        insurance = float(emp.get('insurance_premium', 500))
        
        # Annual income estimation for tax calculation
        annual_gross = (gross_salary - unpaid_leave_deduction) * 12
        annual_pf = pf_deduction * 12
        taxable_income = annual_gross - annual_pf - 50000  # Standard deduction
        monthly_tax = calculate_monthly_tax(taxable_income, emp.get('tax_regime', 'new'))
        
        total_deductions = pf_deduction + insurance + monthly_tax + unpaid_leave_deduction
        net_salary = gross_salary - total_deductions
        
        month_name = MONTH_NAMES.get(month, str(month))
        
        return f"""
💵 **PAYROLL CALCULATION**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
**Employee:** {emp['full_name']} ({employee_id})
**Department:** {emp['department']}
**Pay Period:** {month_name} {year}

📊 **Attendance Summary**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
• Working Days: {working_days}
• Days Worked: {effective_days}
• Unpaid Leave: {unpaid_leave_days} days
• Overtime Hours: {total_overtime:.1f} hrs

💰 **EARNINGS**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Basic Salary:         ₹{base_salary:>12,.2f}
  HRA:                  ₹{hra:>12,.2f}
  DA:                   ₹{da:>12,.2f}
  Special Allowance:    ₹{special_allowance:>12,.2f}
  Overtime Pay:         ₹{overtime_pay:>12,.2f}
  Bonus:                ₹{bonus:>12,.2f}
  ─────────────────────────────────────────
  **Gross Salary:**     ₹{gross_salary:>12,.2f}

📉 **DEDUCTIONS**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Provident Fund (PF):  ₹{pf_deduction:>12,.2f}
  Income Tax (TDS):     ₹{monthly_tax:>12,.2f}
  Insurance Premium:    ₹{insurance:>12,.2f}
  Unpaid Leave:         ₹{unpaid_leave_deduction:>12,.2f}
  ─────────────────────────────────────────
  **Total Deductions:** ₹{total_deductions:>12,.2f}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ **NET SALARY:**      ₹{net_salary:>12,.2f}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
    except Exception as e:
        logger.error(f"Error calculating payroll: {e}")
        return f"Error calculating payroll: {str(e)}"


@tool
def process_department_payroll(department: str, month: int, year: int) -> str:
    """
    Process payroll for all employees in a department.
    
    Args:
        department: Department name (e.g., Engineering, Finance)
        month: Month (1-12)
        year: Year (e.g., 2026)
    
    Returns:
        Summary of payroll processing for the department.
    """
    if not _DB_AVAILABLE:
        return f"Database connection unavailable: {_DB_ERROR}"
    
    if month < 1 or month > 12:
        return "Invalid month. Please provide a value between 1 and 12."
    
    try:
        # Get all active employees in the department
        emp_result = supabase.table("employees").select("*").ilike("department", f"%{department}%").eq("is_active", True).execute()
        
        if not emp_result.data:
            return f"No active employees found in department '{department}'."
        
        employees = emp_result.data
        month_name = MONTH_NAMES.get(month, str(month))
        
        total_gross = 0.0
        total_deductions = 0.0
        total_net = 0.0
        processed = []
        
        for emp in employees:
            # Get attendance
            att_result = supabase.table("attendance_records").select("*").eq("employee_id", emp['employee_id']).eq("month", month).eq("year", year).execute()
            attendance = att_result.data[0] if att_result.data else None
            
            # Calculate payroll
            base_salary = float(emp['base_salary'])
            hra = base_salary * float(emp['hra_percentage']) / 100
            da = base_salary * float(emp['da_percentage']) / 100
            special = float(emp.get('special_allowance', 0))
            
            working_days = 22
            unpaid_leave_days = 0
            overtime_hours = 0.0
            
            if attendance:
                working_days = attendance['working_days']
                unpaid_leave_days = attendance.get('leave_days_unpaid', 0)
                overtime_hours = float(attendance.get('overtime_hours', 0))
            
            per_day = (base_salary + hra + da) / working_days
            unpaid_ded = per_day * unpaid_leave_days
            
            hourly = base_salary / (working_days * 8)
            overtime_pay = overtime_hours * hourly * 1.5
            
            gross = base_salary + hra + da + special + overtime_pay
            
            pf = base_salary * float(emp['pf_percentage']) / 100
            insurance = float(emp.get('insurance_premium', 500))
            
            annual_gross = (gross - unpaid_ded) * 12
            annual_pf = pf * 12
            taxable = annual_gross - annual_pf - 50000
            tax = calculate_monthly_tax(taxable, emp.get('tax_regime', 'new'))
            
            deductions = pf + insurance + tax + unpaid_ded
            net = gross - deductions
            
            total_gross += gross
            total_deductions += deductions
            total_net += net
            
            # Create payroll record
            payroll_id = str(uuid.uuid4())
            payroll_record = {
                "payroll_id": payroll_id,
                "employee_id": emp['employee_id'],
                "month": month,
                "year": year,
                "basic_salary": base_salary,
                "hra": hra,
                "da": da,
                "special_allowance": special,
                "overtime_pay": overtime_pay,
                "bonus": 0,
                "gross_salary": gross,
                "pf_deduction": pf,
                "income_tax": tax,
                "insurance": insurance,
                "unpaid_leave_ded": unpaid_ded,
                "total_deductions": deductions,
                "net_salary": net,
                "status": "processed"
            }
            
            try:
                supabase.table("payroll_records").upsert(payroll_record, on_conflict="employee_id,month,year").execute()
            except:
                pass  # Ignore duplicates
            
            processed.append({
                "id": emp['employee_id'],
                "name": emp['full_name'],
                "gross": gross,
                "deductions": deductions,
                "net": net
            })
        
        output = f"""
📊 **DEPARTMENT PAYROLL SUMMARY**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
**Department:** {department}
**Pay Period:** {month_name} {year}
**Employees Processed:** {len(processed)}

👥 **Employee Breakdown**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        for p in processed:
            output += f"  • {p['id']}: {p['name'][:20]:<20} | Net: ₹{p['net']:>10,.2f}\n"
        
        output += f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💰 **DEPARTMENT TOTALS**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Total Gross Salary:   ₹{total_gross:>14,.2f}
  Total Deductions:     ₹{total_deductions:>14,.2f}
  ─────────────────────────────────────────────
  **Total Net Payout:** ₹{total_net:>14,.2f}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ Payroll records created/updated for {len(processed)} employees.
"""
        return output
    except Exception as e:
        logger.error(f"Error processing department payroll: {e}")
        return f"Error processing payroll: {str(e)}"


@tool
def generate_payslip(employee_id: str, month: int, year: int) -> str:
    """
    Generate a detailed payslip for an employee.
    
    Args:
        employee_id: The employee ID
        month: Month (1-12)
        year: Year (e.g., 2026)
    
    Returns:
        Formatted payslip document.
    """
    if not _DB_AVAILABLE:
        return f"Database connection unavailable: {_DB_ERROR}"
    
    try:
        # Get payroll record
        payroll_result = supabase.table("payroll_records").select("*").eq("employee_id", employee_id).eq("month", month).eq("year", year).execute()
        
        # Get employee details
        emp_result = supabase.table("employees").select("*").eq("employee_id", employee_id).execute()
        
        if not emp_result.data:
            return f"Employee with ID '{employee_id}' not found."
        
        emp = emp_result.data[0]
        month_name = MONTH_NAMES.get(month, str(month))
        
        # Use existing payroll record or calculate fresh
        if payroll_result.data:
            p = payroll_result.data[0]
            basic = float(p['basic_salary'])
            hra = float(p['hra'])
            da = float(p['da'])
            special = float(p['special_allowance'])
            overtime = float(p['overtime_pay'])
            bonus = float(p['bonus'])
            gross = float(p['gross_salary'])
            pf = float(p['pf_deduction'])
            tax = float(p['income_tax'])
            insurance = float(p['insurance'])
            unpaid_ded = float(p['unpaid_leave_ded'])
            total_ded = float(p['total_deductions'])
            net = float(p['net_salary'])
        else:
            # Calculate fresh
            basic = float(emp['base_salary'])
            hra = basic * float(emp['hra_percentage']) / 100
            da = basic * float(emp['da_percentage']) / 100
            special = float(emp.get('special_allowance', 0))
            overtime = 0.0
            bonus = 0.0
            gross = basic + hra + da + special
            pf = basic * float(emp['pf_percentage']) / 100
            insurance = float(emp.get('insurance_premium', 500))
            annual = gross * 12 - pf * 12 - 50000
            tax = calculate_monthly_tax(annual, emp.get('tax_regime', 'new'))
            unpaid_ded = 0.0
            total_ded = pf + insurance + tax
            net = gross - total_ded
        
        # Generate payslip number
        payslip_number = f"PS-{year}{month:02d}-{employee_id}"
        today = datetime.now().strftime("%d-%b-%Y")
        
        # Create payslip record
        payslip_id = str(uuid.uuid4())
        try:
            supabase.table("payslips").upsert({
                "payslip_id": payslip_id,
                "payroll_id": payroll_result.data[0]['payroll_id'] if payroll_result.data else None,
                "employee_id": employee_id,
                "month": month,
                "year": year,
                "payslip_number": payslip_number
            }, on_conflict="payslip_number").execute()
        except:
            pass
        
        payslip = f"""
╔══════════════════════════════════════════════════════════════════╗
║                     🏢 COMPANY NAME PVT. LTD.                    ║
║                          SALARY SLIP                              ║
╠══════════════════════════════════════════════════════════════════╣
║  Payslip No: {payslip_number:<20}  Generated: {today:<15} ║
║  Pay Period: {month_name} {year}                                          ║
╠══════════════════════════════════════════════════════════════════╣
║  EMPLOYEE DETAILS                                                 ║
║  ────────────────────────────────────────────────────────────     ║
║  Employee ID:   {emp['employee_id']:<20}                          ║
║  Name:          {emp['full_name']:<35}                 ║
║  Department:    {emp['department']:<25}                       ║
║  Designation:   {emp['designation']:<30}                  ║
║  PAN:           {emp.get('pan_number', 'N/A'):<20}                          ║
╠══════════════════════════════════════════════════════════════════╣
║              EARNINGS              ║           DEDUCTIONS          ║
║  ────────────────────────────────  ║  ──────────────────────────── ║
║  Basic Salary:    ₹{basic:>10,.2f}  ║  Provident Fund: ₹{pf:>10,.2f} ║
║  HRA:             ₹{hra:>10,.2f}  ║  Income Tax:     ₹{tax:>10,.2f} ║
║  DA:              ₹{da:>10,.2f}  ║  Insurance:      ₹{insurance:>10,.2f} ║
║  Special Allow.:  ₹{special:>10,.2f}  ║  Unpaid Leave:   ₹{unpaid_ded:>10,.2f} ║
║  Overtime:        ₹{overtime:>10,.2f}  ║                               ║
║  Bonus:           ₹{bonus:>10,.2f}  ║                               ║
║  ────────────────────────────────  ║  ──────────────────────────── ║
║  GROSS EARNINGS:  ₹{gross:>10,.2f}  ║  TOTAL DEDUCTIONS:₹{total_ded:>10,.2f}║
╠══════════════════════════════════════════════════════════════════╣
║                                                                   ║
║     ★ ★ ★   NET SALARY: ₹{net:>12,.2f}   ★ ★ ★              ║
║                                                                   ║
╠══════════════════════════════════════════════════════════════════╣
║  BANK DETAILS                                                     ║
║  ────────────────────────────────────────────────────────────     ║
║  Bank Name:      {emp.get('bank_name', 'N/A'):<30}               ║
║  Account No:     {'*' * 8 + emp.get('bank_account', '')[-4:] if emp.get('bank_account') else 'N/A':<20}                          ║
║  IFSC Code:      {emp.get('ifsc_code', 'N/A'):<20}                          ║
╠══════════════════════════════════════════════════════════════════╣
║  This is a computer-generated document.                          ║
║  For queries, contact HR at hr@company.com                        ║
╚══════════════════════════════════════════════════════════════════╝
"""
        return payslip
    except Exception as e:
        logger.error(f"Error generating payslip: {e}")
        return f"Error generating payslip: {str(e)}"


@tool
def get_payroll_summary(month: int, year: int) -> str:
    """
    Get a summary of payroll for all departments for a given month.
    
    Args:
        month: Month (1-12)
        year: Year (e.g., 2026)
    
    Returns:
        Company-wide payroll summary with department breakdown.
    """
    if not _DB_AVAILABLE:
        return f"Database connection unavailable: {_DB_ERROR}"
    
    try:
        # Get all payroll records for the month
        payroll_result = supabase.table("payroll_records").select("*").eq("month", month).eq("year", year).execute()
        
        month_name = MONTH_NAMES.get(month, str(month))
        
        if not payroll_result.data:
            return f"No payroll records found for {month_name} {year}. Please run payroll processing first."
        
        # Get employee details for department info
        emp_ids = [p['employee_id'] for p in payroll_result.data]
        emp_result = supabase.table("employees").select("employee_id, department").in_("employee_id", emp_ids).execute()
        
        emp_dept = {e['employee_id']: e['department'] for e in emp_result.data}
        
        # Aggregate by department
        dept_summary = {}
        total_gross = 0.0
        total_deductions = 0.0
        total_net = 0.0
        
        for p in payroll_result.data:
            dept = emp_dept.get(p['employee_id'], 'Unknown')
            if dept not in dept_summary:
                dept_summary[dept] = {'count': 0, 'gross': 0.0, 'deductions': 0.0, 'net': 0.0}
            
            gross = float(p['gross_salary'])
            deductions = float(p['total_deductions'])
            net = float(p['net_salary'])
            
            dept_summary[dept]['count'] += 1
            dept_summary[dept]['gross'] += gross
            dept_summary[dept]['deductions'] += deductions
            dept_summary[dept]['net'] += net
            
            total_gross += gross
            total_deductions += deductions
            total_net += net
        
        output = f"""
📊 **COMPANY PAYROLL SUMMARY**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
**Pay Period:** {month_name} {year}
**Total Employees:** {len(payroll_result.data)}
**Total Departments:** {len(dept_summary)}

📋 **Department-wise Breakdown**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
        for dept, data in sorted(dept_summary.items()):
            output += f"""
**{dept}** ({data['count']} employees)
  Gross: ₹{data['gross']:>12,.2f} | Deductions: ₹{data['deductions']:>10,.2f} | Net: ₹{data['net']:>12,.2f}
"""
        
        output += f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
💰 **COMPANY TOTALS**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Total Gross Payroll:    ₹{total_gross:>14,.2f}
  Total Deductions:       ₹{total_deductions:>14,.2f}
  ─────────────────────────────────────────────
  **Total Net Payout:**   ₹{total_net:>14,.2f}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📈 **Quick Stats**
  • Average Net Salary: ₹{total_net/len(payroll_result.data):,.2f}
  • Highest Department Cost: {max(dept_summary.items(), key=lambda x: x[1]['net'])[0]}
  • Payroll processed: {sum(1 for p in payroll_result.data if p['status'] == 'processed')}/{len(payroll_result.data)}
"""
        return output
    except Exception as e:
        logger.error(f"Error getting payroll summary: {e}")
        return f"Error getting payroll summary: {str(e)}"


@tool
def add_bonus_or_adjustment(employee_id: str, month: int, year: int, bonus: float = 0.0, adjustment_type: str = "bonus", remarks: str = "") -> str:
    """
    Add a bonus or adjustment to an employee's payroll.
    
    Args:
        employee_id: The employee ID
        month: Month (1-12)
        year: Year (e.g., 2026)
        bonus: The bonus or adjustment amount (positive for bonus, negative for deduction)
        adjustment_type: Type of adjustment (bonus, overtime, adjustment, deduction)
        remarks: Reason for the adjustment
    
    Returns:
        Confirmation of the adjustment applied.
    """
    if not _DB_AVAILABLE:
        return f"Database connection unavailable: {_DB_ERROR}"
    
    try:
        # Check if payroll record exists
        payroll_result = supabase.table("payroll_records").select("*").eq("employee_id", employee_id).eq("month", month).eq("year", year).execute()
        
        # Get employee details
        emp_result = supabase.table("employees").select("full_name").eq("employee_id", employee_id).execute()
        
        if not emp_result.data:
            return f"Employee with ID '{employee_id}' not found."
        
        emp_name = emp_result.data[0]['full_name']
        month_name = MONTH_NAMES.get(month, str(month))
        
        if not payroll_result.data:
            return f"No payroll record found for {emp_name} for {month_name} {year}. Please process payroll first."
        
        payroll = payroll_result.data[0]
        
        # Update the payroll record
        current_bonus = float(payroll.get('bonus', 0))
        current_other_deductions = float(payroll.get('other_deductions', 0))
        current_gross = float(payroll['gross_salary'])
        current_deductions = float(payroll['total_deductions'])
        
        if adjustment_type.lower() in ['bonus', 'overtime']:
            new_bonus = current_bonus + bonus
            new_gross = current_gross + bonus
            new_net = new_gross - current_deductions
            update_data = {
                'bonus': new_bonus,
                'gross_salary': new_gross,
                'net_salary': new_net,
                'remarks': f"{payroll.get('remarks', '')} | {adjustment_type}: ₹{bonus} - {remarks}".strip(' |')
            }
        else:  # deduction or adjustment
            new_other_ded = current_other_deductions + abs(bonus)
            new_deductions = current_deductions + abs(bonus)
            new_net = current_gross - new_deductions
            update_data = {
                'other_deductions': new_other_ded,
                'total_deductions': new_deductions,
                'net_salary': new_net,
                'remarks': f"{payroll.get('remarks', '')} | {adjustment_type}: ₹{bonus} - {remarks}".strip(' |')
            }
        
        supabase.table("payroll_records").update(update_data).eq("payroll_id", payroll['payroll_id']).execute()
        
        return f"""
✅ **Adjustment Applied Successfully**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
**Employee:** {emp_name} ({employee_id})
**Pay Period:** {month_name} {year}
**Adjustment Type:** {adjustment_type.title()}
**Amount:** ₹{bonus:,.2f}
**Remarks:** {remarks if remarks else 'N/A'}

Updated net salary: ₹{update_data['net_salary']:,.2f}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
    except Exception as e:
        logger.error(f"Error adding adjustment: {e}")
        return f"Error adding adjustment: {str(e)}"


@tool
def get_payroll_status(employee_id: Optional[str] = None, month: Optional[int] = None, year: Optional[int] = None) -> str:
    """
    Check the status of payroll records.
    
    Args:
        employee_id: Optional employee ID to filter
        month: Optional month to filter (1-12)
        year: Optional year to filter
    
    Returns:
        Payroll status information.
    """
    if not _DB_AVAILABLE:
        return f"Database connection unavailable: {_DB_ERROR}"
    
    try:
        query = supabase.table("payroll_records").select("*, employees(full_name, department)")
        
        if employee_id:
            query = query.eq("employee_id", employee_id)
        if month:
            query = query.eq("month", month)
        if year:
            query = query.eq("year", year)
        
        result = query.order("year", desc=True).order("month", desc=True).limit(50).execute()
        
        if not result.data:
            return "No payroll records found matching the criteria."
        
        output = "📋 **Payroll Status Report**\n"
        output += "━" * 70 + "\n\n"
        
        # Group by status
        status_counts = {'pending': 0, 'processed': 0, 'paid': 0, 'on_hold': 0}
        
        for record in result.data:
            status = record['status']
            status_counts[status] = status_counts.get(status, 0) + 1
            
            emp_name = record['employees']['full_name'] if record.get('employees') else record['employee_id']
            month_name = MONTH_NAMES.get(record['month'], str(record['month']))
            
            status_icon = {'pending': '🟡', 'processed': '🟢', 'paid': '✅', 'on_hold': '🔴'}.get(status, '⚪')
            
            output += f"{status_icon} {record['employee_id']}: {emp_name[:25]:<25} | {month_name} {record['year']} | ₹{float(record['net_salary']):>10,.2f} | {status.upper()}\n"
        
        output += "\n" + "━" * 70 + "\n"
        output += "**Summary:** "
        output += " | ".join([f"{k.title()}: {v}" for k, v in status_counts.items() if v > 0])
        
        return output
    except Exception as e:
        logger.error(f"Error getting payroll status: {e}")
        return f"Error getting payroll status: {str(e)}"


@tool
def list_departments() -> str:
    """
    List all departments with employee counts.
    
    Returns:
        List of departments and their employee counts.
    """
    if not _DB_AVAILABLE:
        return f"Database connection unavailable: {_DB_ERROR}"
    
    try:
        result = supabase.table("employees").select("department, is_active").execute()
        
        if not result.data:
            return "No employees found in the database."
        
        dept_counts = {}
        for emp in result.data:
            dept = emp['department']
            if dept not in dept_counts:
                dept_counts[dept] = {'active': 0, 'inactive': 0}
            if emp['is_active']:
                dept_counts[dept]['active'] += 1
            else:
                dept_counts[dept]['inactive'] += 1
        
        output = "🏢 **Departments Overview**\n"
        output += "━" * 50 + "\n\n"
        
        total_active = 0
        for dept, counts in sorted(dept_counts.items()):
            total_active += counts['active']
            output += f"  • **{dept}**: {counts['active']} active"
            if counts['inactive']:
                output += f" ({counts['inactive']} inactive)"
            output += "\n"
        
        output += "\n" + "━" * 50 + "\n"
        output += f"**Total Active Employees:** {total_active}"
        
        return output
    except Exception as e:
        logger.error(f"Error listing departments: {e}")
        return f"Error listing departments: {str(e)}"
