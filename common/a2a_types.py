"""
Shared Pydantic models for the A2A (Agent-to-Agent) protocol.
Based on the Google A2A JSON-RPC spec.
"""
from __future__ import annotations

from typing import Any, Literal, Optional, Union
from pydantic import BaseModel, Field
import uuid


# ── Message primitives ────────────────────────────────────────────────────────

class TextPart(BaseModel):
    type: Literal["text"] = "text"
    text: str


class DataPart(BaseModel):
    type: Literal["data"] = "data"
    data: dict[str, Any]


Part = Union[TextPart, DataPart]


class TaskMessage(BaseModel):
    role: Literal["user", "agent"] = "user"
    parts: list[Part]

    @classmethod
    def user(cls, text: str) -> "TaskMessage":
        return cls(role="user", parts=[TextPart(text=text)])


# ── Task models ───────────────────────────────────────────────────────────────

class TaskStatus(BaseModel):
    state: Literal["submitted", "working", "completed", "failed"] = "submitted"
    message: Optional[str] = None


class TaskArtifact(BaseModel):
    name: Optional[str] = None
    parts: list[Part]


class Task(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    message: TaskMessage


class TaskResult(BaseModel):
    id: str
    status: TaskStatus
    artifacts: Optional[list[TaskArtifact]] = None

    def text(self) -> str:
        """Extract plain-text response from artifacts."""
        if not self.artifacts:
            return ""
        for artifact in self.artifacts:
            for part in artifact.parts:
                if isinstance(part, TextPart):
                    return part.text
        return ""


# ── JSON-RPC wrapper ──────────────────────────────────────────────────────────

class JsonRpcRequest(BaseModel):
    jsonrpc: str = "2.0"
    method: str
    params: dict[str, Any]
    id: Union[str, int] = Field(default_factory=lambda: str(uuid.uuid4()))


class JsonRpcResponse(BaseModel):
    jsonrpc: str = "2.0"
    result: Optional[Any] = None
    error: Optional[dict[str, Any]] = None
    id: Union[str, int, None] = None


# ── Agent Card ────────────────────────────────────────────────────────────────

class AgentSkill(BaseModel):
    id: str
    name: str
    description: str
    tags: list[str] = []
    examples: list[str] = []


class AgentCapabilities(BaseModel):
    streaming: bool = False
    pushNotifications: bool = False
    stateTransitionHistory: bool = False


class AgentCard(BaseModel):
    """Served at GET /.well-known/agent.json"""
    name: str
    description: str
    url: str
    version: str = "1.0.0"
    skills: list[AgentSkill] = []
    capabilities: AgentCapabilities = AgentCapabilities()
    defaultInputModes: list[str] = ["text"]
    defaultOutputModes: list[str] = ["text"]
