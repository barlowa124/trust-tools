"""Pydantic schemas for the review API."""
from __future__ import annotations

from pydantic import BaseModel


class ApproveRequest(BaseModel):
    by: str
    note: str = ""


class RejectRequest(BaseModel):
    by: str
    reason: str
