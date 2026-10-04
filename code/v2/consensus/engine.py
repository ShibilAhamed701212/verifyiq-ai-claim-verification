from code.v2.models.consensus import ConsensusReport, ModelDisagreement
from code.v2.models.observation import ObservationReport


class ConsensusEngine:
    """Compares multiple model outputs and produces agreement/confidence/uncertainty."""

    def evaluate(self, observation_report: ObservationReport) -> ConsensusReport:
        observations = observation_report.observations
        successful = [o for o in observations if o.success]
        models_used = len(observations)
        models_succeeded = len(successful)

        if models_succeeded == 0:
            return ConsensusReport(
                agreement_score=0.0, confidence=0.0, uncertainty=1.0,
                models_used=models_used, models_succeeded=0, unanimous=False,
            )

        if models_succeeded == 1:
            obs = successful[0]
            avg_conf = sum(a.confidence for a in obs.assessments) / max(len(obs.assessments), 1)
            return ConsensusReport(
                agreement_score=1.0, confidence=avg_conf, uncertainty=0.0,
                models_used=models_used, models_succeeded=1, unanimous=True,
            )

        disagreements = []
        damage_types: dict[str, list[str]] = {}
        object_parts: dict[str, list[str]] = {}
        confidences = []

        for obs in successful:
            for a in obs.assessments:
                key = a.image_path
                if key not in damage_types:
                    damage_types[key] = []
                    object_parts[key] = []
                damage_types[key].append(a.damage_type)
                object_parts[key].append(a.object_part)
                confidences.append(a.confidence)

        for img_path in damage_types:
            types = damage_types[img_path]
            unique_types = set(types)
            if len(unique_types) > 1:
                disagreements.append(ModelDisagreement(
                    field=f"damage_type:{img_path}",
                    values={o.model_name: t for o, t in zip(successful, types)},
                    severity="medium" if "unknown" not in unique_types else "low",
                ))

        total_checks = sum(len(damage_types[k]) for k in damage_types)
        total_agreements = total_checks
        for d in disagreements:
            total_agreements -= len(d.values)

        agreement_score = total_agreements / max(total_checks, 1)
        avg_confidence = sum(confidences) / max(len(confidences), 1)
        uncertainty = 1.0 - agreement_score

        return ConsensusReport(
            agreement_score=round(agreement_score, 4),
            confidence=round(avg_confidence, 4),
            uncertainty=round(uncertainty, 4),
            conflicting_models=list(set(
                v for d in disagreements for v in d.values.values()
            )) or [],
            disagreements=disagreements,
            models_used=models_used,
            models_succeeded=models_succeeded,
            unanimous=agreement_score == 1.0,
        )
