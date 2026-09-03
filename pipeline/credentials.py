"""Zertifikate als Beleg-Quelle (wie GitHub-Repos, nur aus src/data/credentials.json).

Ein Zertifikat belegt Skills, die man im Code nicht sehen kann -- Power BI, Excel,
Cloud-Zertifizierungen. Es landet als kind="certificate" in derselben Beleg-
Tabelle, damit das Panel es genauso ausweisen kann wie ein Repo.
"""
from __future__ import annotations

import json

from config import ROOT

CREDENTIALS_PATH = ROOT / "src" / "data" / "credentials.json"


def credentials() -> list[dict]:
    if not CREDENTIALS_PATH.exists():
        return []
    try:
        data = json.loads(CREDENTIALS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []
    # Unfertige Vorlagen zaehlen nicht als Beleg -- sonst behauptet die Seite
    # ein Zertifikat, das so noch gar nicht eingetragen ist.
    return [c for c in data.get("items", [])
            if c.get("title") and "[AUSFUELLEN]" not in c.get("title", "")]


def credential_skills() -> dict[str, list[dict]]:
    """skill -> [zertifikat, ...]"""
    out: dict[str, list[dict]] = {}
    for cred in credentials():
        for skill in cred.get("skills", []) or []:
            out.setdefault(skill, []).append(cred)
    return out


def store(run_date=None) -> int:
    """Zertifikats-Belege in DuckDB schreiben (ersetzt die alten)."""
    import datetime as dt

    from db import connect

    week = (run_date or dt.date.today())
    week = week - dt.timedelta(days=week.weekday())

    by_skill = credential_skills()
    con = connect()
    con.execute("DELETE FROM skill_evidence WHERE kind = 'certificate'")
    added = 0
    for skill, creds in by_skill.items():
        for cred in creds:
            con.execute(
                "INSERT INTO skill_evidence (term, repo, kind) VALUES (?, ?, ?) ON CONFLICT DO NOTHING",
                [skill, cred["title"], "certificate"])
        if con.execute("SELECT 1 FROM skill_terms WHERE term = ?", [skill]).fetchone() is None:
            con.execute(
                """INSERT INTO skill_terms (term, first_seen, last_seen, total_count)
                   VALUES (?, ?, ?, 0)""", [skill, week, week])
            added += 1
        # Der Zertifikatstitel dient zugleich als Kontext fuer die Einordnung.
        con.execute(
            "INSERT INTO skill_contexts (term, snippet, week) VALUES (?, ?, ?) ON CONFLICT DO NOTHING",
            [skill, f"{skill}: {creds[0]['title']}", week])
    con.close()
    if by_skill:
        print(f"[cert] {len(by_skill)} Skills durch Zertifikate belegt ({added} neu ins Netz).")
    return len(by_skill)
