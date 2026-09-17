# Phase 4.5 — Local Ollama Adapter

## Purpose

Connect the existing model-independent agent to a free local Ollama server without giving the model access to tools, SQLite, approvals, or the executor.

## Configuration

- `OLLAMA_HOST` — defaults to `http://localhost:11434`
- `VERIAGENT_OLLAMA_MODEL` — defaults to `llama3.2`
- Temperature defaults to `0` for repeatability.

## Setup

```powershell
ollama serve
ollama pull llama3.2
$env:VERIAGENT_OLLAMA_MODEL = "llama3.2"
```

The adapter uses the local `/api/chat` endpoint with streaming disabled and JSON mode enabled. The existing strict `ActionParser` remains the final authority on output validity.

## Test commands

Unit tests do not require Ollama:

```powershell
py -W error::ResourceWarning -m unittest discover -s tests -v
```

Live test is explicitly opt-in:

```powershell
$env:VERIAGENT_RUN_OLLAMA_TESTS = "1"
py -m unittest tests.test_ollama.OllamaLiveIntegrationTests -v
```

## Fail-closed behavior

Connection failures, timeouts, HTTP errors, malformed server responses, missing message content, and invalid configuration raise `LLMError` or `LLMTimeout`. The agent converts these failures into a non-executing response.
