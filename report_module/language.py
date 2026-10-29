"""Language support: did the agent understand and reply in the selected language?

Language detection here is simple and local (no API calls):
- Indian scripts are recognised from Unicode ranges.
- Devanagari is shared by Hindi and Marathi: we use the selected language to choose.
- Latin text is checked for common romanised Hindi words to spot Hinglish.
Romanised Tamil/Telugu/etc. are reported as "English (Latin script)" - a known limit.
"""
import re

from .call_data import CallData
from .text_utils import normalize_text

SCRIPT_RANGES = {
    "Devanagari": (0x0900, 0x097F),
    "Bengali": (0x0980, 0x09FF),
    "Tamil": (0x0B80, 0x0BFF),
    "Telugu": (0x0C00, 0x0C7F),
    "Kannada": (0x0C80, 0x0CFF),
}
SCRIPT_LANGUAGE = {"Bengali": "Bengali", "Tamil": "Tamil", "Telugu": "Telugu", "Kannada": "Kannada"}

# Frequent romanised Hindi words. Two or more in a turn = Hindi/Hinglish.
HINGLISH_WORDS = {
    "hai", "hain", "nahi", "nahin", "haan", "kya", "mera", "meri", "mujhe", "aap", "aapka", "hum", "main",
    "maine", "kaha", "bola", "ji", "theek", "thik", "accha", "acha", "kyun", "kaise", "kitne", "kitna",
    "bachche", "bacche", "saal", "umar", "gaon", "zila", "abhi", "baad", "pehle", "lekin", "aur", "bhi",
    "tha", "thi", "ho", "hoon", "hun", "sakte", "chahiye", "naam", "batao", "bataiye",
    "namaste", "namaskar", "dhanyavaad", "shukriya", "bas", "wahi", "vahi", "jila", "nahi", "kaam", "mila", "bachcha", "hi",
}
# Common English words; seen together with Hindi words they mean code-mixing (Hinglish).
ENGLISH_HINT_WORDS = {
    "the", "is", "are", "and", "my", "i", "you", "yes", "no", "what", "how", "please", "thank", "thanks",
    "time", "sample", "okay", "ok", "sorry", "school", "program", "session", "sessions", "job", "work",
    "family", "children", "district", "village", "busy", "actually", "but", "so",
}


def detect_language(text: str, selected: str) -> dict:
    """Return {"language": ..., "script": ..., "code_mixed": bool}."""
    counts = {name: 0 for name in SCRIPT_RANGES}
    latin = 0
    for ch in text:
        code = ord(ch)
        for name, (low, high) in SCRIPT_RANGES.items():
            if low <= code <= high:
                counts[name] += 1
                break
        else:
            if ch.isascii() and ch.isalpha():
                latin += 1
    script, top = max(counts.items(), key=lambda kv: kv[1])
    total = top + latin
    if total == 0:
        return {"language": None, "script": None, "code_mixed": False}

    words = set(normalize_text(text).split())
    hinglish_hits = len(words & HINGLISH_WORDS)

    if top > 0:
        language = SCRIPT_LANGUAGE.get(script) or ("Marathi" if selected == "Marathi" else "Hindi")
        mixed = latin / total > 0.2  # Indian script with a lot of English mixed in
        return {"language": language, "script": script, "code_mixed": mixed}
    if hinglish_hits >= 2 or (hinglish_hits >= 1 and len(words) <= 3):
        # Romanised Hindi with English words in it = Hinglish (code-mixed).
        mixed = len(words & ENGLISH_HINT_WORDS) > 0
        return {"language": "Hindi", "script": "Latin", "code_mixed": mixed}
    return {"language": "English", "script": "Latin", "code_mixed": False}


def _matches(detected: str | None, selected: str) -> bool:
    if detected is None:
        return True
    if selected in ("Hindi", "Marathi") and detected in ("Hindi", "Marathi"):
        return detected == selected or selected == "Hindi"
    return detected == selected


def analyze_language(data: CallData, mishearings: dict) -> dict:
    selected = data.call.language
    caller_turns, agent_turns = [], []
    for index, turn in enumerate(data.transcript):
        detected = detect_language(turn.text, selected)
        if turn.detected_language:  # provider value wins
            detected["language"] = turn.detected_language
        entry = {"index": index, **detected, "words": len(turn.text.split())}
        (caller_turns if turn.role == "caller" else agent_turns).append(entry)

    # Agent replies: very short turns ("OK", names, numbers) are not judged.
    judged = [t for t in agent_turns if t["words"] >= 3 and t["language"]]
    correct = [t for t in judged if _matches(t["language"], selected)]
    wrong_turns = [t["index"] for t in judged if not _matches(t["language"], selected)]

    detected_set = sorted({t["language"] for t in caller_turns if t["language"]})
    code_mixed_turns = sum(1 for t in caller_turns if t["code_mixed"])

    # Mishearings in non-English caller turns (or all of them in a non-English call).
    lang_by_index = {t["index"]: t["language"] for t in caller_turns}
    language_mishearings = 0
    for item in mishearings["items"]:
        lang = lang_by_index.get(item.get("transcript_index"))
        if (lang and lang != "English") or (lang is None and selected != "English"):
            language_mishearings += 1

    return {
        "selected": selected,
        "detected_caller_languages": detected_set,
        "caller_turn_languages": {t["index"]: t["language"] for t in caller_turns},
        "agent_turns_judged": len(judged),
        "agent_correct_language_turns": len(correct),
        "agent_correct_language_pct": round(len(correct) / len(judged), 3) if judged else None,
        "agent_wrong_language_turn_indexes": wrong_turns,
        "code_mixed_caller_turns": code_mixed_turns,
        "code_mixing_rating": data.ratings.code_mixing,
        "language_mishearings": language_mishearings,
        "detection_note": "Detected locally from script and common Hinglish words. Romanised Tamil/Telugu/"
                          "Kannada/Bengali/Marathi text is not recognised.",
    }


SENTENCE_END_RE = re.compile(r"[.?!।॥…]\s*$")
