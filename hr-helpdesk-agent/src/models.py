"""
Pydantic models for A2A protocol.
Defines the request/response structure for JSON-RPC communication.
"""
import uuid
from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field


class MessagePart(BaseModel):
    """A part of a message containing content."""
    kind: str
    text: Optional[str] = None


class Message(BaseModel):
    """A message in the conversation."""
    role: str
    parts: List[MessagePart]
    messageId: Optional[str] = None


class JsonRpcParams(BaseModel):
    """Parameters for JSON-RPC requests."""
    session_id: Optional[str] = None
    message: Message


class JsonRpcRequest(BaseModel):
    """JSON-RPC 2.0 request format."""
    jsonrpc: Literal["2.0"]
    id: str
    method: str
    params: JsonRpcParams


class ArtifactPart(BaseModel):
    """A part of an artifact containing response content."""
    kind: str = "text"
    text: str


class Artifact(BaseModel):
    """An artifact containing the agent's response."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    kind: str = "text"
    parts: List[ArtifactPart]


class TaskStatus(BaseModel):
    """Status of a task."""
    state: str
    timestamp: str


class Task(BaseModel):
    """A task representing the agent's work on a request."""
    id: str
    kind: str = "task"
    status: TaskStatus
    artifacts: List[Artifact] = []
    contextId: Optional[str] = None


class JsonRpcResponse(BaseModel):
    """JSON-RPC 2.0 response format."""
    jsonrpc: Literal["2.0"] = "2.0"
    id: str
    result: Task


class JsonRpcError(BaseModel):
    """JSON-RPC 2.0 error format."""
    code: int
    message: str
    data: Optional[Any] = None


class JsonRpcErrorResponse(BaseModel):
    """JSON-RPC 2.0 error response format."""
    jsonrpc: Literal["2.0"] = "2.0"
    id: Optional[str] = None
    error: JsonRpcError
