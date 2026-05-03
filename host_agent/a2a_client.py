"""
A2A Client – sends tasks to remote A2A servers and retrieves responses.
"""
from __future__ import annotations

import uuid
from typing import Optional

import httpx

from common.a2a_types import AgentCard, TaskMessage, TaskResult, TextPart


class A2AClient:
    """Lightweight async A2A client."""

    def __init__(self, agent_url: str, timeout: float = 120.0):
        self.agent_url = agent_url.rstrip("/")
        self.timeout = timeout

    async def get_agent_card(self) -> AgentCard:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.get(f"{self.agent_url}/.well-known/agent.json")
            resp.raise_for_status()
            return AgentCard(**resp.json())

    async def send_task(self, text: str, task_id: Optional[str] = None) -> TaskResult:
        """Send a text task to the remote agent and return the result."""
        if task_id is None:
            task_id = str(uuid.uuid4())

        payload = {
            "jsonrpc": "2.0",
            "method": "tasks/send",
            "params": {
                "id": task_id,
                "message": TaskMessage.user(text).model_dump(),
            },
            "id": str(uuid.uuid4()),
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(self.agent_url, json=payload)
            resp.raise_for_status()
            data = resp.json()

        if "error" in data and data["error"]:
            raise RuntimeError(f"A2A error: {data['error']}")

        return TaskResult(**data["result"])
