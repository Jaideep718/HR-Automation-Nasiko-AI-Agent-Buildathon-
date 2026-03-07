"""
HR Master Orchestrator Agent - FastAPI Server
Routes A2A JSON-RPC requests to appropriate worker agents.
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
logger = logging.getLogger("master-orchestrator-agent")

# Initialize FastAPI app
app = FastAPI(
    title="HR Master Orchestrator Agent",
    description="Master agent that routes HR requests to specialized worker agents.",
    version="1.0.0"
)

# Initialize the orchestrator agent
agent = Agent()


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "agent": "HR Master Orchestrator Agent",
        "version": "1.0.0",
        "worker_agents": [
            "hr-helpdesk-agent",
            "onboarding-agent",
            "resume-shortlisting-agent",
            "attendance-agent"
        ]
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
    - message/send: Process user messages and route to appropriate worker agent
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
            
            logger.info(f"Received HR request: {input_text[:100]}... (Session: {session_id})")
            
            # 2. Invoke Orchestrator Agent Logic
            response_text = agent.process_message(input_text)
            
            logger.info(f"Orchestrator response generated successfully")
            
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
            logger.error(f"Error processing request: {e}", exc_info=True)
            return JsonRpcErrorResponse(
                id=request.id,
                error=JsonRpcError(
                    code=-32603,
                    message=f"Internal error: {str(e)}"
                )
            )
    
    # Method not found
    return JsonRpcErrorResponse(
        id=request.id,
        error=JsonRpcError(
            code=-32601,
            message=f"Method not found: {request.method}"
        )
    )


@click.command()
@click.option("--host", default="0.0.0.0", help="Host to bind to")
@click.option("--port", default=5000, help="Port to bind to")
def main(host: str, port: int):
    """Start the HR Master Orchestrator Agent server."""
    logger.info(f"Starting HR Master Orchestrator Agent on {host}:{port}")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
