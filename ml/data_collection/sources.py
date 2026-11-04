"""Registry of fact-check sources and how (or whether) we may collect from them.

Access status was checked on 2026-11-04 from a normal residential connection:

* Factly (factly.in)        robots.txt allows /wp-json; public WordPress REST API.
* Alt News (altnews.in)     robots.txt allows /wp-json; public WordPress REST API
                            (separate English and Hindi installs).
* BOOM Live (boomlive.in)   returns HTTP 403 for robots.txt and feeds -> NOT collected.
* PIB Fact Check            factcheck.pib.gov.in returns 401/"inaccessible" -> NOT collected.
                            PIB verdicts appear inside Factly articles as embedded posts
                            but we do not extract them as separate records.

Re-check these before every collection run: terms and access can change.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class WordPressSource:
    key: str
    publisher: str
    base_url: str  # WordPress root (where /wp-json lives)
    language: str
    homepage: str
    # Restrict to fact-check categories when the site also publishes other content.
    category_ids: tuple[int, ...] = ()
    exclude_category_ids: tuple[int, ...] = ()
    # Only keep posts whose verdict could be parsed (sites mixing news + fact-checks).
    require_verdict: bool = False
    # Category names that carry no topical meaning (language tags etc.).
    generic_categories: frozenset = field(default_factory=frozenset)
    notes: str = ""


SOURCES: dict[str, WordPressSource] = {
    "factly_en": WordPressSource(
        key="factly_en", publisher="Factly", base_url="https://factly.in", language="en",
        homepage="https://factly.in", category_ids=(358,),  # 358 = "English" fact-checks (under "Fake News")
        generic_categories=frozenset({"Fake News", "English", "Fact Check", "Fake News - Kannada",
                                       "Uncategorized", "Stories", "Featured"}),
        notes="Articles contain an explicit 'Claim: ... Fact: ...' block.",
    ),
    "factly_kn": WordPressSource(
        key="factly_kn", publisher="Factly", base_url="https://factly.in", language="kn",
        homepage="https://factly.in", category_ids=(376,),  # 376 = "Fake News - Kannada"
        generic_categories=frozenset({"Fake News", "English", "Fact Check", "Fake News - Kannada",
                                       "Uncategorized", "Stories", "Featured"}),
        notes="Kannada-language fact-checks.",
    ),
    "altnews_en": WordPressSource(
        key="altnews_en", publisher="Alt News", base_url="https://www.altnews.in", language="en",
        homepage="https://www.altnews.in", require_verdict=True,
        generic_categories=frozenset({"Featured", "Uncategorized", "News", "Compilation"}),
        notes="Mixes fact-checks with reporting; only posts with a parseable verdict are kept.",
    ),
    "altnews_hi": WordPressSource(
        key="altnews_hi", publisher="Alt News", base_url="https://www.altnews.in/hindi", language="hi",
        homepage="https://www.altnews.in/hindi", require_verdict=True,
        generic_categories=frozenset({"Featured", "Uncategorized"}),
        notes="Hindi edition. Mixes fact-checks with reporting.",
    ),
}


@dataclass(frozen=True)
class UnavailableSource:
    publisher: str
    homepage: str
    reason: str
    checked_on: str


UNAVAILABLE_SOURCES = [
    UnavailableSource("BOOM Live", "https://www.boomlive.in",
                      "HTTP 403 for robots.txt and RSS with an honest bot User-Agent; not bypassed.", "2026-11-04"),
    UnavailableSource("PIB Fact Check", "https://factcheck.pib.gov.in",
                      "HTTP 401 / 'URL is inaccessible'. Primary channel is X (login-gated); not bypassed.", "2026-11-04"),
]


def get_source(key: str) -> Optional[WordPressSource]:
    return SOURCES.get(key)
