# VerifyIQ Provider Examples

VerifyIQ is an AI agent framework — it does NOT contain a built-in vision model.
You must configure an external vision provider for image analysis.

## Available Providers

| Provider | Setup | Model Example |
|----------|-------|---------------|
| **Gemini** | `export GEMINI_API_KEY="..."` | `gemini-2.0-flash` |
| **OpenRouter** | `export OPENROUTER_API_KEY="..."` | `qwen/qwen2.5-vl-72b-instruct` |
| **Local VLM** | Run local server on `localhost:8001` | `qwen2.5-vl-7b` |
| **Custom** | Implement `VisionProvider` interface | Any |

## Running Examples

```bash
# Gemini (recommended)
export GEMINI_API_KEY="your-key"
python examples/providers/gemini_example.py

# OpenRouter
export OPENROUTER_API_KEY="your-key"
python examples/providers/openrouter_example.py

# Local VLM (requires running server)
python examples/providers/local_vlm_example.py
```

## Without a Vision Provider

Set `VERIFYIQ_MODE=demo` to run text-only with honest disclaimers:

```bash
export VERIFYIQ_MODE=demo
python -c "
from verifyiq.v2.pipeline import V2Pipeline
p = V2Pipeline()
print(f'Vision state: {p.vision_manager.state.value}')  # 'unavailable'
print(f'Mode: {p.vision_manager.mode.value}')           # 'demo'
"
```

## Provider Priority Chain

When multiple providers are configured, VerifyIQ tries them in order:

1. **Gemini** — fastest, most reliable
2. **OpenRouter** — broad model selection
3. **Local VLM** — no API dependency, slower

If the primary provider fails (3 consecutive errors = circuit open for 60s), the next provider is tried automatically.

## Custom Provider

See `code/v2/providers/base.py` for the `VisionProvider` interface.
Implement `_check_availability()` and `analyze()` to add any VLM.
