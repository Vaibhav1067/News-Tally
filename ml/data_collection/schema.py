"""Common record schema for every fact-check, regardless of where it came from.

Each source publishes verdicts differently ("Fake", "Misleading", "Old video
shared as recent", "भ्रामक", ...). We keep the publisher's own wording in
``verdict_raw`` and map it to a small shared vocabulary in ``verdict``.
If the mapping is not confident, ``verdict`` stays ``None`` rather than being
forced into TRUE/FALSE.
"""
from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class Verdict(str, Enum):
    FALSE = "FALSE"
    MISLEADING = "MISLEADING"
    TRUE = "TRUE"
    UNVERIFIED = "UNVERIFIED"
    OUTDATED = "OUTDATED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


@dataclass
class FactCheckRecord:
    claim_id: str
    claim_text: str
    claim_source: str  # "claim_field" | "title" — where claim_text came from
    fact_check_title: str
    fact_check_url: str
    verdict: Optional[str]
    verdict_raw: Optional[str]
    verdict_rule: Optional[str]  # which normalisation rule matched (auditability)
    explanation: Optional[str]  # short conclusion sentence only (copyright-aware)
    category: Optional[str]
    category_source: Optional[str]  # "publisher_tag" | "keyword_inferred" | None
    language: Optional[str]
    publisher: str
    publication_date: Optional[str]
    collection_date: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )

    def to_dict(self) -> dict:
        return asdict(self)


def make_claim_id(publisher: str, url: str) -> str:
    """Deterministic id: the same article always gets the same id across runs."""
    digest = hashlib.sha1(f"{publisher}|{url}".encode("utf-8")).hexdigest()[:16]
    return f"{publisher.lower().replace(' ', '')}-{digest}"


REQUIRED_FIELDS = ("claim_id", "claim_text", "fact_check_url", "publisher")
