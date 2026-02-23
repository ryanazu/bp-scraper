# Sponsorship Lead Finder

Production-quality tool for **student orgs** to find sponsorship and partnership contact routes **ethically**: no scraping of personal emails, full respect for robots.txt and rate limits, and attribution for every lead.

## Goal

Given a list of company names (and optional domains), discover the **best way to contact them** about sponsorship/donations by preferring:

1. Official **Contact**, **Partnerships**, **Sponsorship**, **Community**, **CSR**, **Donations**, **Marketing**, **Press**, **Careers/Recruiting**, **Vendor/Events** pages  
2. **Contact forms** (URL + form fields)  
3. **Press/PR or partnership inboxes** only when explicitly published on the site  
4. **LinkedIn** company page (and search URL when not found on site); no collection of personal emails  

## Strict ethical rules

- **No crawling** of pages disallowed by `robots.txt`.  
- **Rate limits**: default 1 request/second/domain with exponential backoff on errors.  
- **Identify as a bot**: User-Agent includes a contact email (set `LEADFINDER_CONTACT_EMAIL` or `--user-agent`).  
- **No brute-force or guessing** of email patterns; only **explicitly shown** addresses are stored.  
- **Source attribution**: every lead has `source_url` and `evidence_snippet`.  

## Tech stack

- **CLI**: Typer  
- **HTTP**: httpx  
- **HTML parsing**: selectolax  
- **robots.txt**: `urllib.robotparser`  
- **Storage**: SQLite (SQLModel when available, else sqlite3)  

## Install

```bash
cd bp-scraper
pip install -e .
# or with dev deps: pip install -e ".[dev]"
```

## Usage

### Run: crawl companies and build leads DB

Input CSV columns: `company_name`, `domain` (optional), `notes` (optional).

```bash
# Default: 30 pages/company, 1 req/s/domain, output leads.db
leadfinder run input.csv --out leads.db

# Tune crawl size and rate
leadfinder run input.csv --out leads.db --max-pages 30 --rate 1.0

# Override User-Agent (include your org contact email)
leadfinder run input.csv --out leads.db --user-agent "SponsorshipLeadFinder/1.0 (contact: your-org@university.edu)"
# or set env: export LEADFINDER_CONTACT_EMAIL=your-org@university.edu
```

### Export: SQLite → CSV and ranked list

```bash
leadfinder export leads.db --format csv --out leads.csv
```

Prints a ranked table (by confidence) and writes the full CSV.

## Input CSV example

```csv
company_name,domain,notes
Acme Corp,acme.com,Tech sponsor
Berkeley Bank,,Finance
```

If `domain` is missing, the **domain resolver** is used (stub by default; you can plug in SerpAPI/Bing later).

## Output schema (SQLite + CSV)

| Column               | Description |
|----------------------|-------------|
| `company_name`       | From input  |
| `domain`             | Resolved/normalized |
| `contact_route_type` | `form`, `email`, `phone`, `linkedin`, `address` |
| `contact_value`      | Form URL, email, phone, LinkedIn URL, or address text |
| `contact_role_hint`  | e.g. Partnerships, CSR, Marketing |
| `confidence`         | 0–100 heuristic score |
| `source_url`         | Page where this was found |
| `evidence_snippet`   | Short excerpt or description |
| `discovered_at`      | ISO timestamp |

## Scoring (heuristic)

- Contact form on **partnerships/sponsorship** page: **90+**  
- **partnerships@** / **community@** etc.: **85+**  
- Generic contact form: **70**  
- Generic **info@** email: **60**  
- LinkedIn / company page only: **50**  

## Project layout

```
src/leadfinder/
  __init__.py
  cli.py          # Typer: run, export
  constants.py    # UA, paths, rate, allowed email patterns
  crawl.py        # httpx, robots, queue, depth 2
  domain_resolver.py  # Pluggable domain lookup (stub)
  extract.py      # Forms, emails, phones, LinkedIn, scoring
  robots.py       # urllib.robotparser wrapper
  store.py        # SQLite leads table
tests/
  test_extract.py
  test_robots.py
```

## Tests

```bash
pytest tests/ -v
```

## Ethical notes

- **Purpose**: Help student orgs find **official** sponsorship/partnership channels, not to harvest personal data.  
- **Transparency**: Identify as a bot and provide a contact so site owners can request exclusion.  
- **Minimal data**: Store only what is clearly intended for public/partnership contact (forms, published inboxes, LinkedIn).  
- **Compliance**: Respect robots.txt and rate limits; use exponential backoff to avoid overloading servers.  
- **Attribution**: Every lead is tied to a `source_url` and `evidence_snippet` for verification and follow-up.  

## Optional: domain resolution

When `domain` is missing in the CSV, the pipeline uses a **pluggable resolver** (`domain_resolver.py`). The default is a **stub** that returns the hint if provided, otherwise empty. You can implement a real provider (e.g. SerpAPI or Bing Search API) by implementing the `DomainSearchProvider` protocol and passing it into the resolution step.
