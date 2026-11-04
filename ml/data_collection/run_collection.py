"""CLI entry point: collect fact-checks from all permitted sources.

    python -m ml.data_collection.run_collection --pages 10
    python -m ml.data_collection.run_collection --sources factly_en --pages 2

Writes one JSONL file per source into data/raw/ and appends a run summary to
data/metadata/collection_log.jsonl (what was fetched, kept and dropped).
"""
from __future__ import annotations

import argparse
import json
import logging
import time
from datetime import datetime, timezone

from ml.config import METADATA_DIR
from ml.data_collection.polite_http import PoliteSession
from ml.data_collection.sources import SOURCES, UNAVAILABLE_SOURCES
from ml.data_collection.wordpress_collector import WordPressCollector, save_raw

log = logging.getLogger("collection")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--sources", nargs="*", default=list(SOURCES), choices=list(SOURCES))
    ap.add_argument("--pages", type=int, default=5, help="max pages per source")
    ap.add_argument("--per-page", type=int, default=50)
    args = ap.parse_args()

    for src in UNAVAILABLE_SOURCES:
        log.warning("Skipping %s: %s", src.publisher, src.reason)

    session = PoliteSession()
    run = {"started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "pages": args.pages, "per_page": args.per_page, "sources": {}}
    for key in args.sources:
        t0 = time.time()
        collector = WordPressCollector(SOURCES[key], session=session)
        records = collector.collect(max_pages=args.pages, per_page=args.per_page)
        path = save_raw(records, key) if records else None
        stats = {**collector.stats, "output": str(path) if path else None,
                 "seconds": round(time.time() - t0, 1)}
        run["sources"][key] = stats
        log.info("[%s] %s", key, stats)

    run["finished_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    run["unavailable"] = [s.__dict__ for s in UNAVAILABLE_SOURCES]
    with (METADATA_DIR / "collection_log.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(run, ensure_ascii=False) + "\n")
    log.info("Done. Run summary appended to %s", METADATA_DIR / "collection_log.jsonl")


if __name__ == "__main__":
    main()
