"""Pull the *claim* and the *conclusion* out of a fact-check article.

Why this matters (data leakage!): a fact-check headline usually contains the
verdict ("... is a deepfake"). If we trained a classifier on headlines it would
just learn the words "deepfake"/"old"/"fake" and look brilliant on paper while
being useless on real user input, which never contains the verdict.

Factly articles include an explicit ``Claim: ... Fact: ...`` block — the claim
as it circulated, written *before* the verdict. That is the text we train on.
When no claim block exists (most Alt News posts) we keep the headline for
retrieval/display only and mark ``claim_source = "title"`` so training code
can exclude or mask it.
"""
from __future__ import annotations

import re
from typing import Optional

from ml.preprocessing.text_cleaning import normalize_whitespace, truncate

# "Claim:" / "Fact:" markers in English, Kannada and Hindi
_CLAIM_FACT_RE = re.compile(
    r"(?:Claim|ಕ್ಲೇಮ್|ಹೇಳಿಕೆ|दावा)\s*[:：]\s*(.{8,600}?)\s*"
    r"(?:Fact|ಫ್ಯಾಕ್ಟ್|ನಿಜಾಂಶ|तथ्य|सच)\s*[:：]\s*(.{8,500}?[.!?।])?",
    re.S,
)
_CONCLUSION_RE = re.compile(
    r"(?:To sum (?:it )?up|To conclude|In conclusion|In summary|"
    r"ಕೊನೆಯದಾಗಿ ಹೇಳುವುದಾದರೆ|ಸಂಕ್ಷಿಪ್ತವಾಗಿ ಹೇಳುವುದಾದರೆ|"
    r"कुल मिलाकर|निष्कर्ष)\s*[,:]?\s*(.{10,500}?[.!?।])",
    re.S | re.I,
)


def extract_claim_and_fact(body: str) -> tuple[Optional[str], Optional[str]]:
    m = _CLAIM_FACT_RE.search(body)
    if not m:
        return None, None
    claim = normalize_whitespace(m.group(1))
    fact = normalize_whitespace(m.group(2)) if m.group(2) else None
    return claim, fact


def extract_conclusion(body: str) -> Optional[str]:
    matches = list(_CONCLUSION_RE.finditer(body))
    if not matches:
        return None
    # the *last* "to sum up" is the article's actual conclusion
    return normalize_whitespace(matches[-1].group(1))


def short_explanation(conclusion: Optional[str], fact: Optional[str], excerpt: Optional[str],
                      max_chars: int = 300) -> Optional[str]:
    """One short sentence of explanation — never the full article (copyright)."""
    for candidate in (conclusion, fact, excerpt):
        if candidate:
            return truncate(candidate, max_chars)
    return None
