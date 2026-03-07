# HR Helpdesk Agent

An AI-powered HR helpdesk agent built using the [A2A (Agent-to-Agent)](https://github.com/ashishsharma/nasiko) protocol. It answers employee HR policy questions, provides FAQ responses, and escalates complex issues to human HR representatives.

## Features

- **Policy Search**: Search and retrieve company HR policies
- **FAQ Answers**: Quick answers to frequently asked questions
- **Issue Escalation**: Escalate complex issues with ticket tracking
- **Ticket Status**: Check status of existing escalation tickets
- **Conversational Interface**: Natural language interaction powered by LangChain

## Supported Policy Topics

| Topic                 | Description                                    |
| --------------------- | ---------------------------------------------- |
| Leave Policy          | Annual leave, sick leave, parental leave       |
| Remote Work           | Hybrid work guidelines, eligibility, equipment |
| Expense Reimbursement | Travel, meals, office supplies                 |
| Employee Benefits     | Health insurance, 401(k), other perks          |
| Onboarding            | New hire process and requirements              |
| Performance Reviews   | Review cycles, ratings, promotions             |
| Code of Conduct       | Professional standards, reporting              |
| Resignation           | Notice period, exit process                    |

## External Tools/Dependencies Required

| Tool/Library     | Version        | Purpose                         |
| ---------------- | -------------- | ------------------------------- |
| Python           | 3.11+          | Runtime environment             |
| FastAPI          | >=0.109.0      | Web framework for HTTP server   |
| Uvicorn          | >=0.27.0       | ASGI server                     |
| Pydantic         | >=2.6.0        | Data validation and models      |
| LangChain        | >=0.2.0,<0.3.0 | Agent orchestration framework   |
| LangChain-OpenAI | >=0.1.0,<0.2.0 | OpenAI GPT integration          |
| python-dotenv    | >=1.0.0        | Environment variable management |
| requests         | >=2.31.0       | HTTP requests                   |
| click            | >=8.1.7        | CLI argument parsing            |
| Docker           | Latest         | Containerization                |

## Frameworks

- **Server**: FastAPI
- **Agent Logic**: LangChain with OpenAI GPT-4o
- **Protocol**: A2A JSON-RPC 2.0

## Project Structure

```
hr-helpdesk-agent/
├── src/
│   ├── __init__.py          # Package initialization
│   ├── __main__.py           # FastAPI server handling A2A JSON-RPC requests
│   ├── models.py             # A2A protocol Pydantic models
│   ├── tools.py              # HR-specific tools (policy search, escalation, etc.)
│   └── agent.py              # HR helpdesk agent logic and prompt configuration
├── AgentCard.json            # Agent metadata and capabilities
├── Dockerfile                # Docker configuration
├── docker-compose.yml        # Docker Compose configuration
└── README.md                 # This file
```

## How to Run

### Prerequisites

- Docker Desktop installed
- OpenAI API Key

### Option 1: Docker (Recommended)

1. **Set OpenAI API Key**:

   ```bash
   export OPENAI_API_KEY=your_openai_api_key
   ```

2. **Build and Run with Docker**:
   ```bash
   docker build -t hr-helpdesk-agent .
   docker run -p 5000:5000 -e OPENAI_API_KEY=$OPENAI_API_KEY hr-helpdesk-agent
   ```

### Option 2: Docker Compose

1. **Create a `.env` file**:

   ```
   OPENAI_API_KEY=your_openai_api_key
   ```

2. **Create the network (if not exists)**:

   ```bash
   docker network create agents-net
   ```

3. **Run with Docker Compose**:
   ```bash
   docker-compose up --build
   ```

### Option 3: Local Development

1. **Install dependencies**:

   ```bash
   pip install fastapi uvicorn pydantic python-dotenv requests langchain langchain-openai click
   ```

2. **Set environment variable**:

   ```bash
   export OPENAI_API_KEY=your_openai_api_key
   ```

3. **Run the server**:
   ```bash
   cd src
   python __main__.py --host 0.0.0.0 --port 5000
   ```

## Testing the Agent

### Test with curl

```bash
# Ask about leave policy
curl -X POST http://localhost:5000/ \
-H "Content-Type: application/json" \
-d '{
  "jsonrpc": "2.0",
  "id": "1",
  "method": "message/send",
  "params": {
    "message": {
      "role": "user",
      "parts": [{"kind": "text", "text": "What is the leave policy?"}]
    }
  }
}'

# Ask about remote work
curl -X POST http://localhost:5000/ \
-H "Content-Type: application/json" \
-d '{
  "jsonrpc": "2.0",
  "id": "2",
  "method": "message/send",
  "params": {
    "message": {
      "role": "user",
      "parts": [{"kind": "text", "text": "Can I work from home?"}]
    }
  }
}'

# Escalate an issue
curl -X POST http://localhost:5000/ \
-H "Content-Type: application/json" \
-d '{
  "jsonrpc": "2.0",
  "id": "3",
  "method": "message/send",
  "params": {
    "message": {
      "role": "user",
      "parts": [{"kind": "text", "text": "I need to escalate a complaint about my manager. My name is John Smith."}]
    }
  }
}'
```

### Health Check

```bash
curl http://localhost:5000/health
```

## Example Interactions

- "What is the annual leave policy?"
- "How many sick days do I have?"
- "Can I work from home?"
- "What are the expense reimbursement limits?"
- "How do I enroll in 401(k)?"
- "What are the company holidays this year?"
- "I need to escalate a concern about workplace harassment"
- "What's the status of ticket HR-20260307-ABC12345?"

## Escalation Workflow

When an issue is escalated:

1. Agent collects issue details and employee name
2. Creates an escalation ticket with unique ID
3. Assigns priority (low/medium/high/urgent)
4. Categorizes the issue (benefits/leave/complaint/etc.)
5. Returns ticket ID and expected response time
6. Employee can check ticket status anytime

## Customization

### Add New Policies

Edit `src/tools.py` and add entries to the `HR_POLICIES` dictionary:

```python
HR_POLICIES["new_policy"] = {
    "title": "New Policy Name",
    "content": """
    Policy details here...
    """
}
```

### Add New FAQ Entries

Edit `src/tools.py` and add entries to the `FAQ_DATABASE` dictionary:

```python
FAQ_DATABASE["new_faq"] = "Answer to the FAQ..."
```

### Modify Agent Behavior

Edit `src/agent.py` to customize the system prompt and agent behavior.

### Update Agent Metadata

Edit `AgentCard.json` to modify agent metadata and capabilities.

## License

MIT License

## Support

For questions or issues, contact the HR Automation Team.
