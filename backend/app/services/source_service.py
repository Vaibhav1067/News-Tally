"""Source evidence engine.

What we can honestly say about a domain, from our own data:
* whether it is one of the fact-checkers our dataset comes from;
* how many collected fact-checks MENTION the outlet by name (e.g. Alt News
  "Media misreport: ANI ..."), and the verdicts of those fact-checks.

What we deliberately do NOT do:
* compute a "credibility score" or "false-news ratio". Being mentioned in a
  fact-check is not the same as publishing misinformation: big outlets are
  mentioned more because they are big, and fact-checks sometimes cite an
  outlet as the *correct* source.
"""
from __future__ import annotations

import re
from typing import Optional
from urllib.parse import urlparse

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import FactCheck, Source

# Public, factual directory data only (name <-> domain). No ratings.
KNOWN_SOURCES = [
    ("factly.in", "Factly", "fact_checker", ["Factly"]),
    ("altnews.in", "Alt News", "fact_checker", ["Alt News"]),
    ("boomlive.in", "BOOM Live", "fact_checker", ["BOOM Live", "BOOM"]),
    ("pib.gov.in", "Press Information Bureau", "government", ["PIB", "PIB Fact Check"]),
    ("aninews.in", "ANI", "news_outlet", ["ANI"]),
    ("ndtv.com", "NDTV", "news_outlet", ["NDTV"]),
    ("timesofindia.indiatimes.com", "The Times of India", "news_outlet", ["Times of India", "TOI"]),
    ("hindustantimes.com", "Hindustan Times", "news_outlet", ["Hindustan Times"]),
    ("indianexpress.com", "The Indian Express", "news_outlet", ["Indian Express"]),
    ("thehindu.com", "The Hindu", "news_outlet", ["The Hindu"]),
    ("indiatoday.in", "India Today", "news_outlet", ["India Today", "Aaj Tak"]),
    ("aajtak.in", "Aaj Tak", "news_outlet", ["Aaj Tak"]),
    ("abplive.com", "ABP Live", "news_outlet", ["ABP"]),
    ("zeenews.india.com", "Zee News", "news_outlet", ["Zee News"]),
    ("republicworld.com", "Republic", "news_outlet", ["Republic TV", "Republic Bharat"]),
    ("news18.com", "News18", "news_outlet", ["News18"]),
    ("opindia.com", "OpIndia", "news_outlet", ["OpIndia"]),
    ("thewire.in", "The Wire", "news_outlet", ["The Wire"]),
    ("scroll.in", "Scroll", "news_outlet", ["Scroll.in"]),
    ("thequint.com", "The Quint", "news_outlet", ["The Quint"]),
    ("timesnownews.com", "Times Now", "news_outlet", ["Times Now"]),
    ("dainikbhaskar.com", "Dainik Bhaskar", "news_outlet", ["Dainik Bhaskar"]),
    ("jagran.com", "Dainik Jagran", "news_outlet", ["Dainik Jagran"]),
    ("amarujala.com", "Amar Ujala", "news_outlet", ["Amar Ujala"]),
    ("youtube.com", "YouTube", "platform", []),
    ("x.com", "X (Twitter)", "platform", []),
    ("twitter.com", "X (Twitter)", "platform", []),
    ("facebook.com", "Facebook", "platform", []),
    ("instagram.com", "Instagram", "platform", []),
]

LIMITATIONS = [
    "Mentions are counted by outlet name inside collected fact-checks; a mention can be neutral or even supportive.",
    "Coverage reflects which claims Factly and Alt News chose to check, not how accurate an outlet is overall.",
    "No credibility score is computed. Judge each claim on its evidence.",
]


def normalize_domain(url_or_domain: str) -> Optional[str]:
    if not url_or_domain:
        return None
    host = urlparse(url_or_domain if "//" in url_or_domain else f"//{url_or_domain}").hostname or ""
    host = host.lower()
    return host[4:] if host.startswith("www.") else host or None


def seed_sources(db: Session) -> None:
    for domain, name, stype, aliases in KNOWN_SOURCES:
        if not db.scalar(select(Source).where(Source.domain == domain)):
            db.add(Source(domain=domain, name=name, source_type=stype, aliases=aliases))
    db.commit()
    refresh_source_evidence(db)


def _mention_query(aliases: list[str]):
    conds = []
    for a in aliases:
        like = f"%{a}%"
        conds += [FactCheck.title.like(like), FactCheck.claim_text.like(like), FactCheck.explanation.like(like)]
    return select(FactCheck).where(or_(*conds)) if conds else None


def _word_match(alias: str, fc: FactCheck) -> bool:
    pat = re.compile(rf"(?<!\w){re.escape(alias)}(?!\w)")
    return any(pat.search(t or "") for t in (fc.title, fc.claim_text, fc.explanation))


def mentions_for(db: Session, src: Source) -> list[FactCheck]:
    if src.source_type == "fact_checker":
        return list(db.scalars(select(FactCheck).where(FactCheck.source_name == src.name)))
    q = _mention_query(src.aliases or [])
    if q is None:
        return []
    # SQL LIKE is a coarse prefilter; confirm whole-word matches in Python ("ANI" must not match "ANIMAL").
    return [fc for fc in db.scalars(q) if any(_word_match(a, fc) for a in src.aliases)]


def refresh_source_evidence(db: Session) -> None:
    for src in db.scalars(select(Source)):
        fcs = mentions_for(db, src)
        breakdown: dict[str, int] = {}
        for fc in fcs:
            breakdown[fc.verdict or "UNPARSED"] = breakdown.get(fc.verdict or "UNPARSED", 0) + 1
        dates = sorted(str(fc.publication_date) for fc in fcs if fc.publication_date)
        src.available_fact_checks = len(fcs)
        src.evidence_summary = {"verdict_breakdown": breakdown,
                                "first": dates[0] if dates else None, "last": dates[-1] if dates else None}
    db.commit()


def source_info(db: Session, url: Optional[str]) -> dict:
    if not url:
        return {"domain": None, "status": "no_url", "coverage_note": "No URL was submitted.",
                "limitations": []}
    domain = normalize_domain(url)
    src = None
    if domain:
        # match subdomains too (e.g. m.ndtv.com -> ndtv.com)
        for candidate in [domain] + [".".join(domain.split(".")[i:]) for i in range(1, domain.count("."))]:
            src = db.scalar(select(Source).where(Source.domain == candidate))
            if src:
                break
    if not src:
        return {"domain": domain, "status": "insufficient_history",
                "coverage_note": "Insufficient source history: this domain is not in our source directory "
                                 "and no collected fact-check mentions it.",
                "limitations": LIMITATIONS}
    fcs = mentions_for(db, src)
    fcs.sort(key=lambda f: str(f.publication_date or ""), reverse=True)
    examples = [{"id": f.id, "title": f.title, "verdict": f.verdict, "url": f.original_url,
                 "publication_date": str(f.publication_date) if f.publication_date else None} for f in fcs[:5]]
    if src.source_type == "fact_checker":
        status, note = "fact_checker", (f"{src.name} is one of the fact-checking publishers this dataset is built "
                                        f"from ({len(fcs)} of its fact-checks collected).")
    elif len(fcs) == 0:
        status, note = "insufficient_history", (f"{src.name} is a known {src.source_type.replace('_', ' ')}, but "
                                                "no collected fact-check mentions it. Insufficient source history.")
    else:
        status, note = "known_source", (f"{len(fcs)} collected fact-check(s) mention {src.name} by name. "
                                        "This is coverage information, not a rating.")
    return {"domain": domain, "name": src.name, "source_type": src.source_type, "status": status,
            "mentions_in_dataset": len(fcs),
            "verdict_breakdown": (src.evidence_summary or {}).get("verdict_breakdown", {}),
            "example_fact_checks": examples, "coverage_note": note, "limitations": LIMITATIONS}
