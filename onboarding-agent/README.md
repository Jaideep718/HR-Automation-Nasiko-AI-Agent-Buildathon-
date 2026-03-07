# Employee Onboarding Agent

An A2A-compatible agent that automates the full employee onboarding lifecycle — from hire to first-day readiness.

## What It Does

Transitions a hired candidate into a fully onboarded employee by:

- **Creating employee profiles** with role, department, manager, and candidate insights
- **Generating role-based checklists** (employee tasks, HR tasks, manager tasks)
- **Sending welcome emails** with first-day schedules
- **Requesting & tracking documents** (ID proof, bank details, tax form, NDA, offer letter)
- **Scheduling orientation** (HR orientation, team intro, IT setup, manager 1:1)
- **Sending reminders** for pending tasks and missing documents
- **Notifying HR** when onboarding is at risk
- **Providing status summaries** on demand

## Tools

| Tool | Purpose |
|------|---------|
| `create_employee_profile` | Register a new hire in the system |
| `generate_onboarding_checklist` | Create role-specific task lists |
| `send_welcome_email` | Send welcome email with Day 1 schedule |
| `request_documents` | Request required documents from employee |
| `track_documents` | Check document upload status |
| `update_document_status` | Mark a document as uploaded/pending |
| `schedule_orientation` | Schedule Day 1 orientation events |
| `send_reminder` | Remind employee about pending items |
| `notify_hr` | Escalate onboarding risks to HR |
| `get_onboarding_status` | Full onboarding summary |
| `update_checklist_task` | Mark a checklist task complete |

## Quick Start

```bash
# Build
docker build -t onboarding-agent .

# Run
docker run -p 5000:5000 -e OPENAI_API_KEY=$OPENAI_API_KEY onboarding-agent
```

## Test

```bash
# Create an employee profile
curl -X POST http://localhost:5000/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0", "id": "test-1", "method": "message/send",
    "params": { "message": { "role": "user", "parts": [{"kind": "text", "text": "Onboard a new hire: Rahul Sharma, rahul.sharma@email.com, Software Engineer in Engineering, manager Ankit Mehta, starting 2026-07-01 in Bangalore, Full-time. Skills: Python, Machine Learning. 3 years experience. Interview notes: Strong backend developer."}] } }
  }'

# Check onboarding status
curl -X POST http://localhost:5000/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0", "id": "test-2", "method": "message/send",
    "params": { "message": { "role": "user", "parts": [{"kind": "text", "text": "What is the onboarding status for EMP-1001?"}] } }
  }'
```

## Structure

```
my-awesome-agent/
├── src/
│   ├── __init__.py
│   ├── __main__.py    # FastAPI server (A2A protocol handler)
│   ├── agent.py       # LangChain agent configuration
│   ├── models.py      # A2A Pydantic models
│   └── tools.py       # Onboarding tool functions
├── docker-compose.yml
├── Dockerfile
├── AgentCard.json
└── README.md
```
    docker run -p 8000:8000 -e OPENAI_API_KEY=your_key my-agent
    ```

## Protocol Details

This template implements:
- `POST /`: JSON-RPC 2.0 endpoint.
  - Method: `message/send`
  - Params: A2A Message format

