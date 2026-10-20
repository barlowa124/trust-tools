"""Pydantic schemas for the review API."""
from __future__ import annotations

from pydantic import BaseModel, Field


class ApproveRequest(BaseModel):
    by: str
    note: str = ""


class RejectRequest(BaseModel):
    by: str
    reason: str


class AgentRunRequest(BaseModel):
    backend: str = Field(
        default="endpoint",
        pattern="^(endpoint|ollama|scripted-demo)$")
    seed: int | None = None
