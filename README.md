# HR Automation – Nasiko AI Agent Buildathon

Multi-agent HR automation system built with LangChain, LangGraph, and FastAPI.

**Repo:** https://github.com/Jaideep718/HR-Automation-Nasiko-AI-Agent-Buildathon-

## Agents

| Agent | Port |
|---|---|
| Master Orchestrator | 5000 |
| HR Helpdesk | 5001 |
| Onboarding | 5002 |
| Resume Shortlisting | 5003 |
| Attendance | 5004 |
| Offboarding | 5005 |
| Payroll | 5006 |

## Setup

**Prerequisites:** Docker, Docker Compose, OpenAI API key

1. Clone the repo
   ```bash
   git clone https://github.com/Jaideep718/HR-Automation-Nasiko-AI-Agent-Buildathon-.git
   cd HR-Automation-Nasiko-AI-Agent-Buildathon-
   ```

2. Copy `.env.example` to `.env` and fill in your credentials
   ```bash
   cp .env.example .env
   ```

3. Start all agents
   ```bash
   docker compose up --build
   ```

4. Send requests to the orchestrator at `http://localhost:5000`
