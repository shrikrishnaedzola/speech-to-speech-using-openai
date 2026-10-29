"""Voice quality: tester ratings, optional automatic MOS, and audio issues from logs."""
import logging
from pathlib import Path

from .call_data import CallData
from .language import SENTENCE_END_RE
from .text_utils import normalize_text

log = logging.getLogger(__name__)

RATING_KEYS = ["naturalness", "clarity", "pronunciation", "accent_fit", "politeness"]


def predict_mos(wav_path: str) -> dict:
    """Optional: UTMOS22 strong (via torch.hub tarepan/SpeechMOS, MIT code).

    Needs `pip install -e ".[mos]"`. The model is downloaded on first use.
    Returns {"mos": float} or {"mos": None, "reason": ...} - never raises.
    """
    try:
        import soundfile as sf
        import torch
        import torchaudio
    except ImportError:
        return {"mos": None, "reason": "MOS packages not installed (pip install -e \".[mos]\")."}
    if not Path(wav_path).exists():
        return {"mos": None, "reason": "Agent audio file not found."}
    try:
        wave, sr = sf.read(wav_path, dtype="float32", always_2d=True)
        tensor = torch.from_numpy(wave.mean(axis=1)).unsqueeze(0)  # mono, shape (1, time)
        if sr != 16000:
            tensor = torchaudio.functional.resample(tensor, sr, 16000)
        predictor = torch.hub.load("tarepan/SpeechMOS:v1.2.0", "utmos22_strong", trust_repo=True)
        with torch.no_grad():
            score = float(predictor(tensor, 16000).mean())
        return {"mos": round(score, 2), "model": "UTMOS22 strong"}
    except Exception as exc:  # report the problem instead of failing the whole report
        log.warning("MOS prediction failed: %s", exc)
        return {"mos": None, "reason": f"MOS prediction failed: {exc}"}


def detect_audio_issues(data: CallData, long_silence_ms: float) -> dict:
    # Long silences: the caller waited more than X ms for a reply.
    long_silences = [
        {"turn": m.turn, "latency_ms": round(m.latency_ms)} for m in data.turn_metrics if m.latency_ms > long_silence_ms
    ]

    # Agent talking over the caller: barge-in events, else the counter.
    talk_over = [e for e in data.events if e.type in ("barge_in", "agent_talk_over")]
    talk_over_count = len(talk_over) or data.interruptions

    # Cut-off sentences: an agent turn that stops mid-sentence and the caller speaks next.
    cut_off = []
    for i, turn in enumerate(data.transcript[:-1]):
        nxt = data.transcript[i + 1]
        if turn.role == "agent" and nxt.role == "caller" and len(turn.text.split()) > 3 \
                and not SENTENCE_END_RE.search(turn.text.strip()):
            cut_off.append({"index": i, "text": turn.text[-80:]})

    # Repeated phrases: the same agent sentence said 3+ times, or twice in a row.
    agent_texts = [(i, normalize_text(t.text)) for i, t in enumerate(data.transcript) if t.role == "agent"]
    counts: dict[str, int] = {}
    for _, text in agent_texts:
        if len(text.split()) >= 3:
            counts[text] = counts.get(text, 0) + 1
    repeated = [{"text": text, "times": n} for text, n in counts.items() if n >= 3]
    for (i, a), (_, b) in zip(agent_texts, agent_texts[1:]):
        if a == b and len(a.split()) >= 3 and not any(r["text"] == a for r in repeated):
            repeated.append({"text": a, "times": 2})

    return {
        "long_silences": long_silences,
        "talk_over_count": talk_over_count,
        "cut_off_sentences": cut_off,
        "repeated_phrases": repeated,
    }


def analyze_voice_quality(data: CallData, settings: dict) -> dict:
    ratings = {key: getattr(data.ratings, key) for key in RATING_KEYS}
    given = [v for v in ratings.values() if v is not None]

    if settings["mos"]["enabled"] and data.agent_audio_path:
        mos = predict_mos(data.agent_audio_path)
    elif settings["mos"]["enabled"]:
        mos = {"mos": None, "reason": "No agent audio recorded for this call."}
    else:
        mos = {"mos": None, "reason": "Automatic MOS is turned off in settings."}

    return {
        "ratings": ratings,
        "ratings_avg": round(sum(given) / len(given), 2) if given else None,
        "ratings_count": len(given),
        "tester_notes": data.ratings.notes,
        "mos": mos,
        "issues": detect_audio_issues(data, settings["long_silence_ms"]),
    }
