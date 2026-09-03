"""Schritt 2d -- implizite Skills per lokalem LLM (gratis, via Ollama).

Der Ansatz ist genau der gewuenschte: dem Modell wird das *bestehende Netz*
(die Knoten) plus ein Repo gezeigt, und es sagt, welche Knoten dieses Repo
abdeckt. Geschlossene Liste = das Modell kann nichts erfinden, es darf nur
aus vorhandenen Knoten waehlen.

Warum das etwas findet, das das Dictionary nicht findet: "predicted permit
approval times" nennt weder "Regression" noch "Time Series Forecasting" -- ein
Modell schliesst es trotzdem.

Kosten: keine. Laeuft gegen ein lokales Ollama (OLLAMA_HOST, Standard
http://localhost:11434). Ist Ollama nicht erreichbar, wird der Schritt einfach
uebersprungen -- die Pipeline laeuft normal weiter.

Nur Repos mit neuen Commits werden analysiert (repo_scan), also im Wochenlauf
meist gar keine.
"""
from __future__ import annotations

import json
import os
import urllib.request

from config import DETECTOR_VERSION, EXCLUDE_REPOS, GITHUB_USER
from github_skills import _api, _decode, _safe, _token

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
# Modell nicht fest verdrahten: nehmen, was lokal installiert ist. Reihenfolge
# der Vorlieben -- Apertus (Schweizer offenes Modell) zuerst.
MODEL_PREFERENCE = ("apertus", "qwen", "llama", "mistral", "gemma")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "")   # leer = automatisch waehlen
MAX_CHARS = 6000       # so viel Repo-Text bekommt das Modell
TIMEOUT = 180


def _available_models() -> list[str]:
    try:
        with urllib.request.urlopen(f"{OLLAMA_HOST}/api/tags", timeout=5) as r:
            return [m.get("name", "") for m in json.loads(r.read()).get("models", [])]
    except Exception:
        return []


def _pick_model() -> str:
    """Konfiguriertes Modell, sonst das erste installierte nach Vorliebe."""
    if OLLAMA_MODEL:
        return OLLAMA_MODEL
    models = [m for m in _available_models() if m and not m.endswith(":cloud")]
    for want in MODEL_PREFERENCE:
        for m in models:
            if want in m.lower():
                return m
    return models[0] if models else ""


def _ask(prompt: str, model: str) -> str:
    payload = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": False,
        "format": "json",          # erzwingt gueltiges JSON
        "options": {"temperature": 0},
    }).encode()
    req = urllib.request.Request(f"{OLLAMA_HOST}/api/generate", data=payload,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read()).get("response", "")


def _prompt(nodes: list[str], repo: str, description: str, text: str) -> str:
    return (
        "You map a GitHub repository onto an EXISTING skill graph.\n\n"
        "SKILL NODES (choose ONLY from this list, exact spelling):\n"
        + ", ".join(nodes) + "\n\n"
        f"REPOSITORY: {repo}\n"
        f"DESCRIPTION: {description}\n"
        "CONTENT (README and code excerpts):\n"
        f"{text[:MAX_CHARS]}\n\n"
        "Which nodes does this repository actually demonstrate? Be STRICT: include a "
        "node ONLY if the CONTENT above literally supports it. For every node you "
        "must copy a VERBATIM quote from the CONTENT as proof -- if you cannot quote "
        "it word-for-word, leave the node out. Never guess from the project topic.\n"
        'Answer as JSON: {"skills": [{"name": "<node>", "quote": "<verbatim excerpt '
        'from CONTENT>", "why": "<one short sentence>"}]}'
    )


def _quote_ok(quote: str, haystack: str) -> bool:
    """Zitat muss wirklich im Quelltext stehen -- die Bremse gegen Halluzination."""
    q = " ".join((quote or "").split()).lower()
    if len(q) < 12:            # zu kurz, um etwas zu belegen
        return False
    return q in " ".join(haystack.split()).lower()


def llm_evidence(run_date=None) -> int:
    """Implizite Skills ergaenzen. Gibt die Anzahl neuer Belege zurueck."""
    import datetime as dt

    from db import connect

    model = _pick_model()
    if not model:
        print(f"[llm] Kein lokales Modell unter {OLLAMA_HOST} -- Schritt uebersprungen.")
        return 0

    week = (run_date or dt.date.today())
    week = week - dt.timedelta(days=week.weekday())

    con = connect()
    nodes = [r[0] for r in con.execute("SELECT term FROM skill_terms ORDER BY term").fetchall()]
    if not nodes:
        con.close()
        return 0
    # Nur Repos, die seit der letzten LLM-Analyse neue Commits haben.
    todo = [r[0] for r in con.execute(
        """SELECT repo FROM repo_scan
           WHERE detector = ? AND repo NOT IN (SELECT repo FROM llm_scan WHERE detector = ?)""",
        [DETECTOR_VERSION, DETECTOR_VERSION]).fetchall()]
    if not todo:
        con.close()
        print("[llm] Keine neuen/geaenderten Repos -- nichts zu tun.")
        return 0

    token = _token()
    added = 0
    dropped = 0
    for repo in todo:
        if repo in EXCLUDE_REPOS:
            continue
        meta = _safe(lambda: _api(f"/repos/{GITHUB_USER}/{repo}", token), {}) or {}
        readme = _safe(lambda: _api(f"/repos/{GITHUB_USER}/{repo}/readme", token), None)
        text = _decode(readme)
        if not text.strip():
            text = meta.get("description") or ""
        try:
            raw = _ask(_prompt(nodes, repo, meta.get("description") or "", text), model)
            picked = json.loads(raw).get("skills", [])
        except Exception as exc:
            print(f"[llm] {repo}: Analyse fehlgeschlagen ({type(exc).__name__}) -- uebersprungen.")
            continue

        valid = {n.lower(): n for n in nodes}
        source = f"{meta.get('description') or ''}\n{text[:MAX_CHARS]}"
        for item in picked:
            name = valid.get(str(item.get("name", "")).strip().lower())
            if not name:
                continue          # ausserhalb der Liste -> verwerfen
            if not _quote_ok(str(item.get("quote", "")), source):
                dropped += 1      # kein pruefbares Zitat -> verwerfen
                continue
            con.execute(
                "INSERT INTO skill_evidence (term, repo, kind) VALUES (?, ?, 'llm') ON CONFLICT DO NOTHING",
                [name, repo])
            why = str(item.get("why", ""))[:300]
            if why:
                con.execute(
                    "INSERT INTO skill_contexts (term, snippet, week) VALUES (?, ?, ?) ON CONFLICT DO NOTHING",
                    [name, why, week])
            added += 1
        con.execute(
            """INSERT INTO llm_scan (repo, detector, scanned_at) VALUES (?, ?, ?)
               ON CONFLICT DO UPDATE SET detector = excluded.detector,
                                         scanned_at = excluded.scanned_at""",
            [repo, DETECTOR_VERSION, dt.datetime.now()])

    con.close()
    print(f"[llm] {added} Vorschlaege aus {len(todo)} Repo(s) uebernommen, "
          f"{dropped} ohne pruefbares Zitat verworfen (Modell: {model}).")
    return added
