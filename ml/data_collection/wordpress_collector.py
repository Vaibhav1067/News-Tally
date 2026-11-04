"""Collector for fact-check sites that expose the public WordPress REST API.

``GET {base}/wp-json/wp/v2/posts`` is the same data the site's own front-end
and RSS feed use. We request only the fields we need via ``_fields`` and
paginate politely.

What we STORE per article (copyright-aware):
* headline, URL, date, publisher tags
* the short "Claim:" text (the circulating claim, a few sentences at most)
* ONE conclusion sentence as the explanation
We do NOT store the full article body — users are always sent to the original.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional

from ml.config import RAW_DIR
from ml.data_collection.claim_extractor import extract_claim_and_fact, extract_conclusion, short_explanation
from ml.data_collection.polite_http import AccessDenied, PoliteSession
from ml.data_collection.schema import FactCheckRecord, make_claim_id
from ml.data_collection.sources import WordPressSource
from ml.data_collection.topics import infer_category
from ml.data_collection.verdict_normalizer import normalize_verdict
from ml.preprocessing.text_cleaning import clean_article_body, clean_text

log = logging.getLogger(__name__)

POST_FIELDS = "id,date,link,title,excerpt,content,categories"


class WordPressCollector:
    def __init__(self, source: WordPressSource, session: Optional[PoliteSession] = None):
        self.source = source
        self.http = session or PoliteSession()
        self._categories: Optional[dict[int, str]] = None
        self.stats = {"pages_fetched": 0, "posts_seen": 0, "kept": 0,
                      "dropped_no_verdict": 0, "dropped_no_text": 0, "errors": 0}

    @property
    def api(self) -> str:
        return f"{self.source.base_url}/wp-json/wp/v2"

    def category_names(self) -> dict[int, str]:
        """Map category id -> name (one or two requests, cached)."""
        if self._categories is None:
            self._categories = {}
            page = 1
            while page <= 5:
                resp = self.http.get(f"{self.api}/categories",
                                     params={"per_page": 100, "page": page, "_fields": "id,name"})
                if resp.status_code != 200:
                    break
                items = resp.json()
                self._categories.update({c["id"]: clean_text(c["name"]) for c in items})
                if len(items) < 100:
                    break
                page += 1
        return self._categories

    def iter_posts(self, max_pages: int, per_page: int = 50) -> Iterator[dict]:
        params = {"per_page": per_page, "_fields": POST_FIELDS, "orderby": "date", "order": "desc"}
        if self.source.category_ids:
            params["categories"] = ",".join(map(str, self.source.category_ids))
        if self.source.exclude_category_ids:
            params["categories_exclude"] = ",".join(map(str, self.source.exclude_category_ids))
        for page in range(1, max_pages + 1):
            resp = self.http.get(f"{self.api}/posts", params={**params, "page": page})
            if resp.status_code == 400:  # WordPress returns 400 past the last page
                break
            resp.raise_for_status()
            posts = resp.json()
            self.stats["pages_fetched"] += 1
            log.info("[%s] page %d: %d posts", self.source.key, page, len(posts))
            yield from posts
            total_pages = int(resp.headers.get("X-WP-TotalPages", page))
            if page >= total_pages or not posts:
                break

    def parse_post(self, post: dict) -> Optional[FactCheckRecord]:
        src = self.source
        title = clean_text(post.get("title", {}).get("rendered", ""))
        url = post.get("link", "")
        body = clean_article_body(post.get("content", {}).get("rendered", ""))
        excerpt = clean_text(post.get("excerpt", {}).get("rendered", "")).replace("[…]", "").strip()
        if not title or not url:
            self.stats["dropped_no_text"] += 1
            return None

        claim, fact = extract_claim_and_fact(body)
        conclusion = extract_conclusion(body)
        # Headline first (most deliberate verdict wording), then conclusion, then fact line.
        verdict, rule, matched = normalize_verdict(title, conclusion, fact)
        if verdict is None and src.require_verdict:
            self.stats["dropped_no_verdict"] += 1
            return None

        names = [self.category_names().get(cid, "") for cid in post.get("categories", [])]
        topical = [n for n in names if n and n not in src.generic_categories]
        if topical:
            category, category_source = topical[0], "publisher_tag"
        else:
            category = infer_category(f"{claim or ''} {title}")
            category_source = "keyword_inferred" if category else None

        return FactCheckRecord(
            claim_id=make_claim_id(src.publisher, url),
            claim_text=claim or title,
            claim_source="claim_field" if claim else "title",
            fact_check_title=title,
            fact_check_url=url,
            verdict=verdict.value if verdict else None,
            verdict_raw=matched,
            verdict_rule=rule,
            explanation=short_explanation(conclusion, fact, excerpt),
            category=category,
            category_source=category_source,
            language=src.language,
            publisher=src.publisher,
            publication_date=(post.get("date") or "")[:10] or None,
        )

    def collect(self, max_pages: int = 5, per_page: int = 50) -> list[FactCheckRecord]:
        records: list[FactCheckRecord] = []
        try:
            for post in self.iter_posts(max_pages=max_pages, per_page=per_page):
                self.stats["posts_seen"] += 1
                try:
                    rec = self.parse_post(post)
                except Exception as exc:  # one bad post must not kill the run
                    self.stats["errors"] += 1
                    log.exception("parse failed for %s: %s", post.get("link"), exc)
                    continue
                if rec:
                    records.append(rec)
                    self.stats["kept"] += 1
        except AccessDenied as exc:
            log.error("[%s] access denied: %s", self.source.key, exc)
            self.stats["access_denied"] = str(exc)
        return records


def save_raw(records: list[FactCheckRecord], source_key: str, out_dir: Path = RAW_DIR) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = out_dir / f"{source_key}_{stamp}.jsonl"
    with path.open("w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r.to_dict(), ensure_ascii=False) + "\n")
    return path
