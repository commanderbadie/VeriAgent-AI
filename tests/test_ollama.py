from __future__ import annotations

import io
import json
import os
import socket
import unittest
from unittest.mock import patch
from urllib import error

from veriagent.llm.base import LLMError, LLMTimeout
from veriagent.llm.ollama import OllamaLLM, ollama_available


class _Response:
    def __init__(self, payload: object) -> None:
        self.payload = json.dumps(payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self) -> bytes:
        return self.payload


class OllamaLLMTests(unittest.TestCase):
    def test_generate_uses_json_mode_and_temperature_zero(self) -> None:
        response = {
            "message": {"content": '{"action":"get_customer","parameters":{"customer_id":101}}'},
            "eval_count": 12,
        }
        with patch("veriagent.llm.ollama.request.urlopen", return_value=_Response(response)) as mocked:
            result = OllamaLLM(model="test-model").generate("return an action", timeout=4)

        sent = json.loads(mocked.call_args.args[0].data.decode())
        self.assertEqual(sent["model"], "test-model")
        self.assertEqual(sent["format"], "json")
        self.assertFalse(sent["stream"])
        self.assertEqual(sent["options"]["temperature"], 0.0)
        self.assertEqual(result.model, "test-model")
        self.assertEqual(result.metadata["eval_count"], 12)

    def test_connection_failure_fails_closed(self) -> None:
        with patch(
            "veriagent.llm.ollama.request.urlopen",
            side_effect=error.URLError("refused"),
        ):
            with self.assertRaisesRegex(LLMError, "Cannot connect"):
                OllamaLLM().generate("prompt")

    def test_timeout_has_specific_exception(self) -> None:
        with patch(
            "veriagent.llm.ollama.request.urlopen", side_effect=socket.timeout()
        ):
            with self.assertRaises(LLMTimeout):
                OllamaLLM().generate("prompt", timeout=0.1)

    def test_model_not_found_is_clear(self) -> None:
        body = io.BytesIO(b'{"error":"model not found"}')
        failure = error.HTTPError("url", 404, "Not Found", {}, body)
        with patch("veriagent.llm.ollama.request.urlopen", side_effect=failure):
            with self.assertRaisesRegex(LLMError, "model not found"):
                OllamaLLM(model="missing").generate("prompt")

    def test_malformed_server_response_fails_closed(self) -> None:
        response = _Response({"unexpected": True})
        with patch("veriagent.llm.ollama.request.urlopen", return_value=response):
            with self.assertRaisesRegex(LLMError, "no textual message"):
                OllamaLLM().generate("prompt")

    def test_list_models(self) -> None:
        response = _Response({"models": [{"name": "llama3.2:latest"}, {"name": "qwen2.5:3b"}]})
        with patch("veriagent.llm.ollama.request.urlopen", return_value=response):
            adapter = OllamaLLM(model="llama3.2")
            self.assertEqual(adapter.list_models(), ["llama3.2:latest", "qwen2.5:3b"])
            self.assertTrue(adapter.has_model())

    def test_availability_returns_false_instead_of_raising(self) -> None:
        with patch(
            "veriagent.llm.ollama.request.urlopen",
            side_effect=error.URLError("refused"),
        ):
            self.assertFalse(OllamaLLM().is_available())

    def test_rejects_invalid_configuration(self) -> None:
        with self.assertRaises(ValueError):
            OllamaLLM(host="file:///tmp/ollama")
        with self.assertRaises(ValueError):
            OllamaLLM(temperature=-1)
        with self.assertRaises(ValueError):
            OllamaLLM().generate("", timeout=1)


@unittest.skipUnless(
    os.getenv("VERIAGENT_RUN_OLLAMA_TESTS") == "1" and ollama_available(),
    "Set VERIAGENT_RUN_OLLAMA_TESTS=1 with local Ollama running",
)
class OllamaLiveIntegrationTests(unittest.TestCase):
    def test_local_server_and_configured_model(self) -> None:
        adapter = OllamaLLM()
        self.assertTrue(adapter.has_model())
        result = adapter.generate(
            'Return exactly {"action":"get_customer","parameters":{"customer_id":101}}',
            timeout=60,
        )
        self.assertTrue(result.content.strip())


if __name__ == "__main__":
    unittest.main()
