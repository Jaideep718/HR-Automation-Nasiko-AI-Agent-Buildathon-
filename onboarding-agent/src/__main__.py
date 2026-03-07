import logging
import uuid
import click
import uvicorn
import asyncio
from datetime import datetime
from typing import List, Optional, Any, Dict, Union, Literal
from dotenv import load_dotenv
load_dotenv()
from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.responses import JSONResponse, HTMLResponse, Response
from fastapi import UploadFile, File, Form
import os
from tools import (
    notify_hr, schedule_orientation,
    _documents, _employees, _messages, VALID_DOCS, _schedules,
    send_document_reminder, REMINDER_DAYS,
)
from db import supabase, STORAGE_BUCKET
from agent import Agent
from models import JsonRpcRequest, JsonRpcResponse, Message, Task, TaskStatus, Artifact, ArtifactPart

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("agent-template")

app = FastAPI()
# Initialize the agent
agent = Agent()

# ---------------------------------------------------------------------------
# Background: Auto-send document reminders
# ---------------------------------------------------------------------------
async def reminder_loop():
    """Check every hour for employees with pending docs past the reminder threshold."""
    while True:
        await asyncio.sleep(3600)  # check every hour
        now = datetime.now()
        for emp_id, emp in list(_employees.items()):
            docs = _documents.get(emp_id, {})
            pending = [k for k, v in docs.items() if v != "uploaded"]
            if not pending:
                continue

            created = datetime.fromisoformat(emp["created_at"][:19])
            days_since = (now - created).days
            if days_since < REMINDER_DAYS:
                continue

            # only send one reminder per day
            msgs = _messages.get(emp_id, [])
            already_today = any(
                m["type"] == "document_reminder"
                and m["sent_at"][:10] == now.strftime("%Y-%m-%d")
                for m in msgs
            )
            if already_today:
                continue

            try:
                result = send_document_reminder(emp_id)
                logger.info(f"Auto-reminder: {result}")
            except Exception as e:
                logger.error(f"Reminder failed for {emp_id}: {e}")


@app.on_event("startup")
async def start_reminder_task():
    asyncio.create_task(reminder_loop())
@app.post("/")
async def handle_rpc(request: JsonRpcRequest):
    """Handle JSON-RPC requests."""
    
    if request.method == "message/send":
        try:
            # 1. Parse Input
            # request.params is now a JsonRpcParams model
            user_message = request.params.message
            session_id = request.params.session_id
            
            # Extract text
            input_text = ""
            for part in user_message.parts:
                if part.kind == "text" and part.text:
                    input_text += part.text
            
            logger.info(f"Received message: {input_text[:50]}... (Session: {session_id})")
            
            # 2. Invoke Agent Logic (with session memory)
            response_text = agent.process_message(input_text, session_id=session_id or "default")
            
            # 3. Construct Response
            task_id = str(uuid.uuid4())
            context_id = session_id if session_id else str(uuid.uuid4())
            
            artifact = Artifact(
                parts=[ArtifactPart(text=response_text)]
            )
            
            task = Task(
                id=task_id,
                status=TaskStatus(
                    state="completed",
                    timestamp=datetime.now().isoformat()
                ),
                artifacts=[artifact],
                contextId=context_id
            )
            
            return JsonRpcResponse(
                id=request.id,
                result=task
            )
            
        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))
    
    else:
        raise HTTPException(status_code=404, detail=f"Method {request.method} not found")
    
    
@app.get("/onboarding/upload")
async def upload_form(employee_id: str):
    """Serve an HTML upload form with 4 individual upload slots."""
    docs = _documents.get(employee_id, {})
    all_uploaded = all(v == "uploaded" for v in docs.values()) if docs else False

    if all_uploaded and docs:
        html = f"""
        <!DOCTYPE html>
        <html>
        <head><title>Upload Complete - {employee_id}</title>
        <style>
            body {{ font-family: Arial, sans-serif; max-width: 600px; margin: 60px auto; padding: 20px; text-align: center; }}
            .check {{ font-size: 64px; }}
            h2 {{ color: #34a853; }}
        </style>
        </head>
        <body>
            <div class="check">&#10004;</div>
            <h2>All Documents Successfully Submitted!</h2>
            <p>Employee ID: <b>{employee_id}</b></p>
            <p>All {len(docs)} required documents have been uploaded.</p>
            <p>&#9989; HR has been notified for account creation</p>
            <p>&#9989; First-day orientation has been scheduled</p>
            <p style="margin-top: 20px; color: #666;">You're all set! Check your email for orientation details.</p>
        </body>
        </html>
        """
        return HTMLResponse(content=html)

    rows = ""
    for key, label in VALID_DOCS.items():
        status = docs.get(key, "pending")
        if status == "uploaded":
            rows += f"""
            <div class="doc-row uploaded">
                <span class="icon">&#10004;</span>
                <span class="label">{label}</span>
                <span class="status">Uploaded</span>
            </div>"""
        else:
            rows += f"""
            <div class="doc-row">
                <form action="/onboarding/upload" method="post" enctype="multipart/form-data">
                    <input type="hidden" name="employee_id" value="{employee_id}">
                    <input type="hidden" name="document_type" value="{key}">
                    <span class="label">{label}</span>
                    <input type="file" name="file" required>
                    <button type="submit">Upload</button>
                </form>
            </div>"""

    uploaded_count = sum(1 for v in docs.values() if v == "uploaded")
    total = len(docs)

    html = f"""
    <!DOCTYPE html>
    <html>
    <head><title>Document Upload - {employee_id}</title>
    <style>
        body {{ font-family: Arial, sans-serif; max-width: 650px; margin: 40px auto; padding: 20px; }}
        h2 {{ color: #1a73e8; }}
        .progress {{ background: #e0e0e0; border-radius: 8px; height: 10px; margin: 15px 0; }}
        .progress-bar {{ background: #1a73e8; height: 10px; border-radius: 8px; width: {int(uploaded_count/total*100) if total else 0}%; }}
        .doc-row {{ border: 1px solid #ddd; border-radius: 8px; padding: 15px; margin: 10px 0; }}
        .doc-row.uploaded {{ background: #e8f5e9; border-color: #81c784; }}
        .doc-row form {{ display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }}
        .label {{ font-weight: bold; min-width: 200px; }}
        .icon {{ color: #34a853; font-size: 20px; margin-right: 10px; }}
        .status {{ color: #34a853; font-weight: bold; margin-left: auto; }}
        button {{ padding: 8px 20px; background: #1a73e8; color: white; border: none; border-radius: 4px; cursor: pointer; }}
        button:hover {{ background: #1558b0; }}
        input[type=file] {{ flex: 1; min-width: 150px; }}
    </style>
    </head>
    <body>
        <h2>Upload Onboarding Documents</h2>
        <p>Employee ID: <b>{employee_id}</b> &mdash; {uploaded_count}/{total} uploaded</p>
        <div class="progress"><div class="progress-bar"></div></div>
        {rows}
    </body>
    </html>
    """
    return HTMLResponse(content=html)

def _run_post_upload_tasks(employee_id: str):
    """Runs after the upload response is already sent — never blocks the user."""
    try:
        notify_hr.invoke({"employee_id": employee_id})
    except Exception as e:
        logger.error(f"notify_hr failed for {employee_id}: {e}")
    try:
        schedule_orientation.invoke({"employee_id": employee_id})
    except Exception as e:
        logger.error(f"schedule_orientation failed for {employee_id}: {e}")


@app.post("/onboarding/upload")
async def upload_document(
    background_tasks: BackgroundTasks,
    employee_id: str = Form(...),
    document_type: str = Form(...),
    file: UploadFile = File(...)
):
    try:
        file_content = await file.read()
        file_name = file.filename
        storage_path = f"{employee_id}/{document_type}_{file_name}"
        content_type = file.content_type or "application/octet-stream"
        now_iso = datetime.now().isoformat()

        def _do_upload():
            supabase.storage.from_(STORAGE_BUCKET).upload(
                storage_path, file_content,
                file_options={"content-type": content_type, "upsert": "true"},
            )
            supabase.table("documents").upsert({
                "employee_id": employee_id,
                "document_type": document_type,
                "status": "uploaded",
                "file_name": file_name,
                "storage_path": storage_path,
                "updated_at": now_iso,
            }, on_conflict="employee_id,document_type").execute()

        await asyncio.to_thread(_do_upload)

        # Update in-memory status
        _documents.setdefault(employee_id, {})[document_type] = "uploaded"

        # Schedule post-upload tasks as background work — redirect fires immediately
        docs = _documents.get(employee_id, {})
        if all(v == "uploaded" for v in docs.values()) and not _schedules.get(employee_id):
            background_tasks.add_task(_run_post_upload_tasks, employee_id)

        from fastapi.responses import RedirectResponse
        return RedirectResponse(
            url=f"/onboarding/upload?employee_id={employee_id}",
            status_code=303,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/onboarding/download/{employee_id}/{document_type}")
async def download_document(employee_id: str, document_type: str):
    """Download an uploaded document from Supabase Storage."""
    def _do_download():
        doc = supabase.table("documents").select("file_name, storage_path").eq(
            "employee_id", employee_id
        ).eq("document_type", document_type).execute()
        if not doc.data or not doc.data[0].get("storage_path"):
            return None, None
        row = doc.data[0]
        file_bytes = supabase.storage.from_(STORAGE_BUCKET).download(row["storage_path"])
        return file_bytes, row["file_name"]

    file_bytes, file_name = await asyncio.to_thread(_do_download)
    if file_bytes is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return Response(
        content=file_bytes,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{file_name}"'},
    )


if __name__ == "__main__":
    import click

    @click.command()
    @click.option('--host', 'host', default='0.0.0.0')
    @click.option('--port', 'port', default=5000)
    def main(host: str, port: int):
        uvicorn.run(app, host=host, port=port)

    main()
