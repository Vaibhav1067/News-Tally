"""A small 'polite' HTTP client used by every collector.

Responsibilities:
* identify ourselves honestly with a User-Agent
* obey robots.txt (refuse to fetch disallowed paths)
* wait between requests to the same host (rate limiting)
* retry transient errors with exponential back-off
* NEVER try to get around 401/403/CAPTCHA responses — those mean "no".
"""
from __future__ import annotations

import logging
import time
import urllib.robotparser
from typing import Optional
from urllib.parse import urlparse

import requests

from ml.config import REQUEST_DELAY_SECONDS, USER_AGENT

log = logging.getLogger(__name__)


class AccessDenied(RuntimeError):
    """Raised when robots.txt or the server refuses access. Do not work around it."""


class PoliteSession:
    def __init__(self, delay: float = REQUEST_DELAY_SECONDS, user_agent: str = USER_AGENT,
                 timeout: float = 30.0, max_retries: int = 3):
        self.delay = delay
        self.timeout = timeout
        self.max_retries = max_retries
        self.user_agent = user_agent
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent, "Accept": "application/json"})
        self._robots: dict[str, urllib.robotparser.RobotFileParser] = {}
        self._last_request: dict[str, float] = {}

    # -- robots.txt -------------------------------------------------------
    def _robots_for(self, url: str) -> urllib.robotparser.RobotFileParser:
        parts = urlparse(url)
        base = f"{parts.scheme}://{parts.netloc}"
        if base not in self._robots:
            rp = urllib.robotparser.RobotFileParser()
            robots_url = f"{base}/robots.txt"
            try:
                resp = self.session.get(robots_url, timeout=self.timeout)
                if resp.status_code in (401, 403):
                    # Server refuses even robots.txt: treat whole host as off-limits.
                    rp.parse(["User-agent: *", "Disallow: /"])
                elif resp.status_code >= 400:
                    rp.parse([])  # no robots.txt => allowed by convention
                else:
                    rp.parse(resp.text.splitlines())
            except requests.RequestException as exc:
                log.warning("Could not read %s (%s); refusing to crawl host", robots_url, exc)
                rp.parse(["User-agent: *", "Disallow: /"])
            self._robots[base] = rp
        return self._robots[base]

    def allowed(self, url: str) -> bool:
        return self._robots_for(url).can_fetch(self.user_agent, url)

    # -- rate limiting ----------------------------------------------------
    def _wait_turn(self, url: str) -> None:
        host = urlparse(url).netloc
        elapsed = time.monotonic() - self._last_request.get(host, 0.0)
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)
        self._last_request[host] = time.monotonic()

    def get(self, url: str, params: Optional[dict] = None) -> requests.Response:
        if not self.allowed(url):
            raise AccessDenied(f"robots.txt disallows {url}")
        last_exc: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            self._wait_turn(url)
            try:
                resp = self.session.get(url, params=params, timeout=self.timeout)
            except requests.RequestException as exc:
                last_exc = exc
                log.warning("GET %s failed (attempt %d): %s", url, attempt, exc)
                time.sleep(2 ** attempt)
                continue
            if resp.status_code in (401, 403):
                raise AccessDenied(f"{url} returned {resp.status_code}; not bypassing")
            if resp.status_code == 429 or resp.status_code >= 500:
                retry_after = resp.headers.get("Retry-After")
                wait = float(retry_after) if retry_after and retry_after.isdigit() else 2 ** (attempt + 1)
                log.warning("GET %s -> %d; backing off %.0fs", url, resp.status_code, wait)
                time.sleep(wait)
                continue
            return resp
        raise RuntimeError(f"Giving up on {url}: {last_exc}")
