"""Chat backend protocol."""
from __future__ import annotations

from typing import Protocol


class ChatBackend(Protocol):
    name: str
    model_id: str

    def complete(self, messages: list[dict[str, str]], *,
                 temperature: float = 0.0, seed: int | None = None) -> str:
        """Return the assistant's reply text for a chat-style message list."""
        ...
