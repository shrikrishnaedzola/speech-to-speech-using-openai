"""Small text helpers shared by several sections."""
import re
import unicodedata
from typing import Any


def normalize_text(text: str) -> str:
    """Lower-case, Unicode NFC, remove punctuation, collapse spaces.

    Combining marks (category M, e.g. Hindi matras, Tamil vowel signs) are KEPT,
    otherwise Indian-script words would be broken apart.
    """
    text = unicodedata.normalize("NFC", text or "").lower()
    kept = []
    for ch in text:
        cat = unicodedata.category(ch)
        if cat.startswith("P") or cat.startswith("S"):
            kept.append(" ")  # punctuation and symbols -> space
        else:
            kept.append(ch)
    return re.sub(r"\s+", " ", "".join(kept)).strip()


# ---------- numbers said as words ----------

ENGLISH_NUMBERS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
    "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20,
    "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
}
# Common romanised Hindi number words (Hinglish callers often use these).
HINDI_NUMBERS = {
    "ek": 1, "do": 2, "teen": 3, "char": 4, "chaar": 4, "paanch": 5, "panch": 5, "chhe": 6, "che": 6,
    "saat": 7, "aath": 8, "nau": 9, "das": 10, "gyarah": 11, "barah": 12, "pandrah": 15,
    "bees": 20, "tees": 30, "chalis": 40, "pachas": 50, "pachaas": 50, "saath": 60, "sattar": 70,
    "assi": 80, "nabbe": 90, "sau": 100,
}
TENS = {20, 30, 40, 50, 60, 70, 80, 90}


def extract_numbers(text: str) -> list[float]:
    """All numbers in a text: digits (any script) and English/Hindi number words.

    "thirty five" -> 35, "I am 45" -> 45, "teen bachche" -> 3.
    """
    numbers: list[float] = []
    words = normalize_text(text).replace("-", " ").split()
    i = 0
    while i < len(words):
        word = words[i]
        if re.fullmatch(r"\d+(\.\d+)?", word):  # \d also matches Devanagari/Tamil digits
            numbers.append(float(unicodedata.numeric(word) if len(word) == 1 else _to_ascii_number(word)))
        elif word in ENGLISH_NUMBERS:
            value = ENGLISH_NUMBERS[word]
            # "thirty five" -> 35
            if value in TENS and i + 1 < len(words) and ENGLISH_NUMBERS.get(words[i + 1], 99) < 10:
                value += ENGLISH_NUMBERS[words[i + 1]]
                i += 1
            if i + 1 < len(words) and words[i + 1] == "hundred":
                value *= 100
                i += 1
            numbers.append(float(value))
        elif word in HINDI_NUMBERS:
            numbers.append(float(HINDI_NUMBERS[word]))
        i += 1
    return numbers


def _to_ascii_number(word: str) -> float:
    """Convert digits in any script (e.g. '४५') to a float."""
    return float("".join(str(unicodedata.digit(c)) if c.isdigit() else c for c in word))


def value_to_text(value: Any) -> str:
    """Saved values can be numbers, booleans or lists. Turn them into comparable text."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if isinstance(value, list):
        return ", ".join(value_to_text(v) for v in value)
    return str(value)


YES_WORDS = {"yes", "y", "true", "haan", "ha", "han", "ji", "हाँ", "हां", "ஆம்"}
NO_WORDS = {"no", "n", "false", "nahi", "nahin", "na", "नहीं", "இல்லை"}


def values_match(saved: Any, expected: Any) -> bool | None:
    """Compare a saved value with the expected value. None if there is no expected value."""
    if expected is None or (isinstance(expected, str) and not expected.strip()):
        return None
    saved_text, expected_text = normalize_text(value_to_text(saved)), normalize_text(value_to_text(expected))
    if saved_text == expected_text:
        return True
    # yes/no written differently ("haan" vs true)
    for group in (YES_WORDS, NO_WORDS):
        if saved_text in group and expected_text in group:
            return True
    # Numbers written differently ("35" vs "thirty five", "4, 7" vs "4 and 7")
    saved_nums, expected_nums = extract_numbers(saved_text), extract_numbers(expected_text)
    if saved_nums and expected_nums:
        return saved_nums == expected_nums
    return False
