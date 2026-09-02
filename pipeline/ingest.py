"""Schritt 1 -- Ingest: Job-Anzeigen holen und in die raw-Schicht schreiben.

Ohne Adzuna-Key laeuft alles offline mit den Beispiel-Anzeigen in
sample_data/postings.json. Sobald ADZUNA_APP_ID und ADZUNA_KEY als
Umgebungsvariablen gesetzt sind, wird die echte API abgefragt.
"""
from __future__ import annotations

import datetime as dt
import json
import os

from config import SAMPLE_POSTINGS, TARGET_ROLES
from db import connect


def _monday(d: dt.date) -> dt.date:
    """Montag der Woche -- unser Wochen-Partitionsschluessel."""
    return d - dt.timedelta(days=d.weekday())


def _fetch_adzuna(role: str, country: str = "de", pages: int = 1) -> list[dict]:
    """Echte Adzuna-API. Gratis-Tier: https://developer.adzuna.com/"""
    import requests

    app_id = os.environ["ADZUNA_APP_ID"]
    app_key = os.environ["ADZUNA_KEY"]
    results: list[dict] = []
    for page in range(1, pages + 1):
        url = f"https://api.adzuna.com/v1/api/jobs/{country}/search/{page}"
        resp = requests.get(
            url,
            params={
                "app_id": app_id,
                "app_key": app_key,
                "what_phrase": role,
                "results_per_page": 50,
                "content-type": "application/json",
            },
            timeout=30,
        )
        resp.raise_for_status()
        for job in resp.json().get("results", []):
            results.append(
                {
                    "source": "adzuna",
                    "external_id": str(job.get("id")),
                    "role": role,
                    "title": job.get("title", ""),
                    "description": job.get("description", ""),
                }
            )
    return results


def _load_sample() -> list[dict]:
    return json.loads(SAMPLE_POSTINGS.read_text(encoding="utf-8"))


def ingest(run_date: dt.date | None = None) -> int:
    """Holt Anzeigen und schreibt sie idempotent in raw_job_postings."""
    week = _monday(run_date or dt.date.today())
    use_api = bool(os.environ.get("ADZUNA_APP_ID") and os.environ.get("ADZUNA_KEY"))

    if use_api:
        postings: list[dict] = []
        for role in TARGET_ROLES:
            postings.extend(_fetch_adzuna(role))
        print(f"[ingest] {len(postings)} Anzeigen von Adzuna geholt.")
    else:
        postings = _load_sample()
        print(f"[ingest] Kein Adzuna-Key -> {len(postings)} Beispiel-Anzeigen.")

    con = connect()
    inserted = 0
    for p in postings:
        con.execute(
            """
            INSERT INTO raw_job_postings
                (source, external_id, role, title, description, ingest_week)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT DO NOTHING
            """,
            [p["source"], p["external_id"], p.get("role", ""),
             p.get("title", ""), p.get("description", ""), week],
        )
        inserted += 1
    con.close()
    print(f"[ingest] Woche {week}: {inserted} Anzeigen verarbeitet.")
    return inserted


if __name__ == "__main__":
    ingest()
