"""
Extraction: contact forms, public emails (explicit only), phones, address, LinkedIn.
Scoring heuristics 0-100. Every field has source_url and evidence_snippet.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import quote_plus, urlparse

from selectolax.parser import HTMLParser

from leadfinder.constants import ALLOWED_EMAIL_PATTERNS, PERSON_ROLE_KEYWORDS, ROLE_HINTS

# Public inbox / explicit email pattern (no guessing)
EMAIL_RE = re.compile(
    r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
    re.IGNORECASE,
)

# US/international phone
PHONE_RE = re.compile(
    r"(?:\+?1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}"
    r"|(?:\+[0-9]{1,3}[-.\s]?)?[0-9]{2,4}[-.\s]?[0-9]{2,4}[-.\s]?[0-9]{2,4}",
)

# LinkedIn company URL
LINKEDIN_COMPANY_RE = re.compile(
    r"https?://(?:www\.)?linkedin\.com/company/[\w\-]+/?",
    re.IGNORECASE,
)


def _snippet(text: str, max_len: int = 200) -> str:
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_len] + ("..." if len(text) > max_len else "")


@dataclass
class ExtractedLead:
    contact_route_type: str  # form, email, phone, linkedin, address
    contact_value: str
    contact_role_hint: str
    confidence: int
    source_url: str
    evidence_snippet: str


def _path_role_hint(url: str) -> str:
    path = urlparse(url).path.lower()
    for hint in ROLE_HINTS:
        if hint in path:
            return hint.replace("-", " ").title()
    if "contact" in path or "about" in path:
        return "Contact"
    if "form" in path or "inquiry" in path:
        return "Inquiry"
    return "General"


def _score_form(url: str, path: str, role_hint: str) -> int:
    path_lower = path.lower()
    if any(x in path_lower for x in ("partnership", "sponsor", "community", "csr", "donat")):
        return 92
    if "contact" in path_lower or "press" in path_lower or "marketing" in path_lower:
        return 78
    return 70


def _score_email(local_part: str, role_hint: str) -> int:
    local_lower = local_part.lower()
    if "partnership" in local_lower or "sponsorship" in local_lower or "sponsors" in local_lower:
        return 88
    if "donations" in local_lower or "donate" in local_lower:
        return 87
    if "volunteer" in local_lower or "community" in local_lower or "csr" in local_lower:
        return 86
    if "press" in local_lower or "media" in local_lower:
        return 82
    if "marketing" in local_lower or "recruiting" in local_lower or "careers" in local_lower:
        return 80
    if "info" in local_lower or "contact" in local_lower:
        return 60
    return 50


def _is_allowed_public_email(email: str) -> bool:
    local = email.split("@")[0].lower() if "@" in email else ""
    return any(local.startswith(p.replace("@", "")) for p in ALLOWED_EMAIL_PATTERNS)


def _is_generic_inbox(email: str) -> bool:
    """True if this is a generic inbox (info@, contact@, etc.), not a person."""
    return _is_allowed_public_email(email)


def _domain_from_url(url: str) -> str:
    """Return hostname (domain) from URL, normalized to lowercase without www."""
    netloc = urlparse(url).netloc.lower()
    return netloc[4:] if netloc.startswith("www.") else netloc


def extract_person_emails(html: str, page_url: str) -> list[ExtractedLead]:
    """Find mailto: links where context suggests a person in charge of donations, volunteering,
    nonprofit communications, or VPs. Only stores explicitly shown emails at the same domain."""
    out: list[ExtractedLead] = []
    parser = HTMLParser(html)
    page_domain = _domain_from_url(page_url)
    role_hint = _path_role_hint(page_url)
    mailto_re = re.compile(r"^mailto:([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})", re.IGNORECASE)
    seen: set[str] = set()

    for node in parser.tags("a"):
        href = (node.attributes.get("href") or "").strip()
        if not href.lower().startswith("mailto:"):
            continue
        m = mailto_re.match(href.split("?")[0])
        if not m:
            continue
        email = m.group(1)
        if email in seen:
            continue
        email_domain = email.split("@")[-1].lower() if "@" in email else ""
        if email_domain != page_domain and not page_domain.endswith("." + email_domain) and not email_domain.endswith("." + page_domain):
            continue
        if _is_generic_inbox(email):
            continue
        link_text = (node.text(deep=False) or "").strip() or ""
        parent = node.parent
        context_parts = [link_text]
        if parent:
            context_parts.append((parent.text(deep=False) or "").strip())
            if parent.parent:
                context_parts.append((parent.parent.text(deep=False) or "").strip())
        context = " ".join(context_parts).lower()
        path_lower = urlparse(page_url).path.lower()
        page_has_role = any(kw in path_lower for kw in PERSON_ROLE_KEYWORDS)
        if not page_has_role and not any(kw in context for kw in PERSON_ROLE_KEYWORDS):
            continue
        seen.add(email)
        snippet = _snippet(link_text or context[:120])
        out.append(
            ExtractedLead(
                contact_route_type="email",
                contact_value=email,
                contact_role_hint=f"Person ({role_hint})",
                confidence=75,
                source_url=page_url,
                evidence_snippet=snippet or f"Mailto: {email}",
            )
        )
    return out


def extract_forms(html: str, page_url: str) -> list[ExtractedLead]:
    """Find forms with action or typical form endpoints; return form URL + fields hint."""
    out: list[ExtractedLead] = []
    parser = HTMLParser(html)
    path = urlparse(page_url).path
    role_hint = _path_role_hint(page_url)
    for form in parser.tags("form"):
        action = form.attributes.get("action") or ""
        if not action.strip():
            form_url = page_url
        else:
            from urllib.parse import urljoin
            form_url = urljoin(page_url, action)
        method = (form.attributes.get("method") or "get").upper()
        fields: list[str] = []
        for inp in form.css("input"):
            name = inp.attributes.get("name")
            if name and inp.attributes.get("type", "text").lower() not in ("submit", "button", "image"):
                fields.append(name)
        for sel in form.css("select"):
            name = sel.attributes.get("name")
            if name:
                fields.append(name)
        snippet = f"Form ({method}), fields: {', '.join(fields[:8])}" if fields else "Form (submit)"
        score = _score_form(form_url, path, role_hint)
        out.append(
            ExtractedLead(
                contact_route_type="form",
                contact_value=form_url,
                contact_role_hint=role_hint,
                confidence=min(100, score),
                source_url=page_url,
                evidence_snippet=_snippet(snippet),
            )
        )
    return out


def extract_emails(html: str, page_url: str) -> list[ExtractedLead]:
    """Only emails matching allowed public inbox patterns; with source and snippet."""
    out: list[ExtractedLead] = []
    parser = HTMLParser(html)
    path = urlparse(page_url).path
    role_hint = _path_role_hint(page_url)
    text = parser.text(separator=" ") or ""
    for m in EMAIL_RE.finditer(text):
        email = m.group(0)
        if not _is_allowed_public_email(email):
            continue
        local = email.split("@")[0].lower()
        score = _score_email(local, role_hint)
        snippet = _snippet(text[max(0, m.start() - 40) : m.end() + 40])
        out.append(
            ExtractedLead(
                contact_route_type="email",
                contact_value=email,
                contact_role_hint=role_hint,
                confidence=min(100, score),
                source_url=page_url,
                evidence_snippet=snippet,
            )
        )
    return out


def extract_phones(html: str, page_url: str) -> list[ExtractedLead]:
    parser = HTMLParser(html)
    text = parser.text(separator=" ") or ""
    role_hint = _path_role_hint(page_url)
    seen: set[str] = set()
    out: list[ExtractedLead] = []
    for m in PHONE_RE.finditer(text):
        phone = re.sub(r"\s+", " ", m.group(0).strip())
        if len(phone) < 10 or phone in seen:
            continue
        seen.add(phone)
        snippet = _snippet(text[max(0, m.start() - 30) : m.end() + 30])
        out.append(
            ExtractedLead(
                contact_route_type="phone",
                contact_value=phone,
                contact_role_hint=role_hint,
                confidence=65,
                source_url=page_url,
                evidence_snippet=snippet,
            )
        )
    return out


def extract_linkedin(html: str, page_url: str) -> list[ExtractedLead]:
    parser = HTMLParser(html)
    text = parser.text(separator=" ") or ""
    hrefs: list[str] = []
    for node in parser.tags("a"):
        h = node.attributes.get("href") or ""
        match = LINKEDIN_COMPANY_RE.search(h)
        if match:
            hrefs.append(match.group(0))
    out: list[ExtractedLead] = []
    seen: set[str] = set()
    for url in hrefs:
        url = url.rstrip("/")
        if url in seen:
            continue
        seen.add(url)
        out.append(
            ExtractedLead(
                contact_route_type="linkedin",
                contact_value=url,
                contact_role_hint="Company",
                confidence=50,
                source_url=page_url,
                evidence_snippet=f"LinkedIn company link: {url}",
            )
        )
    return out


def extract_address(html: str, page_url: str) -> list[ExtractedLead]:
    """Simple address detection: lines that look like street + optional city/state/zip."""
    parser = HTMLParser(html)
    text = parser.text(separator=" ") or ""
    # Heuristic: number + street type (St, Ave, Blvd, etc.) and optional city/state/zip
    addr_re = re.compile(
        r"\d+[\w\s]+(?:Street|St|Avenue|Ave|Boulevard|Blvd|Road|Rd|Drive|Dr|Lane|Ln|Way|Court|Ct)[\w\s,]+(?:[A-Z]{2}\s+\d{5}(?:-\d{4})?)?",
        re.IGNORECASE,
    )
    seen: set[str] = set()
    out: list[ExtractedLead] = []
    for m in addr_re.finditer(text):
        addr = _snippet(m.group(0), 150).strip()
        if addr in seen or len(addr) < 15:
            continue
        seen.add(addr)
        out.append(
            ExtractedLead(
                contact_route_type="address",
                contact_value=addr,
                contact_role_hint="Mailing",
                confidence=45,
                source_url=page_url,
                evidence_snippet=addr,
            )
        )
    return out


def extract_all(html: str, page_url: str) -> list[ExtractedLead]:
    """Run all extractors and return combined list (may have duplicates by value; caller can dedupe)."""
    out: list[ExtractedLead] = []
    out.extend(extract_forms(html, page_url))
    out.extend(extract_emails(html, page_url))
    out.extend(extract_person_emails(html, page_url))
    out.extend(extract_phones(html, page_url))
    out.extend(extract_linkedin(html, page_url))
    out.extend(extract_address(html, page_url))
    return out


def linkedin_search_url(company_name: str) -> str:
    """Generate LinkedIn company search URL when no company link found on site."""
    q = quote_plus(company_name)
    return f"https://www.linkedin.com/search/results/companies/?keywords={q}"
