"""Overall score (0-100). Same formula for every provider.

Each part gives a 0-100 score, or None when there is no data for it
(e.g. no tester ratings yet). Missing parts are left out and their weight
is shared by the others, so a call is never punished for missing data.

Part formulas (simple on purpose):
- accuracy:      70% field accuracy + 30% completion
- mishearings:   100 - 15 per unfixed - 5 per fixed (min 0); averaged with (1 - CER) when a script exists
- latency:       100 at or below "good" ms, 0 at "zero_score" ms, straight line between
- voice_quality: tester ratings average (1->0, 5->100), averaged with MOS if available
- language:      % agent turns in the right language; 80/20 with the code-mixing rating if given
- cost:          100 at or below the target cost per minute, 0 at 3x the target
"""


def _rating_to_100(value: float | None) -> float | None:
    return None if value is None else (value - 1) / 4 * 100


def _clamp(value: float) -> float:
    return max(0.0, min(100.0, value))


def part_scores(sections: dict, settings: dict) -> dict:
    acc = sections["accuracy"]
    if acc["field_accuracy"] is not None and acc["completion"] is not None:
        accuracy = 70 * acc["field_accuracy"] + 30 * acc["completion"]
    elif acc["completion"] is not None:
        accuracy = 100 * acc["completion"]
    else:
        accuracy = None

    mis = sections["mishearings"]
    mishearings = _clamp(100 - 15 * mis["unfixed"] - 5 * mis["fixed"])
    if mis["cer"] is not None:
        mishearings = (mishearings + _clamp(100 * (1 - mis["cer"]))) / 2

    lat = sections["latency"]
    th = settings["latency_thresholds_ms"]
    if lat["avg_ms"] is None:
        latency = None
    elif lat["avg_ms"] <= th["good"]:
        latency = 100.0
    else:
        latency = _clamp(100 * (th["zero_score"] - lat["avg_ms"]) / (th["zero_score"] - th["good"]))

    vq = sections["voice_quality"]
    voice_parts = [p for p in (_rating_to_100(vq["ratings_avg"]), _rating_to_100(vq["mos"].get("mos"))) if p is not None]
    voice_quality = sum(voice_parts) / len(voice_parts) if voice_parts else None

    lang = sections["language"]
    if lang["agent_correct_language_pct"] is None:
        language = None
    else:
        language = 100 * lang["agent_correct_language_pct"]
        if lang["code_mixing_rating"] is not None:
            language = 0.8 * language + 0.2 * _rating_to_100(lang["code_mixing_rating"])

    cost_per_min = sections["cost"]["cost_per_min_usd"]
    target = settings["cost"]["target_cost_per_min_usd"]
    cost = None if cost_per_min is None else _clamp(100 * (3 * target - cost_per_min) / (2 * target))

    scores = {
        "accuracy": accuracy, "mishearings": mishearings, "latency": latency,
        "voice_quality": voice_quality, "language": language, "cost": cost,
    }
    return {k: (round(v, 1) if v is not None else None) for k, v in scores.items()}


def verdict(score: float | None) -> str:
    if score is None:
        return "Not enough data"
    if score >= 75:
        return "Good"
    if score >= 50:
        return "Needs improvement"
    return "Poor"


def overall_score(parts: dict, weights: dict) -> dict:
    used = {k: weights[k] for k, v in parts.items() if v is not None and weights.get(k)}
    total_weight = sum(used.values())
    score = sum(parts[k] * w for k, w in used.items()) / total_weight if total_weight else None
    return {
        "score": round(score) if score is not None else None,
        "verdict": verdict(score),
        "parts": parts,
        "weights": weights,
        "effective_weights": {k: round(w / total_weight * 100, 1) for k, w in used.items()} if total_weight else {},
        "missing_parts": [k for k, v in parts.items() if v is None],
    }
