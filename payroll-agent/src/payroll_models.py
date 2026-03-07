"""
Schema reference for Payroll Automation Agent tables.
The actual tables live in Supabase. Run init_db.py for the SQL to create them.
"""

# =============================================================================
# EMPLOYEES TABLE
# =============================================================================
# employee_id       VARCHAR(50)   PRIMARY KEY
# full_name         VARCHAR(255)  NOT NULL
# email             VARCHAR(255)  UNIQUE NOT NULL
# department        VARCHAR(100)  NOT NULL
# designation       VARCHAR(100)  NOT NULL
# date_of_joining   DATE          NOT NULL
# employment_type   VARCHAR(50)   DEFAULT 'full-time'  -- full-time | part-time | contract
# base_salary       DECIMAL(12,2) NOT NULL
# hra_percentage    DECIMAL(5,2)  DEFAULT 40.00  -- House Rent Allowance %
# da_percentage     DECIMAL(5,2)  DEFAULT 10.00  -- Dearness Allowance %
# special_allowance DECIMAL(12,2) DEFAULT 0.00
# pf_percentage     DECIMAL(5,2)  DEFAULT 12.00  -- Provident Fund %
# insurance_premium DECIMAL(12,2) DEFAULT 500.00
# tax_regime        VARCHAR(20)   DEFAULT 'new'  -- old | new
# bank_account      VARCHAR(50)
# bank_name         VARCHAR(100)
# ifsc_code         VARCHAR(20)
# pan_number        VARCHAR(20)
# is_active         BOOLEAN       DEFAULT TRUE
# created_at        TIMESTAMPTZ   DEFAULT NOW()
# updated_at        TIMESTAMPTZ   DEFAULT NOW()

# =============================================================================
# ATTENDANCE_RECORDS TABLE (for payroll calculations)
# =============================================================================
# record_id         VARCHAR(50)   PRIMARY KEY
# employee_id       VARCHAR(50)   REFERENCES employees(employee_id)
# month             INTEGER       NOT NULL  -- 1-12
# year              INTEGER       NOT NULL
# working_days      INTEGER       NOT NULL
# days_present      INTEGER       NOT NULL
# days_absent       INTEGER       DEFAULT 0
# leave_days_paid   INTEGER       DEFAULT 0
# leave_days_unpaid INTEGER       DEFAULT 0
# overtime_hours    DECIMAL(6,2)  DEFAULT 0.00
# late_arrivals     INTEGER       DEFAULT 0
# created_at        TIMESTAMPTZ   DEFAULT NOW()

# =============================================================================
# PAYROLL_RECORDS TABLE
# =============================================================================
# payroll_id        VARCHAR(50)   PRIMARY KEY
# employee_id       VARCHAR(50)   REFERENCES employees(employee_id)
# month             INTEGER       NOT NULL
# year              INTEGER       NOT NULL
# payroll_cycle     VARCHAR(20)   DEFAULT 'monthly'
# -- Earnings
# basic_salary      DECIMAL(12,2) NOT NULL
# hra               DECIMAL(12,2) DEFAULT 0.00
# da                DECIMAL(12,2) DEFAULT 0.00
# special_allowance DECIMAL(12,2) DEFAULT 0.00
# overtime_pay      DECIMAL(12,2) DEFAULT 0.00
# bonus             DECIMAL(12,2) DEFAULT 0.00
# other_earnings    DECIMAL(12,2) DEFAULT 0.00
# gross_salary      DECIMAL(12,2) NOT NULL
# -- Deductions
# pf_deduction      DECIMAL(12,2) DEFAULT 0.00
# income_tax        DECIMAL(12,2) DEFAULT 0.00
# insurance         DECIMAL(12,2) DEFAULT 0.00
# unpaid_leave_ded  DECIMAL(12,2) DEFAULT 0.00
# other_deductions  DECIMAL(12,2) DEFAULT 0.00
# total_deductions  DECIMAL(12,2) DEFAULT 0.00
# -- Net
# net_salary        DECIMAL(12,2) NOT NULL
# -- Status
# status            VARCHAR(20)   DEFAULT 'pending'  -- pending | processed | paid | on_hold
# payment_date      DATE
# payment_mode      VARCHAR(50)   DEFAULT 'bank_transfer'
# remarks           TEXT
# created_at        TIMESTAMPTZ   DEFAULT NOW()
# updated_at        TIMESTAMPTZ   DEFAULT NOW()

# =============================================================================
# PAYSLIPS TABLE
# =============================================================================
# payslip_id        VARCHAR(50)   PRIMARY KEY
# payroll_id        VARCHAR(50)   REFERENCES payroll_records(payroll_id)
# employee_id       VARCHAR(50)   REFERENCES employees(employee_id)
# month             INTEGER       NOT NULL
# year              INTEGER       NOT NULL
# payslip_number    VARCHAR(50)   UNIQUE NOT NULL
# generated_at      TIMESTAMPTZ   DEFAULT NOW()
# emailed           BOOLEAN       DEFAULT FALSE
# emailed_at        TIMESTAMPTZ

TABLE_NAMES = {
    "employees": "employees",
    "attendance_records": "attendance_records",
    "payroll_records": "payroll_records",
    "payslips": "payslips"
}

VALID_EMPLOYMENT_TYPES = ["full-time", "part-time", "contract"]
VALID_TAX_REGIMES = ["old", "new"]
VALID_PAYROLL_STATUS = ["pending", "processed", "paid", "on_hold"]
VALID_PAYMENT_MODES = ["bank_transfer", "cheque", "cash"]

DEPARTMENTS = [
    "Engineering", "Human Resources", "Finance", "Marketing",
    "Sales", "Operations", "IT Support", "Legal", "Administration"
]

CREATE_TABLES_SQL = """
-- Employees Table
CREATE TABLE IF NOT EXISTS employees (
    employee_id       VARCHAR(50)   PRIMARY KEY,
    full_name         VARCHAR(255)  NOT NULL,
    email             VARCHAR(255)  UNIQUE NOT NULL,
    department        VARCHAR(100)  NOT NULL,
    designation       VARCHAR(100)  NOT NULL,
    date_of_joining   DATE          NOT NULL,
    employment_type   VARCHAR(50)   DEFAULT 'full-time',
    base_salary       DECIMAL(12,2) NOT NULL,
    hra_percentage    DECIMAL(5,2)  DEFAULT 40.00,
    da_percentage     DECIMAL(5,2)  DEFAULT 10.00,
    special_allowance DECIMAL(12,2) DEFAULT 0.00,
    pf_percentage     DECIMAL(5,2)  DEFAULT 12.00,
    insurance_premium DECIMAL(12,2) DEFAULT 500.00,
    tax_regime        VARCHAR(20)   DEFAULT 'new',
    bank_account      VARCHAR(50),
    bank_name         VARCHAR(100),
    ifsc_code         VARCHAR(20),
    pan_number        VARCHAR(20),
    is_active         BOOLEAN       DEFAULT TRUE,
    created_at        TIMESTAMPTZ   DEFAULT NOW(),
    updated_at        TIMESTAMPTZ   DEFAULT NOW()
);

-- Attendance Records Table
CREATE TABLE IF NOT EXISTS attendance_records (
    record_id         VARCHAR(50)   PRIMARY KEY,
    employee_id       VARCHAR(50)   REFERENCES employees(employee_id) ON DELETE CASCADE,
    month             INTEGER       NOT NULL CHECK (month >= 1 AND month <= 12),
    year              INTEGER       NOT NULL CHECK (year >= 2020),
    working_days      INTEGER       NOT NULL,
    days_present      INTEGER       NOT NULL,
    days_absent       INTEGER       DEFAULT 0,
    leave_days_paid   INTEGER       DEFAULT 0,
    leave_days_unpaid INTEGER       DEFAULT 0,
    overtime_hours    DECIMAL(6,2)  DEFAULT 0.00,
    late_arrivals     INTEGER       DEFAULT 0,
    created_at        TIMESTAMPTZ   DEFAULT NOW(),
    UNIQUE(employee_id, month, year)
);

-- Payroll Records Table
CREATE TABLE IF NOT EXISTS payroll_records (
    payroll_id        VARCHAR(50)   PRIMARY KEY,
    employee_id       VARCHAR(50)   REFERENCES employees(employee_id) ON DELETE CASCADE,
    month             INTEGER       NOT NULL CHECK (month >= 1 AND month <= 12),
    year              INTEGER       NOT NULL CHECK (year >= 2020),
    payroll_cycle     VARCHAR(20)   DEFAULT 'monthly',
    basic_salary      DECIMAL(12,2) NOT NULL,
    hra               DECIMAL(12,2) DEFAULT 0.00,
    da                DECIMAL(12,2) DEFAULT 0.00,
    special_allowance DECIMAL(12,2) DEFAULT 0.00,
    overtime_pay      DECIMAL(12,2) DEFAULT 0.00,
    bonus             DECIMAL(12,2) DEFAULT 0.00,
    other_earnings    DECIMAL(12,2) DEFAULT 0.00,
    gross_salary      DECIMAL(12,2) NOT NULL,
    pf_deduction      DECIMAL(12,2) DEFAULT 0.00,
    income_tax        DECIMAL(12,2) DEFAULT 0.00,
    insurance         DECIMAL(12,2) DEFAULT 0.00,
    unpaid_leave_ded  DECIMAL(12,2) DEFAULT 0.00,
    other_deductions  DECIMAL(12,2) DEFAULT 0.00,
    total_deductions  DECIMAL(12,2) DEFAULT 0.00,
    net_salary        DECIMAL(12,2) NOT NULL,
    status            VARCHAR(20)   DEFAULT 'pending',
    payment_date      DATE,
    payment_mode      VARCHAR(50)   DEFAULT 'bank_transfer',
    remarks           TEXT,
    created_at        TIMESTAMPTZ   DEFAULT NOW(),
    updated_at        TIMESTAMPTZ   DEFAULT NOW(),
    UNIQUE(employee_id, month, year)
);

-- Payslips Table
CREATE TABLE IF NOT EXISTS payslips (
    payslip_id        VARCHAR(50)   PRIMARY KEY,
    payroll_id        VARCHAR(50)   REFERENCES payroll_records(payroll_id) ON DELETE CASCADE,
    employee_id       VARCHAR(50)   REFERENCES employees(employee_id) ON DELETE CASCADE,
    month             INTEGER       NOT NULL,
    year              INTEGER       NOT NULL,
    payslip_number    VARCHAR(50)   UNIQUE NOT NULL,
    generated_at      TIMESTAMPTZ   DEFAULT NOW(),
    emailed           BOOLEAN       DEFAULT FALSE,
    emailed_at        TIMESTAMPTZ
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_employees_department ON employees(department);
CREATE INDEX IF NOT EXISTS idx_employees_active ON employees(is_active);
CREATE INDEX IF NOT EXISTS idx_attendance_month_year ON attendance_records(month, year);
CREATE INDEX IF NOT EXISTS idx_payroll_month_year ON payroll_records(month, year);
CREATE INDEX IF NOT EXISTS idx_payroll_status ON payroll_records(status);
CREATE INDEX IF NOT EXISTS idx_payslips_month_year ON payslips(month, year);
"""
