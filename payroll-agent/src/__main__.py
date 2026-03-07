"""
Payroll Automation Agent - FastAPI Server
Handles A2A JSON-RPC requests for payroll processing and management.
"""
import logging
import uuid
import click
import uvicorn
from datetime import datetime
from typing import List, Optional, Any, Dict, Union, Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from agent import Agent
from models import (
    JsonRpcRequest,
    JsonRpcResponse,
    JsonRpcErrorResponse,
    JsonRpcError,
    Message,
    Task,
    TaskStatus,
    Artifact,
    ArtifactPart
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("payroll-agent")

# Initialize FastAPI app
app = FastAPI(
    title="Payroll Automation Agent",
    description="An AI-powered payroll agent that manages salary calculations, payslip generation, and payroll reports.",
    version="1.0.0"
)

# Initialize the agent
agent = Agent()


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "agent": "Payroll Automation Agent",
        "version": "1.0.0"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint for container orchestration."""
    return {"status": "healthy"}


@app.post("/")
async def handle_rpc(request: JsonRpcRequest):
    """
    Handle JSON-RPC requests following the A2A protocol.
    
    Supported methods:
    - message/send: Process user messages and return agent responses
    """
    
    if request.method == "message/send":
        try:
            # 1. Parse Input
            user_message = request.params.message
            session_id = request.params.session_id
            
            # Extract text from message parts
            input_text = ""
            for part in user_message.parts:
                if part.kind == "text" and part.text:
                    input_text += part.text
            
            logger.info(f"Received payroll query: {input_text[:100]}... (Session: {session_id})")
            
            # 2. Invoke Agent Logic
            response_text = agent.process_message(input_text)
            
            logger.info(f"Agent response generated successfully")
            
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
                    timestamp=datetime.utcnow().isoformat() + "Z"
                ),
                artifacts=[artifact],
                contextId=context_id
            )
            
            return JsonRpcResponse(
                id=request.id,
                result=task
            )
            
        except Exception as e:
            logger.error(f"Error processing request: {e}")
            return JsonRpcErrorResponse(
                id=request.id,
                error=JsonRpcError(
                    code=-32603,
                    message="Internal error",
                    data=str(e)
                )
            )
    
    # Unknown method
    return JsonRpcErrorResponse(
        id=request.id,
        error=JsonRpcError(
            code=-32601,
            message=f"Method not found: {request.method}"
        )
    )


@click.command()
@click.option("--host", default="localhost", help="Host to bind to")
@click.option("--port", default=5003, help="Port to bind to")
def main(host: str, port: int):
    """Run the Payroll Automation Agent server."""
    logger.info(f"Starting Payroll Automation Agent on {host}:{port}")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
