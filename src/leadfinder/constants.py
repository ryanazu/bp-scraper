"""Constants: User-Agent, rate limits, seed paths."""

# Identify as bot; set LEADFINDER_CONTACT_EMAIL env or pass in CLI for your org
import os

DEFAULT_CONTACT_EMAIL = os.environ.get("LEADFINDER_CONTACT_EMAIL", "leadfinder@example.com")
USER_AGENT = f"SponsorshipLeadFinder/1.0 (+https://github.com/leadfinder; contact: {DEFAULT_CONTACT_EMAIL})"

# Seed path suffixes to try (without leading slash for joining with domain)
CONTACT_LIKE_PATHS = [
    "contact",
    "about",
    "about-us",
    "community",
    "csr",
    "corporate-social-responsibility",
    "sponsorship",
    "sponsors",
    "donate",
    "donations",
    "partnerships",
    "partners",
    "press",
    "media",
    "newsroom",
    "marketing",
    "careers",
    "recruiting",
    "vendor",
    "events",
    "get-in-touch",
    "support",
    "volunteer",
    "volunteering",
]

# Preferred role hints for scoring
ROLE_HINTS = [
    "partnerships",
    "sponsorship",
    "community",
    "csr",
    "donations",
    "marketing",
    "press",
    "recruiting",
    "vendor",
    "events",
]

# Public inbox patterns we allow (explicit only)
ALLOWED_EMAIL_PATTERNS = [
    "partnerships@",
    "community@",
    "sponsorship@",
    "sponsors@",
    "donations@",
    "donate@",
    "press@",
    "media@",
    "marketing@",
    "recruiting@",
    "careers@",
    "events@",
    "vendor@",
    "volunteer@",
    "volunteering@",
    "info@",
    "contact@",
]

# Keywords for "person in charge" mailto extraction: donations, volunteering, nonprofit communications, VPs only
PERSON_ROLE_KEYWORDS = [
    "donation", "donations", "donate",
    "volunteer", "volunteering", "volunteers",
    "nonprofit", "non-profit", "non profit",
    "communications", "communication",
    "vp", "vice president", "v.p.",
]

DEFAULT_RATE_LIMIT_PER_DOMAIN = 1.0  # requests per second
MAX_CRAWL_DEPTH = 2
