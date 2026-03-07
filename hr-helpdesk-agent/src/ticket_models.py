"""
Schema reference for HR Helpdesk escalation tickets.
The actual table lives in Supabase. Run init_db.py for the SQL to create it.
"""

# Column reference (matches the Supabase table schema)
# ticket_id       VARCHAR(50)   PRIMARY KEY
# employee_name   VARCHAR(255)  NOT NULL
# issue_description TEXT         NOT NULL
# priority        VARCHAR(20)   DEFAULT 'medium'  -- low | medium | high | urgent
# category        VARCHAR(50)   DEFAULT 'general' -- general | benefits | leave | complaint | payroll | accommodation | other
# status          VARCHAR(20)   DEFAULT 'open'    -- open | in_progress | pending | resolved | closed
# created_at      TIMESTAMPTZ   DEFAULT NOW()
# updated_at      TIMESTAMPTZ   DEFAULT NOW()
# assigned_to     VARCHAR(255)  DEFAULT 'HR Team'
# expected_response VARCHAR(100) DEFAULT '24-48 hours'
# notes           TEXT
# resolution      TEXT
# contact_email   VARCHAR(255)
# contact_phone   VARCHAR(50)

TABLE_NAME = "escalation_tickets"

VALID_PRIORITIES = ["low", "medium", "high", "urgent"]
VALID_CATEGORIES = ["general", "benefits", "leave", "complaint", "payroll", "accommodation", "other"]
VALID_STATUSES   = ["open", "in_progress", "pending", "resolved", "closed"]

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS escalation_tickets (
    ticket_id         VARCHAR(50)  PRIMARY KEY,
    employee_name     VARCHAR(255) NOT NULL,
    issue_description TEXT         NOT NULL,
    priority          VARCHAR(20)  DEFAULT 'medium',
    category          VARCHAR(50)  DEFAULT 'general',
    status            VARCHAR(20)  DEFAULT 'open',
    created_at        TIMESTAMPTZ  DEFAULT NOW(),
    updated_at        TIMESTAMPTZ  DEFAULT NOW(),
    assigned_to       VARCHAR(255) DEFAULT 'HR Team',
    expected_response VARCHAR(100) DEFAULT '24-48 hours',
    notes             TEXT,
    resolution        TEXT,
    contact_email     VARCHAR(255),
    contact_phone     VARCHAR(50)
);
"""
