import hashlib

from verifyiq.v2.models.fraud import BehavioralFraudResult


class BehavioralFraudDetector:
    """Detects repeated claims, image reuse, escalation patterns."""

    def __init__(self):
        self._claim_history: dict[str, list[dict]] = {}

    def load_history(self, csv_path: str):
        import csv
        try:
            with open(csv_path) as f:
                reader = csv.DictReader(f)
                for row in reader:
                    uid = row.get("user_id", "")
                    if uid not in self._claim_history:
                        self._claim_history[uid] = []
                    self._claim_history[uid].append(row)
        except Exception:
            pass

    def check(self, user_id: str, current_damage: str, current_images: list[str]) -> BehavioralFraudResult:
        result = BehavioralFraudResult()
        history = self._claim_history.get(user_id, [])
        if not history:
            return result

        result.repeated_claims = len(history)
        if result.repeated_claims > 3:
            result.flags.append("frequent_claims")
            result.fraud_score += 0.3

        current_hashes = set()
        for p in current_images:
            try:
                with open(p, "rb") as f:
                    current_hashes.add(hashlib.sha256(f.read()).hexdigest())
            except Exception:
                pass

        if current_hashes:
            for past_claim in history:
                past_images = past_claim.get("image_paths", "").split(",")
                for p_img in past_images:
                    p_img = p_img.strip()
                    try:
                        with open(p_img, "rb") as f:
                            if hashlib.sha256(f.read()).hexdigest() in current_hashes:
                                result.image_reuse_count += 1
                    except Exception:
                        pass

        if result.image_reuse_count > 0:
            result.flags.append("image_reuse")
            result.fraud_score += 0.4

        severity_order = ["scratch", "dent", "crack", "glass_shatter", "broken_part"]
        if current_damage and history:
            current_idx = next((i for i, s in enumerate(severity_order) if s in current_damage.lower()), -1)
            if current_idx >= 0:
                prev_idxes = [
                    next((i for i, s in enumerate(severity_order) if s in c.get("damage_type", "").lower()), -1)
                    for c in history
                ]
                valid_prev = [i for i in prev_idxes if i >= 0]
                if valid_prev and current_idx > max(valid_prev):
                    result.escalation_pattern = True
                    result.flags.append("severity_escalation")
                    result.fraud_score += 0.2

        result.fraud_score = min(1.0, result.fraud_score)
        return result
