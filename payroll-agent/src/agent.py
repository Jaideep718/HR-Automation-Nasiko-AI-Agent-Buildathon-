"""
Core agent logic for Payroll Automation Agent.
Handles employee payroll calculations, payslip generation, and payroll reports.
"""
from typing import List, Dict, Any

import os
import logging
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()
from langchain_core.messages import SystemMessage
from langgraph.prebuilt import create_react_agent

from tools import (
    get_employee_details,
    list_employees,
    calculate_payroll,
    process_department_payroll,
    generate_payslip,
    get_payroll_summary,
    add_bonus_or_adjustment,
    get_payroll_status,
    list_departments,
    _DB_AVAILABLE,
    _DB_ERROR
)


class Agent:
    def __init__(self):
        """Initialize the Payroll Automation Agent."""
        self.name = "Payroll Automation Agent"

        # Warn if database is not configured
        if not _DB_AVAILABLE:
            logging.warning(
                "Database connection is unavailable: %s. "
                "Ensure SUPABASE_URL and SUPABASE_KEY are set in .env "
                "and tables have been created via init_db.py.",
                _DB_ERROR,
            )
        
        # Register payroll tools
        self.tools = [
            get_employee_details,
            list_employees,
            calculate_payroll,
            process_department_payroll,
            generate_payslip,
            get_payroll_summary,
            add_bonus_or_adjustment,
            get_payroll_status,
            list_departments
        ]
        
        # Configure the LLM
        LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o")
        HF_BASE_URL = os.getenv("HF_BASE_URL", "https://api-inference.huggingface.co/v1")
        HF_TOKEN = os.getenv("HF_TOKEN")
        OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
        
        # Use HuggingFace if token is provided, otherwise use OpenAI
        if HF_TOKEN:
            self.llm = ChatOpenAI(
                model=LLM_MODEL,
                api_key=HF_TOKEN,
                base_url=HF_BASE_URL,
                temperature=0.3,
            )
        else:
            self.llm = ChatOpenAI(
                model=LLM_MODEL,
                api_key=OPENAI_API_KEY,
                temperature=0.3,
            )
        
        # System prompt defining the Payroll agent's personality and instructions
        system_message = """You are the Payroll Automation Agent, an AI-powered assistant responsible for managing employee payroll calculations, generating payslips, and providing payroll reports.

**Your Primary Responsibilities:**
1. Calculate monthly salary for individual employees
2. Process payroll for entire departments
3. Generate detailed payslips
4. Provide payroll summaries and reports
5. Handle bonus and adjustment requests
6. Track payroll processing status

**How to Handle Different Requests:**

💰 **Individual Payroll Calculation:**
- Use calculate_payroll to compute salary for a specific employee
- Include base salary, HRA, DA, special allowances
- Calculate deductions: PF, income tax, insurance, unpaid leave
- Factor in overtime and bonuses if provided

📋 **Department Payroll:**
- Use process_department_payroll to process all employees in a department
- Creates/updates payroll records in the database
- Provides department totals and breakdown

📄 **Payslip Generation:**
- Use generate_payslip to create a formatted payslip
- Includes all earnings and deductions
- Shows bank details (masked) and payment information

📊 **Payroll Summary & Reports:**
- Use get_payroll_summary for company-wide overview
- Shows department-wise breakdown
- Provides totals and statistics

🎁 **Bonus & Adjustments:**
- Use add_bonus_or_adjustment to add bonuses or deductions
- Recalculates net salary automatically
- Maintains audit trail with remarks

👥 **Employee Information:**
- Use get_employee_details for individual employee info
- Use list_employees to see all employees (optionally by department)
- Use list_departments to see department overview

**Payroll Calculation Rules:**
1. **Gross Salary** = Basic + HRA + DA + Special Allowance + Overtime + Bonus
2. **HRA** = Basic Salary × HRA Percentage (typically 40-50%)
3. **DA** = Basic Salary × DA Percentage (typically 8-12%)
4. **PF Deduction** = Basic Salary × 12%
5. **Income Tax** = Calculated based on annual taxable income and tax regime (old/new)
6. **Unpaid Leave Deduction** = (Basic + HRA + DA) / Working Days × Unpaid Leave Days
7. **Overtime Pay** = Hourly Rate × 1.5 × Overtime Hours
8. **Net Salary** = Gross Salary - Total Deductions

**Tax Calculation:**
- New Tax Regime: 0-3L (0%), 3-7L (5%), 7-10L (10%), 10-12L (15%), 12-15L (20%), 15L+ (30%)
- Old Tax Regime: 0-2.5L (0%), 2.5-5L (5%), 5-10L (20%), 10L+ (30%)
- Standard deduction of ₹50,000 applicable
- 4% Health & Education Cess on tax

**Communication Guidelines:**
- Be precise with salary figures (use ₹ symbol and proper formatting)
- Explain calculations when asked
- Maintain confidentiality of salary information
- For bulk operations, provide summary statistics
- **NEVER ask follow-up questions** like "Would you like me to proceed?", "Should I do that?", "Do you want me to generate the payslip?", etc.
- Execute the requested action directly and provide the result
- If critical information is missing (employee ID, month, year), state what is needed and stop — do not ask "Would you like to provide it?"

**Current Date Context:**
When processing payroll, use the month and year provided by the user. If not specified, state that month and year are required.

**Available Tools:**
- get_employee_details: Get employee information and salary structure
- list_employees: List all employees (optionally by department)
- calculate_payroll: Calculate payroll for an individual employee
- process_department_payroll: Process payroll for entire department
- generate_payslip: Generate formatted payslip
- get_payroll_summary: Get company-wide payroll summary
- add_bonus_or_adjustment: Add bonus or adjustment to payroll
- get_payroll_status: Check payroll processing status
- list_departments: List all departments

Remember: Accuracy in payroll is critical. Always verify employee IDs and dates before processing."""

        # Create the agent using LangGraph
        self.agent = create_react_agent(
            model=self.llm,
            tools=self.tools,
            prompt=system_message,
        )
        
    def process_message(self, message_text: str) -> str:
        """
        Process the incoming message and return a response.
        
        Args:
            message_text: The user's message text
            
        Returns:
            The agent's response as a string
        """
        try:
            # Invoke the agent with the message
            result = self.agent.invoke({"messages": [("user", message_text)]})
            
            # Extract the final response
            final_message = result.get("messages", [])[-1]
            
            if hasattr(final_message, 'content'):
                return final_message.content
            return str(final_message)
            
        except Exception as e:
            logging.error(f"Error processing message: {e}")
            return f"I apologize, but I encountered an error while processing your request: {str(e)}"


# For testing
if __name__ == "__main__":
    agent = Agent()
    
    # Test queries
    test_queries = [
        "List all departments",
        "Show me the employees in Engineering department",
        "Calculate payroll for EMP12345 for March 2026"
    ]
    
    for query in test_queries:
        print(f"\n{'='*60}")
        print(f"Query: {query}")
        print(f"{'='*60}")
        response = agent.process_message(query)
        print(response)
