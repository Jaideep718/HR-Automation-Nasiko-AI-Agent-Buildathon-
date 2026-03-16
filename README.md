# HR Automation – Nasiko AI Agent Buildathon

Multi-agent HR automation system built with LangChain, LangGraph, and FastAPI.

**Repo:** https://github.com/Jaideep718/HR-Automation-Nasiko-AI-Agent-Buildathon-

## Agents

| Agent | Port | Description|
|---|---|---|
| Master Orchestrator | 5000 | Routes prompts to the correct agent |
| HR Helpdesk | 5001 | Policy Q&A (RAG) + ticket escalation |
| Onboarding | 5002 | New hire onboarding, docs, calendar |
| Resume Shortlisting | 5003 | Parse & rank resumes from CSV/PDF |
| Attendance | 5004 | Leave requests + attendance tracking |
| Offboarding | 5005 | Exit process, asset return, interviews |
| Payroll | 5006 | Salary computation + payslips |

## Prerequisites

- **Docker** and **Docker Compose**
- **Python 3.11+** (for one-time setup scripts below — not needed at runtime)
- **OpenAI API key**
- **Supabase** account ([supabase.com](https://supabase.com))
- **Pinecone** account ([pinecone.io](https://app.pinecone.io)) — for HR Helpdesk
- **Gmail App Password** — for any agent that sends email

### Gmail App Passwords

Several agents send email (helpdesk, onboarding, offboarding, resume, attendance). Each needs a Gmail App Password:

1. Go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
2. Sign in, select **Mail** and **Other (Custom name)**, generate a 16-character password
3. Use that password (not your Gmail password) in the `.env` file

> Requires 2-Step Verification to be enabled on the Google account.

---

## Setup (follow in order)

### 1. Clone the repo

```bash
git clone https://github.com/Jaideep718/HR-Automation-Nasiko-AI-Agent-Buildathon-.git
cd HR-Automation-Nasiko-AI-Agent-Buildathon-
```

### 2. Install Python dependencies (for setup scripts only)

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

```bash
cp .env.example .env
```

Open `.env` and fill in all values. Each agent that uses Supabase needs a Supabase project URL + service role key. You can find them in **Supabase Dashboard → Project Settings → API**.

You can use separate Supabase projects per agent or reuse one — just make sure table names don't collide. Offboarding reuses the onboarding Supabase project by default.

### 4. Set up Supabase tables

Tables are **not auto-created**. Run each agent's `init_db.py` once. If a script prints SQL instead of creating tables directly, paste that SQL into **Supabase Dashboard → SQL Editor → New Query** and run it.

```bash
# HR Helpdesk — escalation_tickets table
cd hr-helpdesk-agent/src
python init_db.py
cd ../..

# Onboarding — employees, documents tables + storage bucket
cd onboarding-agent/src
python init_db.py
cd ../..

# Offboarding — offboardings, offboarding_assets, exit_interviews, offboarding_messages
cd offboarding-agent/src
python init_db.py
cd ../..

# Payroll — payroll tables + seed sample data
cd payroll-agent/src
python init_db.py
python seed_data.py
cd ../..

# Attendance — employees + leave_requests tables + seed sample data
python attendance-agent/seed_employees.py
```

### 5. Set up Pinecone (HR Helpdesk Agent)

1. Create two indexes in [Pinecone Console](https://app.pinecone.io) with:
   - **Dimension:** 384
   - **Metric:** cosine
   - Index names matching `PINECONE_INDEX` and `PINECONE_FAQ_INDEX` in your `.env` (e.g. `hr-policies` and `hr-faqs`)

2. Ingest data into the indexes:
```bash
cd hr-helpdesk-agent/src
python ingest_policies.py
python ingest_faqs.py
cd ../..
```

### 6. Set up Google Calendar (Onboarding Agent — optional)

Without this, all onboarding features work except calendar event scheduling.

1. Go to [Google Cloud Console](https://console.cloud.google.com/), create a project, enable the **Google Calendar API**
2. Create **OAuth 2.0 credentials** (Desktop app type), download as `credentials.json`
3. Place `credentials.json` in `onboarding-agent/src/`
4. Run the agent locally once to complete the OAuth browser flow:
   ```bash
   cd onboarding-agent/src
   python __main__.py
   ```
   This opens a browser, you log in, and `token.json` is generated in the same folder. Stop the server after.
5. Docker mounts both files automatically at runtime — no rebuild needed

> Neither file is committed to git or baked into the Docker image.

### 7. Start all agents

```bash
docker compose up --build
```

The orchestrator waits for all agents to be healthy before starting. First build takes a few minutes.

### 8. Use the system

Send JSON-RPC requests to the orchestrator at `http://localhost:5000`:

```bash
curl -X POST http://localhost:5000 \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "message/send",
    "params": {
      "message": {
        "role": "user",
        "parts": [{"kind": "text", "text": "What is the vacation policy?"}]
      }
    }
  }'
```

You can also hit individual agents directly on their respective ports (5001–5006) using the same format.
