"""Content extraction from a user-submitted URL.

Security: fetching arbitrary URLs on a server is an SSRF risk (a user could
ask us to fetch http://169.254.169.254/ or an internal admin page). We
resolve the hostname and refuse private, loopback, link-local and reserved
addresses, limit redirects, response size and time, and only accept HTML.
"""
from __future__ import annotations

import ipaddress
import logging
import socket
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urljoin, urlparse

import requests

from app.core.config import get_settings
from ml.config import USER_AGENT
from ml.preprocessing.text_cleaning import clean_text

log = logging.getLogger(__name__)


class ExtractionError(ValueError):
    pass


@dataclass
class Extracted:
    text: str
    title: Optional[str]
    final_url: str


def _assert_public_host(url: str) -> None:
    p = urlparse(url)
    if p.scheme not in ("http", "https") or not p.hostname:
        raise ExtractionError("Only http(s) URLs with a hostname are supported.")
    try:
        infos = socket.getaddrinfo(p.hostname, p.port or (443 if p.scheme == "https" else 80))
    except socket.gaierror:
        raise ExtractionError("The domain could not be resolved.")
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise ExtractionError("URLs pointing to private or local network addresses are not allowed.")


def fetch_url(url: str) -> Extracted:
    s = get_settings()
    if not s.allow_url_fetch:
        raise ExtractionError("URL fetching is disabled on this server.")
    current = url
    for _ in range(4):  # follow at most 3 redirects, re-checking each hop
        _assert_public_host(current)
        try:
            resp = requests.get(current, timeout=s.url_fetch_timeout, stream=True, allow_redirects=False,
                                headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"})
        except requests.RequestException as exc:
            raise ExtractionError(f"Could not fetch the URL ({exc.__class__.__name__}).")
        if resp.is_redirect and resp.headers.get("Location"):
            current = urljoin(current, resp.headers["Location"])
            continue
        break
    else:
        raise ExtractionError("Too many redirects.")

    if resp.status_code in (401, 403):
        raise ExtractionError(f"The site refused access (HTTP {resp.status_code}). Paste the text instead.")
    if resp.status_code >= 400:
        raise ExtractionError(f"The site returned HTTP {resp.status_code}.")
    ctype = resp.headers.get("Content-Type", "")
    if "html" not in ctype:
        raise ExtractionError(f"Unsupported content type '{ctype.split(';')[0]}'. Only web pages are supported.")

    chunks, size = [], 0
    for chunk in resp.iter_content(65536):
        size += len(chunk)
        if size > s.url_max_bytes:
            raise ExtractionError("The page is too large to analyse.")
        chunks.append(chunk)
    html = b"".join(chunks).decode(resp.encoding or "utf-8", errors="replace")

    text, title = None, None
    try:
        import trafilatura

        text = trafilatura.extract(html, include_comments=False, include_tables=False, favor_precision=True)
        meta = trafilatura.extract_metadata(html)
        title = meta.title if meta else None
    except Exception as exc:  # trafilatura is optional at runtime
        log.info("trafilatura failed (%s); falling back to BeautifulSoup", exc)
    if not text:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "lxml")
        title = title or (soup.title.string if soup.title else None)
        text = " ".join(p.get_text(" ") for p in soup.find_all("p"))
    text = clean_text(text or "")
    if len(text) < 20:
        raise ExtractionError("No readable article text was found on that page.")
    return Extracted(text=text, title=clean_text(title) if title else None, final_url=current)
