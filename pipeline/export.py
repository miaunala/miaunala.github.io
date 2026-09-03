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
from own_skills import own_labels
from seed_skills import SEED_LANGUAGE


def _slug(s: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in s.lower()).strip("-")


def export() -> None:
    con = connect()
    mine_labels = own_labels()

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

    # Belege aus den eigenen GitHub-Repos: term -> [{repo, kind}]
    evidence_map: dict[str, list[dict]] = {}
    for term, repo, kind in con.execute(
            "SELECT term, repo, kind FROM skill_evidence ORDER BY term, repo").fetchall():
        evidence_map.setdefault(term, []).append({"repo": repo, "kind": kind})
    # Harte Belege = alles ausser LLM. Ein LLM-Fund allein macht einen Skill NICHT
    # zu "meinem" -- Sprachmodelle behaupten sonst Kubernetes & Co. Er wird nur
    # vorgeschlagen und muss bestaetigt werden (spaeterer Editor).
    hard_evidence = {t for t, evs in evidence_map.items()
                     if any(e["kind"] != "llm" for e in evs)}

    # 2D-Koordinaten (PCA) je Begriff und je Kategorie.
    coord_map: dict[str, tuple[float, float]] = {
        t: (x, y) for t, x, y in con.execute("SELECT term, x, y FROM skill_coords").fetchall()
    }
    anchor_coord: dict[str, tuple[float, float]] = {
        a: (x, y) for a, x, y in con.execute("SELECT anchor, x, y FROM anchor_coords").fetchall()
    }

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
            """,
            [last_week, prev_week, anchor],
        ).fetchall()

        # Top-N nach Nachfrage, ABER eigene Skills immer behalten (sonst fehlen
        # sie im Netz, nur weil der Markt sie gerade nicht nennt).
        top = rows[:TOP_N_PER_CATEGORY]
        kept = list(top) + [r for r in rows[TOP_N_PER_CATEGORY:]
                            if r[0] in mine_labels or r[0] in hard_evidence]

        skills = []
        for term, total, conf, freq_now, freq_prev in kept:
            x, y = coord_map.get(term, (0.0, 0.0))
            skill = {
                "label": term,
                "count": int(total),
                "confidence": round(float(conf), 3),
                "trend": int(freq_now) - int(freq_prev),
                "also": also_map.get(term, []),   # weitere Kategorien (Mehrfach-Zuordnung)
                "x": round(float(x), 4),          # 2D-Position (PCA) fuer die Scatter-Ansicht
                "y": round(float(y), 4),
                # "mine" = selbst deklariert (skills.json) ODER in einem eigenen
                # Repo nachweisbar. Belege stehen in "evidence".
                "mine": (term in mine_labels) or (term in hard_evidence),
                "declared": term in mine_labels,
                # nur vom LLM vermutet, noch unbestaetigt
                "suggested": term in evidence_map and term not in hard_evidence
                             and term not in mine_labels,
                "evidence": evidence_map.get(term, []),
            }
            if term in SEED_LANGUAGE:
                skill["lang"] = SEED_LANGUAGE[term]  # Library -> Programmiersprache
            skills.append(skill)
        ax, ay = anchor_coord.get(anchor, (0.0, 0.0))
        categories.append({
            "id": _slug(anchor),
            "label": anchor,
            "description": ANCHOR_DESCRIPTIONS.get(anchor, ""),
            "x": round(float(ax), 4),
            "y": round(float(ay), 4),
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
