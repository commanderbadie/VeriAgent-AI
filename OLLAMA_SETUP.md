# Ollama Setup Guide for VeriAgent

## Installation

### Windows

1. **Download Ollama:**
   - Visit https://ollama.com/download/windows
   - Download `OllamaSetup.exe`
   - Run the installer

2. **Verify installation:**
   ```powershell
   ollama --version
   ```

### Alternative: Manual installation

If the installer doesn't work, you can install Ollama manually:

1. Download from GitHub releases: https://github.com/ollama/ollama/releases
2. Extract to a directory (e.g., `C:\Program Files\Ollama`)
3. Add to PATH or use full path

## Setup for VeriAgent

### 1. Start Ollama server

Open a PowerShell window and run:

```powershell
ollama serve
```

Keep this window open while testing. You should see:
```
Ollama is running on http://localhost:11434
```

### 2. Pull the model

Open **another** PowerShell window and run:

```powershell
ollama pull llama3.2
```

This downloads the Llama 3.2 model (~2GB). Wait for it to complete.

### 3. Verify model is available

```powershell
ollama list
```

You should see `llama3.2:latest` in the list.

### 4. Configure VeriAgent

```powershell
$env:VERIAGENT_OLLAMA_MODEL = "llama3.2"
```

Optional: Change the host if Ollama is running elsewhere:
```powershell
$env:OLLAMA_HOST = "http://localhost:11434"
```

## Testing

### Run the basic adapter test

```powershell
cd "C:\Users\badie\OneDrive\Badie_Personal\Projects\FYP - Veriagent\VeriAgent-AI-starter"

$env:VERIAGENT_OLLAMA_MODEL = "llama3.2"
$env:VERIAGENT_RUN_OLLAMA_TESTS = "1"

py -m unittest tests.test_ollama.OllamaLiveIntegrationTests -v
```

Expected output:
```
test_local_server_and_configured_model ... ok

Ran 1 test in 3.456s

OK
```

### Run the complete end-to-end test

```powershell
py test_end_to_end.py
```

This tests the full pipeline:
1. ✅ Simple read operations (get_customer)
2. ✅ Calculations (calculate_balance)
3. ✅ Small refunds (ALLOW → execute)
4. ✅ Large refunds (REVIEW → queue)
5. ✅ Missing entities (BLOCK)
6. ✅ Unsupported actions (fail closed)
7. ✅ Injection attempts (fail closed)

## Troubleshooting

### "Cannot connect to Ollama"

- Ensure `ollama serve` is running in another terminal
- Check if port 11434 is free: `netstat -ano | findstr 11434`
- Try accessing http://localhost:11434 in a browser

### "Model not found"

- Run `ollama pull llama3.2` again
- Verify with `ollama list`
- Check spelling: it's `llama3.2` not `llama-3.2`

### "Response is not valid JSON"

This is expected occasionally with smaller models. The ActionParser will reject it and fail closed (no execution). Try:

- Using a larger model: `ollama pull llama3.2:3b`
- Adjusting the prompt (but temperature stays at 0)
- Accepting that some requests may fail - this is safe behavior

### Port conflicts

If port 11434 is in use:

```powershell
$env:OLLAMA_HOST = "http://localhost:11435"
ollama serve --port 11435
```

## Alternative Models

VeriAgent works with any Ollama model that supports JSON mode:

```powershell
# Smaller/faster models
ollama pull llama3.2:1b

# Larger/better models  
ollama pull qwen2.5:7b
ollama pull mistral:latest

# Configure
$env:VERIAGENT_OLLAMA_MODEL = "qwen2.5:7b"
```

## Performance Notes

- **First request:** May take 10-30 seconds (model loading)
- **Subsequent requests:** 1-5 seconds per request
- **Memory usage:** ~2-4GB for llama3.2
- **Temperature 0:** Ensures repeatable results for testing

## Next Steps

Once Ollama is working:

1. Run all 133 unit tests: `py -W error::ResourceWarning -m unittest discover -s tests -v`
2. Run end-to-end test: `py test_end_to_end.py`
3. Test specific scenarios interactively
4. Proceed to Phase 5: ML behavioral risk model
