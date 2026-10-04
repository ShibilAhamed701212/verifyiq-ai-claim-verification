from code.v2.models.observation import Observation, ObservationReport
from code.v2.providers.base import VisionProvider


class LocalVLMProvider(VisionProvider):
    """Local VLM provider stub. Always available; analyze is a placeholder."""

    PROVIDER_NAME = "local_vlm"

    def __init__(self, model_name: str = "qwen2.5-vl-7b", config: dict | None = None):
        super().__init__(model_name, config)

    def _check_availability(self) -> bool:
        return True  # Always available (local)

    def analyze(self, image_paths: list[str], claim_text: str, claim_object: str) -> ObservationReport:
        # Stub for now
        obs = Observation(model_name=self.model_name, provider=self.PROVIDER_NAME, success=False, degraded=True)
        return ObservationReport(observations=[obs], all_failed=True)
