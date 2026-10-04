
from verifyiq.v2.models.observation import Observation, ObservationReport, PerImageAssessment
from verifyiq.v2.providers.base import VisionProvider


class GeminiProvider(VisionProvider):
    """Gemini vision provider. Reuses V1's vision_analyzer pattern."""

    PROVIDER_NAME = "gemini"

    def __init__(self, model_name: str = "gemini-2.0-flash", config: dict | None = None):
        super().__init__(model_name, config)

    def _check_availability(self) -> bool:
        import os
        return bool(os.environ.get("GEMINI_API_KEY"))

    def analyze(self, image_paths: list[str], claim_text: str, claim_object: str) -> ObservationReport:
        try:
            import os

            from google import genai
            api_key = self.config.get("api_key") or os.environ.get("GEMINI_API_KEY")
            if not api_key:
                return ObservationReport(all_failed=True)
            client = genai.Client(api_key=api_key)

            import time
            start = time.time()

            contents = [claim_text]
            for p in image_paths[:5]:
                try:
                    from PIL import Image
                    img = Image.open(p)
                    contents.append(img)
                except Exception:
                    pass

            response = client.models.generate_content(
                model=self.model_name,
                contents=contents,
                config={"temperature": 0.0, "response_mime_type": "application/json"}
            )

            assessments = []
            if response and response.text:
                import json
                import re
                text = response.text.strip()
                json_match = re.search(r'\{.*\}', text, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group())
                    per_image = data.get("per_image_assessments") or data.get("image_assessments") or []
                    for i, img_path in enumerate(image_paths[:5]):
                        img_data = per_image[i] if i < len(per_image) else {}
                        assessments.append(PerImageAssessment(
                            image_path=img_path,
                            damage_visible=img_data.get("damage_visible", False),
                            damage_type=img_data.get("damage_type", "unknown"),
                            object_part=img_data.get("object_part", "unknown"),
                            confidence=float(img_data.get("confidence", 0.0)),
                            is_clear=img_data.get("is_clear", False),
                            angle_sufficient=img_data.get("angle_sufficient", False),
                            lighting_adequate=img_data.get("lighting_adequate", False),
                        ))

            elapsed = (time.time() - start) * 1000
            obs = Observation(
                model_name=self.model_name,
                provider=self.PROVIDER_NAME,
                success=bool(assessments),
                assessments=assessments,
                latency_ms=elapsed,
            )
            return ObservationReport(observations=[obs], all_failed=not assessments, primary_model=self.model_name)

        except Exception as e:
            obs = Observation(
                model_name=self.model_name,
                provider=self.PROVIDER_NAME,
                success=False,
                error=str(e)[:200],
                degraded=True,
            )
            return ObservationReport(observations=[obs], all_failed=True)
