"""
Crawler: seed URLs, robots check, rate limit per domain, max depth 2, same-domain only.
Uses httpx and selectolax. Exponential backoff on errors.
"""

from __future__ import annotations

import logging
import os
import time
from collections import deque
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

import httpx
from selectolax.parser import HTMLParser

from leadfinder.constants import (
    CONTACT_LIKE_PATHS,
    DEFAULT_RATE_LIMIT_PER_DOMAIN,
    MAX_CRAWL_DEPTH,
    USER_AGENT,
)
from leadfinder.robots import RobotsChecker

logger = logging.getLogger(__name__)


@dataclass
class CrawlResult:
    url: str
    status_code: int
    html: str
    final_url: str
    depth: int


@dataclass
class RateLimiter:
    """Per-domain rate limit (requests per second) with exponential backoff."""

    rate: float = DEFAULT_RATE_LIMIT_PER_DOMAIN
    _last: dict[str, float] = field(default_factory=dict)
    _backoff: dict[str, float] = field(default_factory=dict)

    def wait(self, domain: str) -> None:
        now = time.monotonic()
        backoff = self._backoff.get(domain, 1.0)
        last = self._last.get(domain, 0.0)
        interval = 1.0 / self.rate if self.rate > 0 else 0
        wait_until = last + interval * backoff
        if now < wait_until:
            time.sleep(wait_until - now)
        self._last[domain] = time.monotonic()

    def record_success(self, domain: str) -> None:
        self._backoff[domain] = max(1.0, self._backoff.get(domain, 1.0) * 0.5)

    def record_failure(self, domain: str) -> None:
        self._backoff[domain] = min(60.0, self._backoff.get(domain, 1.0) * 2.0)


def _domain(url: str) -> str:
    return urlparse(url).netloc.lower() or ""


def _same_domain(base: str, url: str) -> bool:
    return _domain(base) == _domain(url)


def _normalize_url(base: str, href: str) -> str | None:
    href = (href or "").strip().split("#")[0].strip()
    if not href or href.startswith("mailto:") or href.startswith("tel:") or href.startswith("javascript:"):
        return None
    try:
        full = urljoin(base, href)
        p = urlparse(full)
        if p.scheme not in ("http", "https"):
            return None
        return full
    except Exception:
        return None


def _contact_like_path(url: str) -> bool:
    path = urlparse(url).path.strip("/").lower()
    if not path:
        return False
    first = path.split("/")[0]
    return first in {p.lower() for p in CONTACT_LIKE_PATHS}


def _seed_urls(domain: str) -> list[str]:
    base = f"https://{domain}" if not domain.startswith("http") else domain
    base = base.rstrip("/")
    urls = [f"{base}/"]
    for path in CONTACT_LIKE_PATHS:
        urls.append(f"{base}/{path}")
    return urls


def _extract_links(html: str, base_url: str) -> list[str]:
    """Extract same-domain links from document; prioritize contact-like paths."""
    parser = HTMLParser(html)
    seen: set[str] = set()
    out: list[str] = []
    for node in parser.tags("a"):
        href = node.attributes.get("href")
        u = _normalize_url(base_url, href)
        if u and _same_domain(base_url, u) and u not in seen:
            seen.add(u)
            out.append(u)
    return out


def _prioritize_contact_urls(urls: list[str]) -> list[str]:
    contact_like = [u for u in urls if _contact_like_path(u)]
    rest = [u for u in urls if u not in contact_like]
    return contact_like + rest


def crawl(
    domain: str,
    max_pages: int = 30,
    rate: float = DEFAULT_RATE_LIMIT_PER_DOMAIN,
    max_depth: int = MAX_CRAWL_DEPTH,
    user_agent: str = USER_AGENT,
) -> list[CrawlResult]:
    """
    Crawl up to max_pages on the given domain. Respects robots.txt and rate limit.
    Returns list of CrawlResult (url, status_code, html, final_url, depth).
    """
    if not domain:
        return []
    domain = domain.strip().lower().replace("https://", "").replace("http://", "").split("/")[0]
    base = f"https://{domain}"
    results: list[CrawlResult] = []
    visited: set[str] = set()
    # Queue: (url, depth)
    queue: deque[tuple[str, int]] = deque()
    for u in _seed_urls(base):
        queue.append((u, 0))
    limiter = RateLimiter(rate=rate)
    robots = RobotsChecker(user_agent=user_agent)
    headers = {"User-Agent": user_agent}

    with httpx.Client(
        follow_redirects=True,
        timeout=15.0,
        headers=headers,
        verify=os.environ.get("LEADFINDER_SSL_VERIFY", "true").lower() not in ("0", "false", "no"),
    ) as client:
        while queue and len(results) < max_pages:
            url, depth = queue.popleft()
            if url in visited:
                continue
            visited.add(url)
            dom = _domain(url)
            limiter.wait(dom)
            if not robots.can_fetch(url, client):
                logger.info("Robots disallow: %s", url)
                continue
            try:
                resp = client.get(url)
                limiter.record_success(dom)
            except Exception as e:
                logger.warning("Fetch failed %s: %s", url, e)
                limiter.record_failure(dom)
                continue
            if resp.status_code != 200:
                continue
            html = resp.text or ""
            final = str(resp.url)
            results.append(
                CrawlResult(url=url, status_code=resp.status_code, html=html, final_url=final, depth=depth)
            )
            if depth < max_depth:
                links = _extract_links(html, final)
                links = _prioritize_contact_urls(links)
                for link in links:
                    if link not in visited and (link, depth + 1) not in queue:
                        queue.append((link, depth + 1))

    return results
