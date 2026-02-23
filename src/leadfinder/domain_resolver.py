"""
Pluggable domain resolution: given a company name (and optional domain),
return the official domain. Stub implementation for now; can plug in SerpAPI/Bing later.
"""

from __future__ import annotations

import re
from typing import Protocol


def normalize_domain(domain: str) -> str:
    """Lowercase, strip whitespace, remove scheme and path."""
    domain = (domain or "").strip().lower()
    if not domain:
        return ""
    domain = re.sub(r"^https?://", "", domain)
    domain = re.sub(r"/.*$", "", domain)
    domain = domain.split(":")[0]  # remove port for display
    return domain


class DomainSearchProvider(Protocol):
    """Interface for resolving company name -> official domain."""

    def resolve(self, company_name: str, hint_domain: str | None = None) -> str:
        """Return the best-guess official domain for the company. Empty if unknown."""
        ...


class StubDomainProvider:
    """
    Stub: uses hint domain if provided; otherwise returns empty.
    Replace with SerpAPI/Bing provider by implementing DomainSearchProvider.
    """

    def resolve(self, company_name: str, hint_domain: str | None = None) -> str:
        if hint_domain:
            return normalize_domain(hint_domain)
        return ""


def get_domain_for_company(
    company_name: str,
    domain_hint: str | None,
    provider: DomainSearchProvider | None = None,
) -> str:
    """Resolve domain using the given provider (default: stub)."""
    if provider is None:
        provider = StubDomainProvider()
    return provider.resolve(company_name, domain_hint)
