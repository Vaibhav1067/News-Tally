"""Language identification tuned for Indian content.

Why not just call ``langdetect``?
* It is unreliable on short texts (a 6-word WhatsApp forward).
* It cannot say "this is Hinglish" (Hindi written in Latin script, or
  Devanagari mixed with English).

So we combine two signals:
1. **Unicode script counting** — Devanagari, Kannada, Tamil, Telugu, Bengali,
   ... have their own code-point blocks. This is deterministic and very
   reliable for native-script text.
2. **langdetect** — only for Latin-script text, plus a small Hinglish
   lexicon to catch romanised Hindi.

Output codes follow ISO-639-1 ('en', 'hi', 'kn', ...) plus 'mixed' and
'unknown'.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass

SCRIPT_RANGES = {
    "hi": (0x0900, 0x097F),  # Devanagari (Hindi, Marathi, Nepali share it)
    "bn": (0x0980, 0x09FF),
    "pa": (0x0A00, 0x0A7F),
    "gu": (0x0A80, 0x0AFF),
    "or": (0x0B00, 0x0B7F),
    "ta": (0x0B80, 0x0BFF),
    "te": (0x0C00, 0x0C7F),
    "kn": (0x0C80, 0x0CFF),
    "ml": (0x0D00, 0x0D7F),
    "ur": (0x0600, 0x06FF),  # Arabic script (Urdu)
}

LANGUAGE_NAMES = {
    "en": "English", "hi": "Hindi", "bn": "Bengali", "pa": "Punjabi", "gu": "Gujarati",
    "or": "Odia", "ta": "Tamil", "te": "Telugu", "kn": "Kannada", "ml": "Malayalam",
    "ur": "Urdu", "mr": "Marathi", "hi-Latn": "Hinglish (romanised Hindi)",
    "mixed": "Mixed language", "unknown": "Unknown",
}

# Languages for which the training data actually contains examples.
SUPPORTED_FOR_MODEL = {"en", "hi", "kn"}

_HINGLISH = set(
    "hai hain nahi nahin kya kyu kyun aur ki ka ke ko se mein mai main bhi tha thi "
    "kar karo karna raha rahi rahe sab log jaldi bhai yeh ye woh wo jo sach jhooth "
    "sarkar desh share karein karen dekho dekhiye abhi zaroor hoga hogi gaya gayi".split()
)
_LATIN_WORD = re.compile(r"[A-Za-z]+")


@dataclass
class LanguageResult:
    code: str
    name: str
    confidence: float
    scripts: dict
    is_mixed: bool
    method: str
    supported_by_model: bool

    def to_dict(self) -> dict:
        return asdict(self)


def script_profile(text: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for ch in text:
        cp = ord(ch)
        if ch.isascii():
            if ch.isalpha():
                counts["latin"] = counts.get("latin", 0) + 1
            continue
        for code, (lo, hi) in SCRIPT_RANGES.items():
            if lo <= cp <= hi:
                counts[code] = counts.get(code, 0) + 1
                break
    return counts


def _langdetect(text: str) -> tuple[str, float]:
    try:
        from langdetect import DetectorFactory, detect_langs

        DetectorFactory.seed = 0  # make results deterministic
        best = detect_langs(text)[0]
        return best.lang, float(best.prob)
    except Exception:  # langdetect raises on empty / symbol-only input
        return "unknown", 0.0


def detect_language(text: str) -> LanguageResult:
    text = (text or "").strip()
    counts = script_profile(text)
    total = sum(counts.values())
    if total == 0:
        return LanguageResult("unknown", LANGUAGE_NAMES["unknown"], 0.0, counts, False, "none", False)

    shares = {k: v / total for k, v in counts.items()}
    dominant, dom_share = max(shares.items(), key=lambda kv: kv[1])
    # "mixed" when a second script holds a meaningful share (e.g. Hindi + English)
    secondary = sorted(shares.values(), reverse=True)[1] if len(shares) > 1 else 0.0
    is_mixed = secondary >= 0.2

    if dominant != "latin":
        code = dominant
        conf = round(dom_share, 3)
        method = "unicode_script"
        if is_mixed:
            return LanguageResult("mixed", f"Mixed ({LANGUAGE_NAMES.get(code, code)} + other)", conf,
                                  counts, True, method, code in SUPPORTED_FOR_MODEL)
        return LanguageResult(code, LANGUAGE_NAMES.get(code, code), conf, counts, False, method,
                              code in SUPPORTED_FOR_MODEL)

    # Latin script: English, romanised Hindi, or something else
    words = [w.lower() for w in _LATIN_WORD.findall(text)]
    hinglish_share = sum(w in _HINGLISH for w in words) / max(len(words), 1)
    if hinglish_share >= 0.2 and len(words) >= 3:
        return LanguageResult("hi-Latn", LANGUAGE_NAMES["hi-Latn"], round(min(1.0, hinglish_share * 2), 3),
                              counts, True, "hinglish_lexicon", False)
    code, prob = _langdetect(text)
    if len(words) < 4:
        # langdetect is unreliable on very short text; report lower confidence
        prob = min(prob, 0.6)
    if is_mixed:
        return LanguageResult("mixed", "Mixed (English + Indic script)", round(prob, 3), counts, True,
                              "unicode_script+langdetect", True)
    return LanguageResult(code, LANGUAGE_NAMES.get(code, code), round(prob, 3), counts, False,
                          "langdetect", code in SUPPORTED_FOR_MODEL)
