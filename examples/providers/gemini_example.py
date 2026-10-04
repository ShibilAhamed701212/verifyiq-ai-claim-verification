"""VerifyIQ with Gemini Vision Provider.

Prerequisites:
    pip install verifyiq[api]
    export GEMINI_API_KEY="your-gemini-api-key"
"""

import os
from pathlib import Path

# VerifyIQ uses your Gemini key — it does not contain its own VLM
os.environ["GEMINI_API_KEY"] = os.environ.get("GEMINI_API_KEY", "")

if not os.environ["GEMINI_API_KEY"]:
    print("ERROR: Set GEMINI_API_KEY environment variable")
    print("Get a key at https://aistudio.google.com/apikey")
    exit(1)

os.environ["VERIFYIQ_MODE"] = "production"

from verifyiq.v2.pipeline import V2Pipeline

pipeline = V2Pipeline(config={
    "providers": {
        "gemini": {"model": "gemini-2.0-flash"},
    }
})

# Check vision state before processing
state = pipeline.vision_manager.state
print(f"Vision state: {state.value}")
print(f"Provider: Gemini ({pipeline.providers[0].model_name})")

decision = pipeline.process(
    claim_text="There is a dent on the front bumper after a parking lot incident.",
    image_paths=["dataset/images/sample/case_001/img_1.jpg"],
    claim_object="car",
    user_id="demo_user",
)

print(f"Status: {decision.claim_status}")
print(f"Confidence: {decision.confidence:.2f}")
print(f"Severity: {decision.severity}")
print(f"Justification: {decision.justification[:150]}")
