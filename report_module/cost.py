"""Cost of the call, using rates from settings.json.

Each provider/model has a list of rate items:
    {"label": ..., "usage_key": "voice_seconds", "unit": 60, "usd": 0.05}
cost of an item = usage[usage_key] / unit * usd
Items with usd = null ("rate not set") or no usage are listed but not added.
"""
from .call_data import CallData


def _rate_items(settings: dict, provider: str, model: str) -> list[dict]:
    providers = settings["cost"]["providers"]
    by_model = providers.get(provider, {})
    return by_model.get(model) or by_model.get("default") or []


def analyze_cost(data: CallData, settings: dict) -> dict:
    usage = data.usage.model_dump()
    # If the provider did not report billed seconds, fall back to call duration.
    if usage.get("voice_seconds") is None and data.call.duration_s:
        usage["voice_seconds"] = data.call.duration_s
        voice_basis = "call duration"
    else:
        voice_basis = "provider usage"

    breakdown, warnings = [], []
    total = 0.0
    for item in _rate_items(settings, data.call.provider, data.call.model):
        amount = usage.get(item["usage_key"])
        row = {
            "label": item["label"],
            "usage_key": item["usage_key"],
            "usage": amount,
            "unit": item["unit"],
            "rate_usd": item["usd"],
            "verified": item.get("verified", False),
            "usd": None,
        }
        if item["usd"] is None:
            if amount:
                warnings.append(f"No rate set for '{item['label']}' - not included in the total.")
        elif amount is not None:
            row["usd"] = round(amount / item["unit"] * item["usd"], 6)
            total += row["usd"]
        breakdown.append(row)

    if not breakdown:
        warnings.append(f"No cost rates configured for {data.call.provider} / {data.call.model}.")
    if any(r["usd"] is not None and not r["verified"] for r in breakdown):
        warnings.append("Some rates are not verified against official pricing.")

    inr_rate = settings["currency"]["inr_per_usd"]
    minutes = (data.call.duration_s or 0) / 60
    has_cost = any(r["usd"] is not None for r in breakdown)
    total = round(total, 6) if has_cost else None
    return {
        "total_usd": total,
        "total_inr": round(total * inr_rate, 4) if total is not None else None,
        "inr_per_usd": inr_rate,
        "breakdown": breakdown,
        "voice_seconds_basis": voice_basis,
        "cost_per_min_usd": round(total / minutes, 4) if total is not None and minutes else None,
        # One call: cost per completed form = the call cost if the form was completed.
        "cost_per_completed_form_usd": total if total is not None and data.call.form_completed else None,
        "projection_1000_calls_usd": round(total * 1000, 2) if total is not None else None,
        "projection_1000_calls_inr": round(total * 1000 * inr_rate, 2) if total is not None else None,
        "rates_last_updated": settings["cost"]["rates_last_updated"],
        "warnings": warnings,
    }
