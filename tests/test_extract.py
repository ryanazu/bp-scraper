"""Tests for extract module: forms, emails, phones, LinkedIn, scoring."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from leadfinder.extract import (
    extract_all,
    extract_emails,
    extract_forms,
    extract_linkedin,
    extract_person_emails,
    extract_phones,
    linkedin_search_url,
)


def test_extract_forms():
    html = """
    <html><body>
    <form action="/partnerships/inquire" method="post">
        <input name="name" type="text"/>
        <input name="email" type="email"/>
        <input type="submit"/>
    </form>
    </body></html>
    """
    out = extract_forms(html, "https://example.com/partnerships")
    assert len(out) == 1
    assert out[0].contact_route_type == "form"
    assert "partnerships" in out[0].contact_value or "inquire" in out[0].contact_value
    assert out[0].confidence >= 70
    assert out[0].source_url == "https://example.com/partnerships"
    assert "name" in out[0].evidence_snippet or "email" in out[0].evidence_snippet


def test_extract_emails_allowed_only():
    html = """
    <p>Contact us at partnerships@company.com or press@company.com for more info.</p>
    <p>Do not email john.doe@company.com (personal).</p>
    """
    out = extract_emails(html, "https://example.com/contact")
    emails = [e.contact_value for e in out]
    assert "partnerships@company.com" in emails
    assert "press@company.com" in emails
    assert "john.doe@company.com" not in emails


def test_extract_emails_info_score():
    html = "<p>Email info@example.com</p>"
    out = extract_emails(html, "https://example.com/contact")
    assert len(out) == 1
    assert out[0].contact_value == "info@example.com"
    assert 50 <= out[0].confidence <= 70


def test_extract_phones():
    html = "<p>Call us at (555) 123-4567 or +1-800-555-0123.</p>"
    out = extract_phones(html, "https://example.com/contact")
    assert len(out) >= 1
    assert any("555" in p.contact_value for p in out)
    assert out[0].contact_route_type == "phone"
    assert out[0].source_url == "https://example.com/contact"


def test_extract_linkedin():
    html = """
    <a href="https://www.linkedin.com/company/acme-corp/">Our LinkedIn</a>
    <a href="https://linkedin.com/company/other">Other</a>
    """
    out = extract_linkedin(html, "https://example.com")
    urls = [x.contact_value for x in out]
    assert any("acme-corp" in u for u in urls)
    assert all("linkedin.com/company" in u for u in urls)


def test_extract_person_emails_same_domain_and_role():
    """Person in charge: mailto on partnerships page, same domain."""
    html = """
    <p>For partnerships, contact <a href="mailto:jane.smith@company.com">Jane Smith, Director of Partnerships</a>.</p>
    """
    out = extract_person_emails(html, "https://www.company.com/partnerships")
    assert len(out) == 1
    assert out[0].contact_value == "jane.smith@company.com"
    assert "Person" in out[0].contact_role_hint
    assert out[0].confidence == 75


def test_extract_person_emails_ignores_wrong_domain():
    """Do not harvest mailto when email domain does not match page domain."""
    html = """
    <p>Contact <a href="mailto:other@gmail.com">External contact</a> for partnerships.</p>
    """
    out = extract_person_emails(html, "https://company.com/partnerships")
    assert len(out) == 0


def test_extract_person_emails_ignores_generic_inbox():
    """Person extractor does not duplicate generic inboxes (info@, contact@)."""
    html = """
    <p>Email <a href="mailto:info@company.com">info</a> for general inquiries.</p>
    """
    out = extract_person_emails(html, "https://company.com/contact")
    assert len(out) == 0


def test_linkedin_search_url():
    url = linkedin_search_url("Acme Corp")
    assert "linkedin.com" in url
    assert "Acme" in url or "acme" in url or "Acme%20" in url


def test_extract_all_combined():
    html = """
    <form action="/contact" method="post"><input name="email"/></form>
    <p>partnerships@test.com and (555) 111-2222</p>
    """
    out = extract_all(html, "https://example.com/contact")
    types = {x.contact_route_type for x in out}
    assert "form" in types
    assert "email" in types
    assert "phone" in types
