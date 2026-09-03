"""Schritt 2 -- Extraktion: Skills UND ihren Kontext aus dem Freitext ziehen.

Version 1: Dictionary-Matching gegen seed_skills.py. Robust und erklaerbar.
Zusaetzlich wird pro Begriff der SATZ gemerkt, in dem er vorkam -- diese echte
Job-Sprache disambiguiert spaeter Marken-Begriffe (classify.py).

Upgrade-Pfad (in der README vermerkt): spaCy noun_chunks fuer NEUE, noch
unbekannte Begriffe, damit das Netz organisch waechst.
"""
from __future__ import annotations

import datetime as dt
import re

from db import connect
from own_skills import own_skills
from seed_skills import SEED_SKILLS

# canonical -> Liste vorkompilierter Alias-Patterns (Wortgrenzen, case-insensitive)
_PATTERNS: dict[str, list[re.Pattern]] = {
    canonical: [re.compile(rf"(?<![\w-]){re.escape(a)}(?![\w-])", re.I) for a in aliases]
    for canonical, aliases in SEED_SKILLS.items()
}

_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")
MAX_CONTEXTS_PER_TERM = 5   # so viele Kontext-Saetze pro Begriff maximal sammeln


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENT_SPLIT.split(text or "") if s.strip()]


def _matches(text: str) -> dict[str, list[str]]:
    """canonical -> Saetze im Text, die den Begriff enthalten (leer = nicht gefunden)."""
    sents = _sentences(text)
    hits: dict[str, list[str]] = {}
    for canonical, patterns in _PATTERNS.items():
        ctx = [s for s in sents if any(p.search(s) for p in patterns)]
        if ctx:
            hits[canonical] = ctx
    return hits


def extract(run_date: dt.date | None = None) -> int:
    con = connect()
    week = con.execute("SELECT max(ingest_week) FROM raw_job_postings").fetchone()[0]
    if week is None:
        print("[extract] Keine Anzeigen vorhanden -- erst ingest laufen lassen.")
        con.close()
        return 0

    rows = con.execute(
        "SELECT title || '. ' || description FROM raw_job_postings WHERE ingest_week = ?",
        [week],
    ).fetchall()

    counts: dict[str, int] = {}
    contexts: dict[str, set[str]] = {}
    for (text,) in rows:
        for term, sents in _matches(text or "").items():
            counts[term] = counts.get(term, 0) + 1
            bucket = contexts.setdefault(term, set())
            for s in sents:
                if len(bucket) < MAX_CONTEXTS_PER_TERM:
                    bucket.add(s[:220])   # Snippet kappen

    for term, freq in counts.items():
        con.execute(
            """INSERT INTO skill_weekly_freq (term, week, frequency) VALUES (?, ?, ?)
               ON CONFLICT DO UPDATE SET frequency = excluded.frequency""",
            [term, week, freq],
        )
        con.execute(
            """INSERT INTO skill_terms (term, first_seen, last_seen, total_count)
               VALUES (?, ?, ?, ?)
               ON CONFLICT DO UPDATE SET
                   last_seen = excluded.last_seen,
                   total_count = skill_terms.total_count + excluded.total_count""",
            [term, week, week, freq],
        )
        for snippet in contexts.get(term, set()):
            con.execute(
                """INSERT INTO skill_contexts (term, snippet, week) VALUES (?, ?, ?)
                   ON CONFLICT DO NOTHING""",
                [term, snippet, week],
            )
    # Eigene Skills mit aufnehmen, damit sie im Netz auftauchen, auch wenn der
    # Markt sie (noch) nicht nennt. total_count bleibt bei 0 -> kleiner Punkt.
    own_added = 0
    for own in own_skills():
        label, hint = own["label"], own["hint"]
        cur = con.execute("SELECT 1 FROM skill_terms WHERE term = ?", [label]).fetchone()
        if cur is None:
            con.execute(
                """INSERT INTO skill_terms (term, first_seen, last_seen, total_count)
                   VALUES (?, ?, ?, 0)""",
                [label, week, week],
            )
            own_added += 1
        # Herkunfts-Hinweis als Kontext -> gute Einordnung auch ohne Anzeigentext.
        con.execute(
            "INSERT INTO skill_contexts (term, snippet, week) VALUES (?, ?, ?) ON CONFLICT DO NOTHING",
            [label, hint, week],
        )

    con.close()
    print(f"[extract] Woche {week}: {len(counts)} Skills aus Anzeigen, "
          f"{sum(len(v) for v in contexts.values())} Kontext-Saetze, "
          f"{own_added} eigene Skills ergaenzt.")
    return len(counts)


if __name__ == "__main__":
    extract()
