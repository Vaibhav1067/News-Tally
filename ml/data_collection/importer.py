"""Import manually downloaded fact-check datasets (CSV / JSON / JSONL).

Use this when a source cannot be collected automatically (e.g. a Kaggle or
Zenodo dataset you downloaded yourself after accepting its licence).

Put the file in ``data/external/`` and pass a column mapping:

    python -m ml.data_collection.importer data/external/my.csv \
        --publisher "Some Dataset (CC-BY 4.0)" \
        --map claim_text=text verdict_raw=label fact_check_url=url

Unknown verdict strings stay ``None`` instead of being guessed.
"""
from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Optional

import pandas as pd

from ml.data_collection.schema import FactCheckRecord, Verdict, make_claim_id
from ml.data_collection.verdict_normalizer import normalize_verdict
from ml.data_collection.wordpress_collector import save_raw
from ml.preprocessing.language import detect_language
from ml.preprocessing.text_cleaning import clean_text, truncate

log = logging.getLogger(__name__)

# Common explicit labels used by public datasets
EXPLICIT_LABELS = {
    "false": Verdict.FALSE, "fake": Verdict.FALSE, "pants on fire": Verdict.FALSE, "0": None,
    "misleading": Verdict.MISLEADING, "missing context": Verdict.MISLEADING, "half true": Verdict.MISLEADING,
    "partly false": Verdict.MISLEADING, "true": Verdict.TRUE, "real": Verdict.TRUE, "correct": Verdict.TRUE,
    "unverified": Verdict.UNVERIFIED, "unproven": Verdict.UNVERIFIED, "outdated": Verdict.OUTDATED,
    "old": Verdict.OUTDATED, "insufficient evidence": Verdict.INSUFFICIENT_EVIDENCE,
}


def map_label(raw: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None, None
    key = str(raw).strip().lower()
    if key in EXPLICIT_LABELS:
        v = EXPLICIT_LABELS[key]
        return (v.value if v else None), "explicit_label"
    v, rule, _ = normalize_verdict(str(raw))
    return (v.value if v else None), rule


def load_table(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".csv":
        return pd.read_csv(path)
    if path.suffix.lower() == ".jsonl":
        return pd.read_json(path, lines=True)
    if path.suffix.lower() == ".json":
        return pd.DataFrame(json.loads(path.read_text(encoding="utf-8")))
    raise ValueError(f"Unsupported file type: {path.suffix}")


def import_dataset(path: Path, publisher: str, mapping: dict[str, str]) -> list[FactCheckRecord]:
    df = load_table(path)
    missing = [col for col in mapping.values() if col not in df.columns]
    if missing:
        raise ValueError(f"Columns not found in {path.name}: {missing}. Available: {list(df.columns)}")

    def col(row, field):
        name = mapping.get(field)
        val = row.get(name) if name else None
        return None if val is None or (isinstance(val, float) and pd.isna(val)) else val

    records = []
    for i, row in df.iterrows():
        claim = clean_text(str(col(row, "claim_text") or ""))
        if len(claim) < 5:
            continue
        url = str(col(row, "fact_check_url") or f"{path.name}#row{i}")
        verdict, rule = map_label(col(row, "verdict_raw"))
        lang = col(row, "language") or detect_language(claim).code
        records.append(FactCheckRecord(
            claim_id=make_claim_id(publisher, url),
            claim_text=claim,
            claim_source="claim_field",
            fact_check_title=clean_text(str(col(row, "fact_check_title") or claim)),
            fact_check_url=url,
            verdict=verdict,
            verdict_raw=None if col(row, "verdict_raw") is None else str(col(row, "verdict_raw")),
            verdict_rule=rule,
            explanation=truncate(clean_text(str(col(row, "explanation") or "")), 300) or None,
            category=col(row, "category"),
            category_source="publisher_tag" if col(row, "category") else None,
            language=lang,
            publisher=publisher,
            publication_date=str(col(row, "publication_date"))[:10] if col(row, "publication_date") else None,
        ))
    return records


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("path", type=Path)
    ap.add_argument("--publisher", required=True, help="Dataset name + licence, used for attribution")
    ap.add_argument("--map", nargs="+", default=[], metavar="FIELD=COLUMN")
    args = ap.parse_args()
    mapping = dict(m.split("=", 1) for m in args.map)
    mapping.setdefault("claim_text", "claim_text")
    records = import_dataset(args.path, args.publisher, mapping)
    out = save_raw(records, "import_" + args.path.stem)
    log.info("Imported %d records -> %s", len(records), out)


if __name__ == "__main__":
    main()
