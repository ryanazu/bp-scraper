"""
robots.txt checks using urllib.robotparser. Respect disallowed paths before fetching.
"""

from __future__ import annotations

import logging
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

from leadfinder.constants import USER_AGENT

logger = logging.getLogger(__name__)


def _robots_url(origin: str) -> str:
    parsed = urlparse(origin)
    base = f"{parsed.scheme or 'https'}://{parsed.netloc}"
    return urljoin(base, "/robots.txt")


def _origin(url: str) -> str:
    p = urlparse(url)
    return f"{p.scheme or 'https'}://{p.netloc}"


class RobotsChecker:
    """Cache per-origin RobotFileParser and check allow/disallow."""

    def __init__(self, user_agent: str = USER_AGENT) -> None:
        self.user_agent = user_agent
        self._parsers: dict[str, RobotFileParser] = {}
        self._fetched: set[str] = set()

    def fetch_robots(self, url: str, session: "httpx.Client") -> bool:
        """Fetch and parse robots.txt for the URL's origin. Returns True if fetched (or already cached)."""
        origin = _origin(url)
        if origin in self._parsers:
            return True
        rp = RobotFileParser()
        robots_url = _robots_url(origin)
        try:
            resp = session.get(robots_url, timeout=10.0)
            if resp.status_code == 200:
                rp.parse(resp.text.splitlines())
            else:
                rp.parse([])  # treat as allow all
        except Exception as e:
            logger.debug("robots fetch failed for %s: %s", robots_url, e)
            rp.parse([])
        self._parsers[origin] = rp
        self._fetched.add(origin)
        return True

    def can_fetch(self, url: str, session: "httpx.Client") -> bool:
        """Ensure robots is loaded for this origin, then return whether we can fetch URL."""
        origin = _origin(url)
        if origin not in self._parsers:
            self.fetch_robots(url, session)
        rp = self._parsers.get(origin)
        if not rp:
            return True
        return bool(rp.can_fetch(self.user_agent, url))
