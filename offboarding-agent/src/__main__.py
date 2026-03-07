"""
Employee Offboarding Agent — FastAPI Server
Handles A2A JSON-RPC requests for the offboarding lifecycle.
Includes a proactive asset return reminder that emails employees with pending assets.
"""
import logging
import uuid
import asyncio
import click
import uvicorn
from datetime import datetime
from typing import List, Optional, Any, Dict, Union, Literal
from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from agent import Agent
from tools import _offboardings, _assets, _messages, REQUIRED_ASSETS, _send_email, _save_message_to_db
from models import (
    JsonRpcRequest,
    JsonRpcResponse,
    Message,
    Task,
    TaskStatus,
    Artifact,
    ArtifactPart,
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("offboarding-agent")

app = FastAPI(
    title="Employee Offboarding Agent",
    description="AI-powered agent for automating the employee offboarding lifecycle.",
    version="1.0.0",
)

agent = Agent()


# ---------------------------------------------------------------------------
# Background: Proactive asset return reminders
# ---------------------------------------------------------------------------
async def asset_reminder_loop():
    """Check every 6 hours for departing employees with unreturned assets
    whose last working day is within 7 days."""
    while True:
        await asyncio.sleep(21600)  # 6 hours
        now = datetime.now()
        for off_id, rec in list(_offboardings.items()):
            if rec.get("status") in ("completed", "cancelled"):
                continue

            try:
                lwd = datetime.strptime(rec["last_working_date"], "%Y-%m-%d")
            except (ValueError, KeyError):
                continue

            days_left = (lwd - now).days
            if days_left > 7 or days_left < 0:
                continue

            assets = _assets.get(off_id, {})
            pending = [REQUIRED_ASSETS[k] for k, v in assets.items() if v == "pending"]
            if not pending:
                continue

            # Only one reminder per day
            msgs = _messages.get(off_id, [])
            already_today = any(
                m["type"] == "asset_reminder" and m["sent_at"][:10] == now.strftime("%Y-%m-%d")
                for m in msgs
            )
            if already_today:
                continue

            try:
                subject = f"Reminder: {len(pending)} asset(s) pending return — {rec['employee_name']}"
                body = (
                    f"<p>Dear {rec['employee_name']},</p>"
                    f"<p>Your last working day is <b>{rec['last_working_date']}</b> "
                    f"({days_left} day{'s' if days_left != 1 else ''} away).</p>"
                    f"<p>The following company assets are still pending return:</p>"
                    f"<ul>{''.join(f'<li>{a}</li>' for a in pending)}</ul>"
                    f"<p>Please ensure all items are returned to HR/IT before your last day.</p>"
                    f"<p>Best regards,<br><b>HR Team</b></p>"
                )
                _send_email(rec["employee_email"], subject, body)

                msg = {"type": "asset_reminder", "sent_at": now.isoformat(), "to": rec["employee_email"]}
                _messages.setdefault(off_id, []).append(msg)
                _save_message_to_db(off_id, msg)
                logger.info(f"Asset reminder sent: {off_id} → {rec['employee_email']}")
            except Exception as e:
                logger.error(f"Asset reminder failed for {off_id}: {e}")


@app.on_event("startup")
async def start_reminder_task():
    asyncio.create_task(asset_reminder_loop())


@app.get("/")
async def root():
    return {
        "status": "healthy",
        "agent": "Employee Offboarding Agent",
        "version": "1.0.0",
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


@app.post("/")
async def handle_rpc(request: JsonRpcRequest):
    if request.method == "message/send":
        try:
            user_message = request.params.message
            session_id = request.params.session_id

            input_text = ""
            for part in user_message.parts:
                if part.kind == "text" and part.text:
                    input_text += part.text

            logger.info(f"Received message: {input_text[:100]}... (Session: {session_id})")

            response_text = agent.process_message(input_text, session_id=session_id or "default")

            task_id = str(uuid.uuid4())
            context_id = session_id if session_id else str(uuid.uuid4())

            artifact = Artifact(parts=[ArtifactPart(text=response_text)])
            task = Task(
                id=task_id,
                status=TaskStatus(state="completed", timestamp=datetime.now().isoformat()),
                artifacts=[artifact],
                contextId=context_id,
            )
            return JsonRpcResponse(id=request.id, result=task)

        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))
    else:
        raise HTTPException(
            status_code=404,
            detail=f"Method '{request.method}' not found. Supported: message/send",
        )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "jsonrpc": "2.0",
            "id": None,
            "error": {"code": -32603, "message": "Internal error", "data": str(exc)},
        },
    )


if __name__ == "__main__":

    @click.command()
    @click.option("--host", default="0.0.0.0", help="Host to bind to")
    @click.option("--port", default=5000, help="Port to bind to")
    def main(host: str, port: int):
        logger.info(f"Starting Employee Offboarding Agent on {host}:{port}")
        uvicorn.run(app, host=host, port=port)

    main()
