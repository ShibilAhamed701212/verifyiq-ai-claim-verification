"""VerifyIQ with Local VLM Provider.

Prerequisites:
    pip install verifyiq[api]
    # Install your local VLM (e.g., Ollama, llama.cpp, vLLM)
    # Run your local VLM server on localhost:8001

NOTE: LocalVLMProvider is currently a stub. analyze() returns no observations
and base_url is not used yet, so claims run without vision input.
See verifyiq/v2/providers/local_vlm_provider.py.
"""

import os

# No API key needed for local models
os.environ["VERIFYIQ_MODE"] = "production"

from verifyiq.v2.pipeline import V2Pipeline

pipeline = V2Pipeline(config={
    "providers": {
        "local": {
            "model": "qwen2.5-vl-7b",
            "base_url": "http://localhost:8001",
        },
    }
})

state = pipeline.vision_manager.state
print(f"Vision state: {state.value}")
if pipeline.providers:
    print(f"Provider: Local ({pipeline.providers[0].model_name})")
else:
    print("Local provider not available (is your VLM server running?)")
