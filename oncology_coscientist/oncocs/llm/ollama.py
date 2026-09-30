"""Ollama chat backend via langchain-ollama."""
from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_ollama import ChatOllama


def _to_lc(messages: list[dict[str, str]]):
    out = []
    for m in messages:
        role, content = m.get("role", "user"), m["content"]
        if role == "system":
            out.append(SystemMessage(content=content))
        elif role == "assistant":
            out.append(AIMessage(content=content))
        else:
            out.append(HumanMessage(content=content))
    return out


class OllamaBackend:
    name = "ollama"

    def __init__(self, model: str = "gemma3:4b", host: str = "http://127.0.0.1:11434"):
        self.model_id = model
        self.host = host
        self._model = model

    def complete(self, messages: list[dict[str, str]], *,
                 temperature: float = 0.0, seed: int | None = None) -> str:
        kwargs = {"temperature": temperature, "num_predict": 1500}
        if seed is not None:
            kwargs["seed"] = seed
        chat = ChatOllama(model=self._model, base_url=self.host, **kwargs)
        return chat.invoke(_to_lc(messages)).content
