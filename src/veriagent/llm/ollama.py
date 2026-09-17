"""Local Ollama adapter for VeriAgent.

The adapter only converts a prompt into raw model output. It has no access to
business tools, SQLite, review approvals, or the secure executor.
"""
from __future__ import annotations

import json
import os
import socket
from typing import Any
from urllib import error, request
from urllib.parse import urlparse

from .base import BaseLLM, LLMError, LLMResponse, LLMTimeout

DEFAULT_HOST = "http://localhost:11434"
DEFAULT_MODEL = "llama3.2"


def _validated_host(host: str) -> str:
    normalized = host.rstrip("/")
    parsed = urlparse(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Ollama host must be an http(s) URL")
    return normalized


class OllamaLLM(BaseLLM):
    """Generate strict JSON through Ollama's local ``/api/chat`` endpoint."""

    def __init__(
        self,
        model: str | None = None,
        host: str | None = None,
        temperature: float = 0.0,
    ) -> None:
        self.model = (model or os.getenv("VERIAGENT_OLLAMA_MODEL") or DEFAULT_MODEL).strip()
        if not self.model:
            raise ValueError("Ollama model must not be empty")
        self.host = _validated_host(host or os.getenv("OLLAMA_HOST") or DEFAULT_HOST)
        if temperature < 0:
            raise ValueError("Temperature must be non-negative")
        self.temperature = float(temperature)

    def get_model_name(self) -> str:
        return self.model

    def generate(self, prompt: str, timeout: float = 30.0) -> LLMResponse:
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("Prompt must be a non-empty string")
        if timeout <= 0:
            raise ValueError("Timeout must be greater than zero")

        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "format": "json",
            "options": {"temperature": self.temperature},
        }
        data = self._request_json(
            "/api/chat", method="POST", payload=payload, timeout=timeout
        )

        message = data.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str) or not content.strip():
            raise LLMError("Ollama returned no textual message content")

        metadata_keys = (
            "total_duration",
            "load_duration",
            "prompt_eval_count",
            "eval_count",
            "done_reason",
        )
        metadata = {key: data[key] for key in metadata_keys if key in data}
        metadata["host"] = self.host
        metadata["temperature"] = self.temperature
        return LLMResponse(content=content, model=self.model, metadata=metadata)

    def list_models(self, timeout: float = 2.0) -> list[str]:
        """Return locally installed Ollama model names."""
        if timeout <= 0:
            raise ValueError("Timeout must be greater than zero")
        data = self._request_json("/api/tags", method="GET", timeout=timeout)
        models = data.get("models")
        if not isinstance(models, list):
            raise LLMError("Ollama model-list response is malformed")
        names: list[str] = []
        for model in models:
            if isinstance(model, dict) and isinstance(model.get("name"), str):
                names.append(model["name"])
        return names

    def has_model(self, timeout: float = 2.0) -> bool:
        """Check for the configured model, accepting optional ``:latest`` tags."""
        configured = self.model
        candidates = {configured, f"{configured}:latest"}
        if configured.endswith(":latest"):
            candidates.add(configured.removesuffix(":latest"))
        return any(name in candidates for name in self.list_models(timeout))

    def is_available(self, timeout: float = 0.5) -> bool:
        """Return whether the Ollama server is reachable and responds correctly."""
        try:
            self.list_models(timeout)
            return True
        except (LLMError, LLMTimeout, OSError, ValueError):
            return False

    def _request_json(
        self,
        path: str,
        *,
        method: str,
        timeout: float,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        req = request.Request(
            f"{self.host}{path}",
            data=body,
            method=method,
            headers={"Content-Type": "application/json"},
        )
        try:
            with request.urlopen(req, timeout=timeout) as response:
                raw = response.read().decode("utf-8")
        except error.HTTPError as exc:
            detail = self._http_error_detail(exc)
            if exc.code == 404:
                raise LLMError(
                    f"Ollama model or endpoint not found for '{self.model}': {detail}"
                ) from exc
            raise LLMError(f"Ollama HTTP {exc.code}: {detail}") from exc
        except (TimeoutError, socket.timeout) as exc:
            raise LLMTimeout(f"Ollama request exceeded {timeout:g} seconds") from exc
        except error.URLError as exc:
            if isinstance(exc.reason, (TimeoutError, socket.timeout)):
                raise LLMTimeout(f"Ollama request exceeded {timeout:g} seconds") from exc
            raise LLMError(
                f"Cannot connect to Ollama at {self.host}. Start Ollama and verify OLLAMA_HOST."
            ) from exc
        except OSError as exc:
            raise LLMError(f"Ollama connection failed: {exc}") from exc

        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise LLMError("Ollama returned an invalid JSON response") from exc
        if not isinstance(data, dict):
            raise LLMError("Ollama response must be a JSON object")
        if isinstance(data.get("error"), str):
            raise LLMError(f"Ollama error: {data['error']}")
        return data

    @staticmethod
    def _http_error_detail(exc: error.HTTPError) -> str:
        try:
            data = json.loads(exc.read().decode("utf-8"))
            if isinstance(data, dict) and isinstance(data.get("error"), str):
                return data["error"]
        except (json.JSONDecodeError, UnicodeDecodeError, OSError):
            pass
        return exc.reason or "request failed"


def ollama_available(
    host: str | None = None,
    model: str | None = None,
    timeout: float = 0.5,
) -> bool:
    """Convenience probe for optional live integration tests."""
    try:
        return OllamaLLM(model=model, host=host).is_available(timeout)
    except ValueError:
        return False
