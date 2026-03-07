# Payroll Automation Agent

An AI-powered payroll automation agent that manages the complete payroll process for employees, eliminating the need for manual salary calculations and spreadsheet-based payroll management.

## Features

- **Individual Payroll Calculation**: Calculate monthly salary for any employee including all earnings and deductions
- **Department-wide Payroll**: Process payroll for entire departments in one operation
- **Payslip Generation**: Generate detailed, formatted payslips for employees
- **Payroll Summaries**: Company-wide reports with department-wise breakdown
- **Bonus & Adjustments**: Handle bonuses, overtime, and payroll corrections
- **Tax Calculation**: Automatic income tax calculation for both old and new tax regimes
- **Employee Management**: View employee details and salary structures

## Architecture

This agent follows the A2A (Agent-to-Agent) protocol using JSON-RPC for communication. It integrates with:

- **Supabase**: PostgreSQL database for employee and payroll data
- **LangChain/LangGraph**: For AI-powered query processing
- **FastAPI**: HTTP server for API endpoints

## Database Schema

The agent uses four main tables:

1. **employees**: Employee master data including salary structure
2. **attendance_records**: Monthly attendance and leave records
3. **payroll_records**: Computed payroll for each month
4. **payslips**: Generated payslip records

## Setup

### Prerequisites

- Python 3.11+
- Supabase account (for database)
- OpenAI API key or HuggingFace token

### Environment Variables

Create a `.env` file in the `src/` directory:

```env
# Database
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-service-role-key

# LLM Configuration (choose one)
OPENAI_API_KEY=your-openai-api-key
# OR
HF_TOKEN=your-huggingface-token
HF_BASE_URL=https://api-inference.huggingface.co/v1
LLM_MODEL=your-model-name
```

### Installation

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Initialize the database:

```bash
cd src
python init_db.py
```

3. Copy the SQL output and run it in your Supabase SQL Editor

4. Seed sample data:

```bash
python seed_data.py
```

5. Run the agent:

```bash
python __main__.py --host localhost --port 5003
```

## Docker

Build and run with Docker:

```bash
# Build
docker build -t payroll-agent .

# Run
docker run -p 5003:5003 --env-file .env payroll-agent
```

Or use Docker Compose:

```bash
docker-compose up -d
```

## API Usage

### Health Check

```bash
curl http://localhost:5003/health
```

### Process Query (A2A Protocol)

```bash
curl -X POST http://localhost:5003/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": "1",
    "method": "message/send",
    "params": {
      "message": {
        "role": "user",
        "parts": [{"kind": "text", "text": "Calculate payroll for EMP12345 for March 2026"}]
      }
    }
  }'
```

## Example Queries

1. **List employees in a department:**

   > "Show me all employees in the Engineering department"

2. **Calculate individual payroll:**

   > "Calculate payroll for EMP12345 for March 2026"

3. **Process department payroll:**

   > "Process payroll for the Finance department for March 2026"

4. **Generate payslip:**

   > "Generate payslip for EMP12345 for March 2026"

5. **Get payroll summary:**

   > "Show me the payroll summary for March 2026"

6. **Add bonus:**

   > "Add a bonus of ₹10,000 to EMP12345 for March 2026"

7. **Check payroll status:**
   > "What's the payroll status for Engineering department for March 2026?"

## Payroll Calculation Details

### Earnings

- **Basic Salary**: Base monthly salary
- **HRA**: House Rent Allowance (% of basic)
- **DA**: Dearness Allowance (% of basic)
- **Special Allowance**: Additional allowances
- **Overtime**: Calculated at 1.5x hourly rate
- **Bonus**: Performance or ad-hoc bonuses

### Deductions

- **Provident Fund**: 12% of basic salary
- **Income Tax**: Based on annual income and tax regime
- **Insurance**: Health insurance premium
- **Unpaid Leave**: Pro-rated deduction for unpaid leaves

### Tax Regimes

**New Tax Regime (FY 2025-26):**

- 0 - 3L: 0%
- 3L - 7L: 5%
- 7L - 10L: 10%
- 10L - 12L: 15%
- 12L - 15L: 20%
- Above 15L: 30%
- Plus 4% Health & Education Cess

**Old Tax Regime:**

- 0 - 2.5L: 0%
- 2.5L - 5L: 5%
- 5L - 10L: 20%
- Above 10L: 30%
- Plus 4% Cess

## Integration with Master Orchestrator

This agent is designed to work within the HR Automation multi-agent system. The Master Orchestrator routes payroll-related queries to this agent.

## License

MIT License
