"""
SQLite storage for leads. Schema: company_name, domain, contact_route_type,
contact_value, contact_role_hint, confidence, source_url, evidence_snippet, discovered_at.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

# Optional SQLModel; fallback to plain sqlite3 for minimal deps
try:
    from sqlmodel import SQLModel, Field, Session, create_engine
    HAS_SQLMODEL = True
except ImportError:
    HAS_SQLMODEL = False

if HAS_SQLMODEL:

    class Lead(SQLModel, table=True):
        __tablename__ = "leads"
        id: int | None = Field(default=None, primary_key=True)
        company_name: str = Field(index=True)
        domain: str = Field(default="", index=True)
        contact_route_type: str = Field(index=True)  # form, email, phone, linkedin, address
        contact_value: str = Field(default="")
        contact_role_hint: str = Field(default="")
        confidence: int = Field(default=0)
        source_url: str = Field(default="")
        evidence_snippet: str = Field(default="")
        discovered_at: str = Field(default="")

    def _utc_now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

else:
    Lead = None  # type: ignore[misc, assignment]
    _utc_now_iso = lambda: datetime.now(timezone.utc).isoformat()


def _ensure_schema_sqlite3(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS leads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_name TEXT NOT NULL,
            domain TEXT DEFAULT '',
            contact_route_type TEXT NOT NULL,
            contact_value TEXT DEFAULT '',
            contact_role_hint TEXT DEFAULT '',
            confidence INTEGER DEFAULT 0,
            source_url TEXT DEFAULT '',
            evidence_snippet TEXT DEFAULT '',
            discovered_at TEXT DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS ix_leads_company_name ON leads(company_name);
        CREATE INDEX IF NOT EXISTS ix_leads_domain ON leads(domain);
        CREATE INDEX IF NOT EXISTS ix_leads_contact_route_type ON leads(contact_route_type);
        CREATE INDEX IF NOT EXISTS ix_leads_confidence ON leads(confidence);
    """)


class LeadStore:
    """Unified store: uses SQLModel if available, else plain sqlite3."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self._engine = None
        if HAS_SQLMODEL and Lead is not None:
            self._engine = create_engine(f"sqlite:///{self.db_path}", echo=False)

    def init_schema(self) -> None:
        if self._engine is not None and HAS_SQLMODEL:
            SQLModel.metadata.create_all(self._engine)
        else:
            with self._connection() as conn:
                _ensure_schema_sqlite3(conn)

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def insert_lead(
        self,
        company_name: str,
        domain: str,
        contact_route_type: str,
        contact_value: str,
        contact_role_hint: str,
        confidence: int,
        source_url: str,
        evidence_snippet: str,
        discovered_at: str | None = None,
    ) -> None:
        discovered_at = discovered_at or _utc_now_iso()
        if self._engine is not None and HAS_SQLMODEL and Lead is not None:
            with Session(self._engine) as session:
                session.add(
                    Lead(
                        company_name=company_name,
                        domain=domain,
                        contact_route_type=contact_route_type,
                        contact_value=contact_value,
                        contact_role_hint=contact_role_hint,
                        confidence=confidence,
                        source_url=source_url,
                        evidence_snippet=evidence_snippet,
                        discovered_at=discovered_at,
                    )
                )
                session.commit()
        else:
            with self._connection() as conn:
                conn.execute(
                    """
                    INSERT INTO leads (
                        company_name, domain, contact_route_type, contact_value,
                        contact_role_hint, confidence, source_url, evidence_snippet, discovered_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        company_name,
                        domain,
                        contact_route_type,
                        contact_value,
                        contact_role_hint,
                        confidence,
                        source_url,
                        evidence_snippet,
                        discovered_at,
                    ),
                )

    def get_all_leads(self) -> list[dict[str, Any]]:
        if self._engine is not None and HAS_SQLMODEL and Lead is not None:
            with Session(self._engine) as session:
                rows = session.exec(
                    __import__("sqlmodel").select(Lead).order_by(Lead.confidence.desc(), Lead.company_name)
                ).all()
            return [
                {
                    "company_name": r.company_name,
                    "domain": r.domain,
                    "contact_route_type": r.contact_route_type,
                    "contact_value": r.contact_value,
                    "contact_role_hint": r.contact_role_hint,
                    "confidence": r.confidence,
                    "source_url": r.source_url,
                    "evidence_snippet": r.evidence_snippet,
                    "discovered_at": r.discovered_at,
                }
                for r in rows
            ]
        with self._connection() as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.execute(
                "SELECT company_name, domain, contact_route_type, contact_value, "
                "contact_role_hint, confidence, source_url, evidence_snippet, discovered_at "
                "FROM leads ORDER BY confidence DESC, company_name"
            )
            return [dict(row) for row in cur.fetchall()]

    def export_csv(self, out_path: str | Path) -> int:
        import csv
        rows = self.get_all_leads()
        if not rows:
            return 0
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(
                f,
                fieldnames=[
                    "company_name",
                    "domain",
                    "contact_route_type",
                    "contact_value",
                    "contact_role_hint",
                    "confidence",
                    "source_url",
                    "evidence_snippet",
                    "discovered_at",
                ],
            )
            w.writeheader()
            w.writerows(rows)
        return len(rows)

    def get_refined_leads(self) -> list[dict[str, Any]]:
        """One row per company: best contact URL (form) and best email for sponsorship/partnership."""
        all_leads = self.get_all_leads()
        by_company: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for r in all_leads:
            key = (r["company_name"], r["domain"])
            by_company.setdefault(key, []).append(r)

        refined: list[dict[str, Any]] = []
        for (company_name, domain), leads in sorted(by_company.items(), key=lambda x: (x[0][0], x[0][1])):
            best_url = ""
            best_email = ""
            for r in leads:
                if r["contact_route_type"] == "form" and not best_url:
                    best_url = r["contact_value"]
                if r["contact_route_type"] == "email" and not best_email:
                    best_email = r["contact_value"]
            if not best_url:
                for r in leads:
                    if r["contact_route_type"] == "linkedin":
                        best_url = r["contact_value"]
                        break
            refined.append({
                "company_name": company_name,
                "domain": domain,
                "best_contact_url": best_url,
                "best_contact_email": best_email,
            })
        return refined

    def export_refined_csv(self, out_path: str | Path) -> int:
        """Export one row per company with single best contact URL and best email."""
        import csv
        rows = self.get_refined_leads()
        if not rows:
            return 0
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(
                f,
                fieldnames=["company_name", "domain", "best_contact_url", "best_contact_email"],
            )
            w.writeheader()
            w.writerows(rows)
        return len(rows)
