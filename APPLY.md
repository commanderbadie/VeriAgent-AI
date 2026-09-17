# Apply the Phase 4.5 Ollama patch

1. Copy `src/veriagent/llm/ollama.py` into the same path in the project.
2. Replace `src/veriagent/llm/__init__.py` with the provided version.
3. In the existing `src/veriagent/__init__.py`, add:

   ```python
   from .llm.ollama import OllamaLLM, ollama_available
   ```

   Then add `"OllamaLLM"` and `"ollama_available"` to its existing `__all__` list. Do not replace the full existing file.
4. Copy `tests/test_ollama.py` and `docs/phase4-5-ollama.md` into their corresponding directories.
5. Run the full suite:

   ```powershell
   py -W error::ResourceWarning -m unittest discover -s tests -v
   ```

6. Install and test local Ollama:

   ```powershell
   ollama pull llama3.2
   $env:VERIAGENT_OLLAMA_MODEL = "llama3.2"
   $env:VERIAGENT_RUN_OLLAMA_TESTS = "1"
   py -m unittest tests.test_ollama.OllamaLiveIntegrationTests -v
   ```

The implementation uses Python's standard-library HTTP client, so no Python Ollama package is required.
