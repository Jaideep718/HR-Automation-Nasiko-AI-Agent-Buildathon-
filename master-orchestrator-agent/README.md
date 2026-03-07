# HR Master Orchestrator Agent

Master orchestrator agent that intelligently routes HR requests to specialized worker agents.

## Architecture

```
                    ┌─────────────────────────────────┐
                    │   HR Master Orchestrator Agent   │
                    │         (Port 5000)              │
                    └─────────────┬───────────────────┘
                                  │
          ┌───────────────────────┼───────────────────────┐
          │                       │                       │
          ▼                       ▼                       ▼
┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
│  HR Helpdesk    │   │   Onboarding    │   │ Resume Shortlist│
│     Agent       │   │     Agent       │   │     Agent       │
│  (Port 5001)    │   │  (Port 5002)    │   │  (Port 5003)    │
└─────────────────┘   └─────────────────┘   └─────────────────┘
     Employee              HR Admin              HR Admin
     Queries              New Hires            Recruitment
                                                    │
                                   ┌────────────────┘
                                   ▼
                         ┌─────────────────┐
                         │   Attendance    │
                         │     Agent       │
                         │  (Port 5004)    │
                         └─────────────────┘
                           Time & Leave
```

## Worker Agents

| Agent               | Port | Target Users | Purpose                                  |
| ------------------- | ---- | ------------ | ---------------------------------------- |
| HR Helpdesk         | 5001 | Employees    | Policy questions, FAQs, issue escalation |
| Onboarding          | 5002 | HR Admins    | New employee setup and configuration     |
| Resume Shortlisting | 5003 | HR Admins    | Candidate screening and ranking          |
| Attendance          | 5004 | All          | Time tracking, leave management          |

## Quick Start

### 1. Set up environment variables

Create a `.env` file in this directory:

```bash
# LLM Configuration (choose one)
OPENAI_API_KEY=your-openai-key
# OR
HF_TOKEN=your-huggingface-token
HF_BASE_URL=https://api-inference.huggingface.co/v1
LLM_MODEL=your-model-name

# HR Helpdesk specific (optional)
PINECONE_API_KEY=your-pinecone-key
PINECONE_INDEX=hr-policies
PINECONE_FAQ_INDEX=hr-faqs
DB_HOST=localhost
DB_PORT=5432
DB_NAME=hr_helpdesk
DB_USER=postgres
DB_PASSWORD=password
```

### 2. Run with Docker Compose

```bash
# Build and start all agents
docker-compose up --build

# Or run in background
docker-compose up -d --build
```

### 3. Test the orchestrator

```bash
curl -X POST http://localhost:5000/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": "1",
    "method": "message/send",
    "params": {
      "session_id": "test-session",
      "message": {
        "role": "user",
        "parts": [{"kind": "text", "text": "What is the leave policy?"}]
      }
    }
  }'
```

## Example Queries

### Employee Queries (routed to HR Helpdesk)

```
"What is the leave policy?"
"I want to escalate a dispute with my manager"
"How do I reset my password?"
```

### HR Admin - Onboarding (routed to Onboarding Agent)

```
"Onboard a new employee: Rahul Sharma, email mc23bt004@iitdh.ac.in,
role Software Engineer, department Engineering, manager Priya Patel,
start date 2026-04-01, location Bangalore"
```

### HR Admin - Recruitment (routed to Resume Shortlisting)

```
"Shortlist candidates for Full Stack Developer role. Spreadsheet: data/resumes.csv"
```

### Attendance (routed to Attendance Agent)

```
"Show my attendance for this month"
"Process leave request for employee ID 12345"
```

## Local Development

### Run without Docker

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export OPENAI_API_KEY=your-key

# Start worker agents first (in separate terminals)
cd ../hr-helpdesk-agent && python -m src --port 5001
cd ../onboarding-agent && python -m src --port 5002
cd ../resume-shortlisting-agent && python -m src --port 5003
cd ../attendance-agent && python -m src --port 5004

# Start master orchestrator
python -m src --port 5000
```

### Configure worker agent URLs

For local development, set these environment variables:

```bash
export HR_HELPDESK_URL=http://localhost:5001
export ONBOARDING_AGENT_URL=http://localhost:5002
export RESUME_SHORTLIST_URL=http://localhost:5003
export ATTENDANCE_AGENT_URL=http://localhost:5004
```

## API Endpoints

| Endpoint  | Method | Description                        |
| --------- | ------ | ---------------------------------- |
| `/`       | GET    | Health check                       |
| `/health` | GET    | Health status                      |
| `/`       | POST   | JSON-RPC endpoint for A2A protocol |

## How It Works

1. **Request Received**: Master agent receives an HR request via A2A protocol
2. **Intent Analysis**: LLM analyzes the request to determine intent and user type
3. **Agent Selection**: Selects the most appropriate worker agent
4. **Request Forwarding**: Forwards the complete request to the worker agent
5. **Response Relay**: Returns the worker agent's response to the user

## Adding New Worker Agents

1. Create the agent following the same structure as existing agents
2. Add the agent to `docker-compose.yml`
3. Add a new routing tool in `src/tools.py`
4. Register the tool in `src/agent.py`
5. Update the system prompt with the new agent's capabilities
