"""Schritt 4 -- Export: das Ergebnis als market_skills.json fuer die Webseite.

Struktur bewusst kompatibel zu skills.json (categories -> skills), damit der
bestehende SkillGraph es spaeter mit minimalem Aufwand rendern kann. Zusaetzlich
je Skill: count (Nachfrage) und trend (Veraenderung zur Vorwoche).
"""
from __future__ import annotations

import datetime as dt
import json

from config import (ANCHOR_DESCRIPTIONS, ANCHORS, EXPORT_PATH,
                    TOP_N_PER_CATEGORY)
from db import connect
from seed_skills import SEED_LANGUAGE


def _slug(s: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in s.lower()).strip("-")


def export() -> None:
    con = connect()

    # Trend: Frequenz der letzten vs. vorletzten erfassten Woche.
    weeks = [r[0] for r in con.execute(
        "SELECT DISTINCT week FROM skill_weekly_freq ORDER BY week DESC LIMIT 2").fetchall()]
    last_week = weeks[0] if weeks else None
    prev_week = weeks[1] if len(weeks) > 1 else None

    # Sekundaer-Anker je Begriff (fuer die "also"-Kanten im Graph).
    also_map: dict[str, list[str]] = {}
    for term, anchor in con.execute(
        "SELECT term, anchor FROM skill_clusters WHERE NOT is_primary").fetchall():
        also_map.setdefault(term, []).append(anchor)

    categories = []
    for anchor in list(ANCHORS.keys()):
        rows = con.execute(
            """
            SELECT t.term, t.total_count, c.confidence,
                   COALESCE(f_now.frequency, 0)  AS freq_now,
                   COALESCE(f_prev.frequency, 0) AS freq_prev
            FROM skill_clusters c
            JOIN skill_terms t ON t.term = c.term
            LEFT JOIN skill_weekly_freq f_now  ON f_now.term  = t.term AND f_now.week  = ?
            LEFT JOIN skill_weekly_freq f_prev ON f_prev.term = t.term AND f_prev.week = ?
            WHERE c.anchor = ? AND c.is_primary          -- nur wo dies der Haupt-Anker ist
            ORDER BY t.total_count DESC
            LIMIT ?
            """,
            [last_week, prev_week, anchor, TOP_N_PER_CATEGORY],
        ).fetchall()

        skills = []
        for term, total, conf, freq_now, freq_prev in rows:
            skill = {
                "label": term,
                "count": int(total),
                "confidence": round(float(conf), 3),
                "trend": int(freq_now) - int(freq_prev),
                "also": also_map.get(term, []),   # weitere Kategorien (Mehrfach-Zuordnung)
                "mine": False,                     # wird spaeter im Editor auf True gesetzt
            }
            if term in SEED_LANGUAGE:
                skill["lang"] = SEED_LANGUAGE[term]  # Library -> Programmiersprache
            skills.append(skill)
        categories.append({
            "id": _slug(anchor),
            "label": anchor,
            "description": ANCHOR_DESCRIPTIONS.get(anchor, ""),
            "skills": skills,
        })

    # Uncategorized separat -- Signal fuer kuenftige Kategorien, nicht als Hauptknoten.
    unc = con.execute(
        """SELECT t.term, t.total_count FROM skill_clusters c
           JOIN skill_terms t ON t.term = c.term
           WHERE c.anchor = 'Uncategorized' ORDER BY t.total_count DESC""").fetchall()
    con.close()

    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "week": str(last_week) if last_week else None,
        "categories": categories,
        "uncategorized": [{"label": t, "count": int(c)} for t, c in unc],
    }
    EXPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    EXPORT_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    n = sum(len(c["skills"]) for c in categories)
    print(f"[export] {n} Skills in {len(categories)} Kategorien -> {EXPORT_PATH}")


if __name__ == "__main__":
    export()
