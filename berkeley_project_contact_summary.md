# Berkeley Project – Sponsor Lead Summary

## Company list (would collaborate)

The file **`berkeley_project_companies.csv`** contains 20 companies chosen for fit with Berkeley Project (UC Berkeley’s largest community service org):

- **Bay Area / local:** Clif Bar (Berkeley), Patagonia, REI, Safeway, Whole Foods, Trader Joe’s, PG&E, Kaiser Permanente, Genentech  
- **Tech / CSR:** Google, Salesforce, Adobe, Cisco, Intel  
- **Retail / community giving:** Target, North Face, New Belgium, Ben & Jerry’s  
- **Finance / community:** Wells Fargo, Bank of America  

Each row has `company_name`, `domain`, and `notes`. Domains are required because the leadfinder uses a stub domain resolver.

## How to scrape contact routes (forms, emails, LinkedIn)

1. **Full run (all 20 companies, ~10–15 min):**
   ```bash
   cd bp-scraper
   pip install -e .
   leadfinder run berkeley_project_companies.csv --out berkeley_project_leads.db --max-pages 20 --rate 1.0
   ```

2. **Export to CSV:**
   ```bash
   leadfinder export berkeley_project_leads.db --format csv --out berkeley_project_leads.csv
   ```

3. **Optional:** Use the short list for a quicker test:
   ```bash
   leadfinder run berkeley_project_companies_short.csv --out berkeley_project_leads_sample.db --max-pages 12
   leadfinder export berkeley_project_leads_sample.db --out berkeley_project_leads_sample.csv
   ```

## About “emails”

The tool is **ethical and minimal**: it only stores **explicitly published** addresses that match allowed roles (e.g. `partnerships@`, `community@`, `sponsorship@`, `contact@`). It does **not** guess or brute‑force emails.

- Many companies only offer **contact forms** (no public email). The scraper records the **form URL** and type so you can reach out there.
- When a site does publish a partnership/community/sponsorship email, it will appear in the CSV with `contact_route_type` = `email`.
- You also get **phones**, **LinkedIn** company links, and **address** text when found.

## Sample run results (4 companies)

A short run on Patagonia, Clif Bar, REI, and Ben & Jerry’s produced:

- **Clif Bar:** Contact form (https://www.clifbar.com/contact-us), phone **1-866-805-2879**, note: “90 days advanced notice” for new sponsorships.
- **Patagonia:** Contact form and partnership/sponsorship-style pages.
- **REI / Ben & Jerry’s:** Crawl was blocked (403) on some paths; LinkedIn search URLs were still added as fallback.

Full output: **`berkeley_project_leads_sample.csv`** (741 rows including forms, phones, LinkedIn). For a cleaner “best route per company,” filter by `contact_route_type` in (`email`, `form`) and by `contact_role_hint` or `source_url` containing “contact”, “partnership”, or “sponsorship”.
