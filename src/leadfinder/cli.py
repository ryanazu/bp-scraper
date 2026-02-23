"""
CLI: leadfinder run input.csv --out leads.db | leadfinder export leads.db --format csv --out leads.csv
"""

from __future__ import annotations

import csv
import logging
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table

from leadfinder.constants import USER_AGENT
from leadfinder.crawl import crawl
from leadfinder.domain_resolver import get_domain_for_company, normalize_domain
from leadfinder.extract import extract_all, linkedin_search_url
from leadfinder.store import LeadStore

app = typer.Typer(name="leadfinder", help="Sponsorship Lead Finder — ethical contact discovery")
console = Console()


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(console=console, show_path=False)],
    )


@app.command()
def run(
    input_file: Path = typer.Argument(..., help="CSV with company_name, domain (optional), notes (optional)"),
    out: Path = typer.Option(Path("leads.db"), "--out", "-o", help="Output SQLite DB path"),
    max_pages: int = typer.Option(30, "--max-pages", help="Max pages to crawl per company"),
    rate: float = typer.Option(1.0, "--rate", help="Requests per second per domain"),
    user_agent: str | None = typer.Option(None, "--user-agent", help="Override User-Agent (include contact email)"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Crawl companies from CSV and write leads to SQLite."""
    _setup_logging(verbose)
    log = logging.getLogger(__name__)
    ua = user_agent or USER_AGENT

    if not input_file.exists():
        console.print(f"[red]Input file not found: {input_file}[/red]")
        raise typer.Exit(1)

    store = LeadStore(out)
    store.init_schema()

    rows: list[dict[str, str]] = []
    with open(input_file, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            name = (r.get("company_name") or r.get("company") or "").strip()
            if name:
                rows.append({
                    "company_name": name,
                    "domain": (r.get("domain") or "").strip(),
                    "notes": (r.get("notes") or "").strip(),
                })

    if not rows:
        console.print("[yellow]No rows with company_name found in CSV.[/yellow]")
        raise typer.Exit(0)

    seen_keys: set[tuple[str, str, str]] = set()

    for i, row in enumerate(rows):
        company_name = row["company_name"]
        domain_hint = row.get("domain") or ""
        domain = get_domain_for_company(company_name, domain_hint or None)
        if not domain:
            log.warning("No domain for %s; skipping.", company_name)
            continue
        domain = normalize_domain(domain)
        log.info("Crawling %s (%s)", company_name, domain)
        results = crawl(domain=domain, max_pages=max_pages, rate=rate, user_agent=ua)
        has_linkedin = False
        for cr in results:
            for lead in extract_all(cr.html, cr.final_url):
                key = (company_name, lead.contact_route_type, lead.contact_value)
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                if lead.contact_route_type == "linkedin":
                    has_linkedin = True
                store.insert_lead(
                    company_name=company_name,
                    domain=domain,
                    contact_route_type=lead.contact_route_type,
                    contact_value=lead.contact_value,
                    contact_role_hint=lead.contact_role_hint,
                    confidence=lead.confidence,
                    source_url=lead.source_url,
                    evidence_snippet=lead.evidence_snippet,
                )
        if not has_linkedin:
            search_url = linkedin_search_url(company_name)
            key = (company_name, "linkedin", search_url)
            if key not in seen_keys:
                seen_keys.add(key)
                store.insert_lead(
                    company_name=company_name,
                    domain=domain,
                    contact_route_type="linkedin",
                    contact_value=search_url,
                    contact_role_hint="Company (search)",
                    confidence=50,
                    source_url="",
                    evidence_snippet=f"LinkedIn search: {company_name}",
                )

    console.print(f"[green]Done. Leads saved to {out}[/green]")


@app.command()
def export(
    db: Path = typer.Argument(..., help="SQLite DB path (e.g. leads.db)"),
    format: str = typer.Option("csv", "--format", "-f", help="Export format (csv)"),
    out: Path = typer.Option(Path("leads.csv"), "--out", "-o", help="Output file path"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Export leads from SQLite to CSV and print ranked list."""
    _setup_logging(verbose)
    if not db.exists():
        console.print(f"[red]DB not found: {db}[/red]")
        raise typer.Exit(1)

    store = LeadStore(db)
    store.init_schema()
    leads = store.get_all_leads()

    if format == "csv":
        n = store.export_csv(out)
        console.print(f"[green]Exported {n} rows to {out}[/green]")
    else:
        console.print("[yellow]Only csv format is supported.[/yellow]")
        raise typer.Exit(1)

    if leads:
        table = Table(title="Leads (ranked by confidence)")
        table.add_column("Company", style="cyan")
        table.add_column("Type", style="magenta")
        table.add_column("Value", style="green", max_width=50)
        table.add_column("Role", style="yellow")
        table.add_column("Score", justify="right")
        for r in leads[:50]:
            table.add_row(
                r["company_name"],
                r["contact_route_type"],
                r["contact_value"][:50] + ("..." if len(r["contact_value"]) > 50 else ""),
                r["contact_role_hint"],
                str(r["confidence"]),
            )
        console.print(table)
        if len(leads) > 50:
            console.print(f"... and {len(leads) - 50} more (see {out})")


if __name__ == "__main__":
    app()
