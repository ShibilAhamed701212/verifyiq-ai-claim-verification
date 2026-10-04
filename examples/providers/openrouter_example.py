"""VerifyIQ with OpenRouter Vision Provider.

Prerequisites:
    pip install verifyiq[api]
    export OPENROUTER_API_KEY="your-openrouter-api-key"

NOTE: OpenRouterProvider is currently a stub. It reports itself available when
OPENROUTER_API_KEY is set, but analyze() makes no API call and returns no
observations. See verifyiq/v2/providers/openrouter_provider.py.
"""

import os

os.environ["OPENROUTER_API_KEY"] = os.environ.get("OPENROUTER_API_KEY", "")

if not os.environ["OPENROUTER_API_KEY"]:
    print("ERROR: Set OPENROUTER_API_KEY environment variable")
    print("Get a key at https://openrouter.ai/keys")
    exit(1)

os.environ["VERIFYIQ_MODE"] = "production"

from verifyiq.v2.pipeline import V2Pipeline

pipeline = V2Pipeline(config={
    "providers": {
        "openrouter": {"model": "qwen/qwen2.5-vl-72b-instruct"},
    }
})

state = pipeline.vision_manager.state
print(f"Vision state: {state.value}")
print(f"Provider: OpenRouter ({pipeline.providers[0].model_name})")
