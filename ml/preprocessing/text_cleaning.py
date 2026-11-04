"""Text normalisation utilities shared by data collection, training and the API.

Design rule: cleaning must be *the same function* at training time and at
inference time. If we clean training data one way and user input another way,
the model sees a distribution shift ("training/serving skew").

We deliberately do NOT translate, lowercase Devanagari, or strip
non-ASCII characters: Hindi and Kannada must survive cleaning intact.
"""
from __future__ import annotations

import html
import re
import unicodedata

from bs4 import BeautifulSoup

URL_RE = re.compile(r"https?://[^\s<>\"')\]]+", re.I)
_WS_RE = re.compile(r"\s+")
# zero-width chars that often sneak into WhatsApp forwards / CMS text
_ZW_RE = re.compile(r"[​‌‍⁠﻿]")
_EMBED_NOISE = re.compile(
    r"(pic\.twitter\.com/\S+|View this post on Instagram|A post shared by[^.]*|— [^—]{1,80}\(@\w+\) \w+ \d{1,2}, \d{4})",
    re.I,
)


def strip_html(text: str) -> str:
    """Remove tags but keep the visible text, separated by spaces."""
    if not text:
        return ""
    if "<" not in text:
        return html.unescape(text)
    soup = BeautifulSoup(text, "lxml")
    for tag in soup(["script", "style", "noscript", "iframe"]):
        tag.decompose()
    return html.unescape(soup.get_text(" "))


def normalize_unicode(text: str) -> str:
    """NFC keeps Devanagari/Kannada combining marks composed consistently.

    (NFKC would also fold compatibility characters such as full-width
    digits, but it can alter some Indic ligatures, so we use NFC.)
    """
    text = unicodedata.normalize("NFC", text)
    text = _ZW_RE.sub("", text)
    # normalise curly quotes / dashes so 'don’t' == "don't"
    return (text.replace("‘", "'").replace("’", "'")
                .replace("“", '"').replace("”", '"')
                .replace("–", "-").replace("—", "-"))


# Python's \w does NOT match Indic vowel signs/viramas (Unicode Mn/Mc), so a
# default regex tokenizer splits "प्रदर्शन" into fragments. This pattern keeps
# whole words for every Indic block (Devanagari U+0900 … Malayalam U+0D7F).
WORD_TOKEN_PATTERN = r"(?u)(?:[^\W_]|[ऀ-ൿ])(?:[^\W_]|[ऀ-ൿ])+"
_CURRENCY_RE = re.compile(r"(?<![\w₹])(?:rs\.?|inr|rupees?)\s?(?=\d)", re.I)


def normalize_currency(text: str) -> str:
    """'Rs 500', 'Rs.500', 'INR 500' -> '₹500' so all spellings match each other."""
    return _CURRENCY_RE.sub("₹", text)


def normalize_whitespace(text: str) -> str:
    return _WS_RE.sub(" ", text).strip()


def extract_urls(text: str) -> list[str]:
    return [u.rstrip(".,;:!?") for u in URL_RE.findall(text or "")]


def clean_text(text: str, remove_urls: bool = False) -> str:
    """Canonical cleaning pipeline: html -> unicode -> (urls) -> whitespace."""
    if not text:
        return ""
    text = strip_html(text)
    text = normalize_unicode(text)
    text = normalize_currency(text)
    if remove_urls:
        text = URL_RE.sub(" ", text)
    return normalize_whitespace(text)


def clean_article_body(html_body: str) -> str:
    """Clean a full article body, also removing social-embed boilerplate."""
    text = clean_text(html_body)
    return normalize_whitespace(_EMBED_NOISE.sub(" ", text))


def model_text(text: str) -> str:
    """Text as fed to ML models: cleaned, URLs replaced by a token, casefolded.

    casefold() only affects scripts with case (Latin), so Hindi is unchanged.
    """
    text = clean_text(text)
    text = URL_RE.sub(" URLTOKEN ", text)
    return normalize_whitespace(text.casefold())


def truncate(text: str, max_chars: int) -> str:
    if text is None or len(text) <= max_chars:
        return text
    cut = text[:max_chars].rsplit(" ", 1)[0]
    return cut + "…"
