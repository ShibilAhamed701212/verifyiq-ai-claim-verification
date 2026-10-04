from abc import ABC, abstractmethod

from verifyiq.v2.models.observation import ObservationReport


class VisionProvider(ABC):
    """Abstract base for all vision model providers.

    Each provider wraps a specific model API or local inference path.
    Providers must fail independently — one provider failure never
    crashes the pipeline.
    """

    def __init__(self, model_name: str, config: dict | None = None):
        self.model_name = model_name
        self.config = config or {}
        self._available = self._check_availability()

    @abstractmethod
    def _check_availability(self) -> bool:
        """Check if this provider can be used (API key present, model accessible)."""

    @abstractmethod
    def analyze(self, image_paths: list[str], claim_text: str, claim_object: str) -> ObservationReport:
        """Run vision analysis on claim images.

        Must never raise. Return ObservationReport with all_failed=True on error.
        """

    def is_available(self) -> bool:
        return self._available
