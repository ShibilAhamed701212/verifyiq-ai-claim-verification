from code.v2.models.observation import Observation, ObservationReport
from code.v2.providers.base import VisionProvider


class OpenRouterProvider(VisionProvider):
    """OpenRouter multi-model vision provider. Stub — requires OPENROUTER_API_KEY."""

    PROVIDER_NAME = "openrouter"

    def __init__(self, model_name: str = "qwen/qwen2.5-vl-72b-instruct", config: dict | None = None):
        super().__init__(model_name, config)

    def _check_availability(self) -> bool:
        import os
        return bool(os.environ.get("OPENROUTER_API_KEY"))

    def analyze(self, image_paths: list[str], claim_text: str, claim_object: str) -> ObservationReport:
        if not self._available:
            return ObservationReport(all_failed=True)
        # Stub - returns empty result
        obs = Observation(model_name=self.model_name, provider=self.PROVIDER_NAME, success=False, degraded=True)
        return ObservationReport(observations=[obs], all_failed=True)
