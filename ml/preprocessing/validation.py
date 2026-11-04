"""Row-level data validation. Invalid rows are reported, not silently fixed."""
from __future__ import annotations

from urllib.parse import urlparse

import pandas as pd

from ml.data_collection.schema import REQUIRED_FIELDS, Verdict

VALID_VERDICTS = {v.value for v in Verdict}


def validate_row(row: dict) -> list[str]:
    errors = []
    for f in REQUIRED_FIELDS:
        if not row.get(f) or (isinstance(row.get(f), float) and pd.isna(row.get(f))):
            errors.append(f"missing:{f}")
    url = row.get("fact_check_url") or ""
    p = urlparse(str(url))
    if p.scheme not in ("http", "https") or not p.netloc:
        if "#row" not in str(url):  # imported datasets may lack URLs
            errors.append("invalid_url")
    v = row.get("verdict")
    if v is not None and not (isinstance(v, float) and pd.isna(v)) and v not in VALID_VERDICTS:
        errors.append(f"invalid_verdict:{v}")
    text = str(row.get("claim_text") or "")
    if 0 < len(text) < 10:
        errors.append("claim_too_short")
    if len(text) > 2000:
        errors.append("claim_too_long")
    d = row.get("publication_date")
    if d and not (isinstance(d, float) and pd.isna(d)):
        try:
            pd.Timestamp(d)
        except (ValueError, TypeError):
            errors.append("invalid_date")
    return errors


def validate_frame(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split into (valid, invalid-with-reasons)."""
    reasons = df.apply(lambda r: validate_row(r.to_dict()), axis=1)
    bad = reasons.map(bool)
    invalid = df[bad].copy()
    invalid["validation_errors"] = reasons[bad].map(";".join)
    return df[~bad].reset_index(drop=True), invalid.reset_index(drop=True)
