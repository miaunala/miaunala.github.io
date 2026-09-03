"""Schritt 2b -- Belege aus den eigenen GitHub-Repos.

Idee: Statt zu *behaupten*, was man kann, wird es *belegt*. Fuer jeden eigenen
Skill sammeln wir Nachweise aus den Repos -- und zwar in vier Staerken:

  language    GitHub meldet die Sprache des Repos      (Python, R, Java, ...)
  file        Dateiendungen im Repo-Baum               (.sql, .Rmd, .ipynb, .pbix)
  dependency  Paket steht in requirements.txt & Co.    (pandas, ggplot2, ...)
  readme      Begriff kommt im README/der Beschreibung vor

Damit werden auch Skills belegt, die man im Code nicht "sieht" -- z.B.
"Regression" oder "Topic Modeling" stehen im README, nicht im Dateinamen.

Faellt GitHub aus (kein Token, kein Netz), liefert das Modul einfach nichts und
die Pipeline laeuft normal weiter.
"""
from __future__ import annotations

import base64
import json
import os
import re
import subprocess
import urllib.error
import urllib.request

from config import DETECTOR_VERSION, EXCLUDE_REPOS, GITHUB_USER
from extract import _matches

API = "https://api.github.com"
TIMEOUT = 20

# GitHub-Sprachname -> Skill-Label
LANG_SKILL = {
    "Python": "Python", "R": "R", "Java": "Java", "Stata": "Stata",
    "TypeScript": "TypeScript", "JavaScript": "JavaScript", "TeX": "LaTeX",
    "Jupyter Notebook": "Jupyter", "PLpgSQL": "SQL", "TSQL": "SQL", "SQLPL": "SQL",
}
# Dateiendung -> Skill (faengt Dinge, die die Sprachstatistik verschluckt)
EXT_SKILL = {
    ".py": "Python", ".r": "R", ".rmd": "R", ".ipynb": "Jupyter", ".sql": "SQL",
    ".do": "Stata", ".dta": "Stata", ".tex": "LaTeX", ".pbix": "Power BI",
    ".twb": "Tableau", ".twbx": "Tableau", ".java": "Java",
}
# Aus diesen Dateien lesen wir Bibliotheken heraus
MANIFESTS = ("requirements.txt", "pyproject.toml", "environment.yml",
             "environment.yaml", "DESCRIPTION", "renv.lock", "Pipfile", "package.json")
MAX_MANIFESTS_PER_REPO = 3

# Code-Dateien, die wir wirklich AUFMACHEN (nicht nur ihren Namen ansehen).
# Da stecken die Imports und die SQL-Logik drin -- die eigentliche Substanz.
CODE_EXT = {".py", ".r", ".rmd", ".sql", ".java", ".do", ".ipynb", ".qmd"}
MAX_CODE_FILES_PER_REPO = 10      # Deckel gegen API-Limits
MAX_FILE_BYTES = 300_000          # riesige Notebooks ueberspringen

# SQL "im Code": Abfragen stecken oft als String in Python/R statt in .sql-Dateien.
# Zwei unabhaengige Signale noetig, damit ein blosses "select" nicht reicht.
SQL_PATTERNS = [
    re.compile(r"\bselect\b[\s\S]{0,400}?\bfrom\b", re.I),
    re.compile(r"\b(left|right|inner|outer|cross)\s+join\b", re.I),
    re.compile(r"\bgroup\s+by\b", re.I),
    re.compile(r"\border\s+by\b", re.I),
    re.compile(r"\b(create|alter|drop)\s+(table|view|schema)\b", re.I),
    re.compile(r"\bwith\s+\w+\s+as\s*\(", re.I),      # CTE
    re.compile(r"\b(read_sql|to_sql|dbGetQuery|sqlalchemy|psycopg2|duckdb)\b", re.I),
]


# Relationales Arbeiten zeigt sich oft NICHT als SQL, sondern als dplyr/pandas:
# Mehrtabellen-Joins ueber zusammengesetzte Schluessel sind Data Modeling --
# aber eben nicht "SQL". Diese Ehrlichkeit ist wichtig.
RELATIONAL_PATTERNS = [
    re.compile(r"\b(left|right|inner|full|anti|semi)_join\s*\(", re.I),   # dplyr
    re.compile(r"\bgroup_by\s*\(", re.I),
    re.compile(r"\bpd\.merge\s*\(|\.merge\s*\(", re.I),               # pandas
    re.compile(r"\.groupby\s*\(", re.I),
    re.compile(r"\bpivot_longer\s*\(|\bpivot_wider\s*\(|\.pivot_table\s*\(", re.I),
]


def _looks_relational(text: str) -> int:
    return sum(1 for p in RELATIONAL_PATTERNS if p.search(text))


def _looks_like_sql(text: str) -> int:
    """Wie viele unabhaengige SQL-Signale enthaelt der Text?"""
    return sum(1 for p in SQL_PATTERNS if p.search(text))


def _token() -> str | None:
    """Token aus der Umgebung (CI) oder von der lokal eingeloggten gh-CLI."""
    tok = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if tok:
        return tok
    try:
        out = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, timeout=10)
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except Exception:
        pass
    return None


def _has_gh() -> bool:
    try:
        return subprocess.run(["gh", "--version"], capture_output=True,
                              timeout=10).returncode == 0
    except Exception:
        return False


_GH = None  # lazy: gh-CLI verfuegbar?


def _ssl_ctx():
    """macOS-Python bringt oft keine CA-Zertifikate mit -> certifi nutzen."""
    import ssl
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def _api(path: str, token: str | None):
    """Bevorzugt die gh-CLI (loest TLS/Auth selbst und ist auf CI-Runnern da),
    sonst direkt per HTTPS."""
    global _GH
    if _GH is None:
        _GH = _has_gh()
    if _GH:
        out = subprocess.run(["gh", "api", path], capture_output=True,
                             text=True, timeout=TIMEOUT)
        if out.returncode == 0:
            return json.loads(out.stdout)
        raise RuntimeError((out.stderr or "gh api fehlgeschlagen")[:200])

    req = urllib.request.Request(API + path)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "skill-pipeline")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=TIMEOUT, context=_ssl_ctx()) as r:
        return json.loads(r.read())


def _safe(fn, default):
    try:
        return fn()
    except Exception:
        return default


def _decode(payload) -> str:
    if isinstance(payload, dict) and payload.get("encoding") == "base64":
        try:
            return base64.b64decode(payload.get("content", "")).decode("utf-8", "replace")
        except Exception:
            return ""
    return ""


def collect(known: dict[str, str] | None = None):
    """Belege einsammeln.

    `known` = {repo: pushed_at} aus dem letzten Lauf. Repos ohne neue Commits
    werden uebersprungen -- so kostet der Wochenlauf fast nichts und nur wirklich
    veraenderte Repos werden neu gelesen.

    -> (rows, contexts, pushed_map, scanned) mit rows = [(term, repo, kind)]
    """
    known = known or {}
    token = _token()
    repos = _safe(lambda: _api(f"/users/{GITHUB_USER}/repos?per_page=100&sort=updated", token), None)
    if not repos:
        print("[github] Keine Repos abrufbar (kein Token/Netz?) -- Schritt uebersprungen.")
        return [], {}, {}, set()

    evidence: set[tuple[str, str, str]] = set()
    contexts: dict[str, list[str]] = {}
    pushed_map: dict[str, str] = {}
    scanned: set[str] = set()
    skipped = 0

    def add_ctx(term: str, sents: list[str]) -> None:
        cur = contexts.setdefault(term, [])
        for sent in sents[:2]:
            if sent not in cur and len(cur) < 4:
                cur.append(sent)

    for repo in repos:
        name = repo.get("name", "")
        # Forks belegen nichts (fremder Code); das Portfolio-Repo selbst waere
        # eine Falschquelle -- seine README *diskutiert* Skills als Thema.
        if repo.get("fork") or name in EXCLUDE_REPOS or not name:
            continue

        pushed = repo.get("pushed_at") or ""
        pushed_map[name] = pushed
        if known.get(name) == pushed:
            skipped += 1          # unveraendert -> alte Belege bleiben stehen
            continue
        scanned.add(name)

        # 1) Sprachen
        langs = _safe(lambda: _api(f"/repos/{GITHUB_USER}/{name}/languages", token), {}) or {}
        for lang in langs:
            skill = LANG_SKILL.get(lang)
            if skill:
                evidence.add((skill, name, "language"))

        # 2) Dateibaum -> Endungen, Manifeste und Kandidaten fuer die Code-Analyse
        branch = repo.get("default_branch") or "main"
        tree = _safe(lambda: _api(f"/repos/{GITHUB_USER}/{name}/git/trees/{branch}?recursive=1", token), {}) or {}
        manifest_paths: list[str] = []
        code_files: list[tuple[int, str]] = []
        for node in (tree.get("tree") or []):
            if node.get("type") != "blob":
                continue
            path = node.get("path", "")
            size = int(node.get("size") or 0)
            low = path.lower()
            dot = low.rfind(".")
            ext = low[dot:] if dot > 0 else ""
            if ext:
                skill = EXT_SKILL.get(ext)
                if skill:
                    evidence.add((skill, name, "file"))
                if ext in CODE_EXT and 0 < size <= MAX_FILE_BYTES:
                    code_files.append((size, path))
            base = path.rsplit("/", 1)[-1]
            if base in MANIFESTS and len(manifest_paths) < MAX_MANIFESTS_PER_REPO:
                manifest_paths.append(path)

        # 3) Abhaengigkeiten aus den Manifesten
        for path in manifest_paths:
            payload = _safe(lambda: _api(f"/repos/{GITHUB_USER}/{name}/contents/{path}", token), None)
            text = _decode(payload)
            if not text:
                continue
            for term in _matches(text):
                evidence.add((term, name, "dependency"))

        # 4) Code wirklich lesen: Imports + SQL-Logik. Groesste Dateien zuerst --
        #    da steckt in der Regel die eigentliche Arbeit drin.
        code_files.sort(reverse=True)
        for _, path in code_files[:MAX_CODE_FILES_PER_REPO]:
            payload = _safe(lambda: _api(f"/repos/{GITHUB_USER}/{name}/contents/{path}", token), None)
            text = _decode(payload)
            if not text:
                continue
            for term in _matches(text):
                evidence.add((term, name, "code"))
            # SQL steht meist als String im Python/R-Code, nicht in .sql-Dateien.
            if _looks_like_sql(text) >= 2:
                evidence.add(("SQL", name, "code"))
            # dplyr/pandas-Joins: relationales Arbeiten. dplyr ist bewusst nach
            # SQL-Verben modelliert (dbplyr uebersetzt es sogar nach SQL), daher
            # zaehlt es als SQL-Logik -- aber mit eigener, ehrlicher Beleg-Art,
            # damit im Panel sichtbar bleibt, worauf der Beleg beruht.
            if _looks_relational(text) >= 2:
                evidence.add(("Data Modeling", name, "code"))
                evidence.add(("SQL", name, "sql-logic"))

        # 5) README + Beschreibung -> hier stehen die Methoden ("Regression", ...)
        readme = _safe(lambda: _api(f"/repos/{GITHUB_USER}/{name}/readme", token), None)
        text = "\n".join(filter(None, [repo.get("description") or "", _decode(readme)]))
        if text.strip():
            for term, sents in _matches(text).items():
                evidence.add((term, name, "readme"))
                add_ctx(term, sents)

    if skipped:
        print(f"[github] {skipped} Repos unveraendert -> uebersprungen.")
    return sorted(evidence), contexts, pushed_map, scanned


def evidence(run_date=None) -> int:
    """Belege einsammeln und in DuckDB ablegen (inkrementell).

    Nur Repos mit neuen Commits werden neu gelesen; deren alte Belege werden
    ersetzt. Belege verschwundener Repos werden aufgeraeumt. Neu belegte
    Begriffe kommen als Term ins Netz (total_count 0), die README-Saetze dienen
    zugleich als Kontext fuer classify.py.
    """
    import datetime as dt

    from db import connect

    week = (run_date or dt.date.today())
    week = week - dt.timedelta(days=week.weekday())

    con = connect()
    known = {r: p for r, p in con.execute(
        "SELECT repo, pushed_at FROM repo_scan WHERE detector = ?",
        [DETECTOR_VERSION]).fetchall()}

    rows, contexts, pushed_map, scanned = collect(known)
    if not pushed_map:                      # GitHub nicht erreichbar
        con.close()
        return 0

    now = dt.datetime.now()
    # Belege von Repos, die es nicht mehr gibt, entfernen.
    for repo in list(known):
        if repo not in pushed_map:
            con.execute("DELETE FROM skill_evidence WHERE repo = ?", [repo])
            con.execute("DELETE FROM repo_scan WHERE repo = ?", [repo])
    # Nur neu gescannte Repos bekommen frische Belege.
    for repo in scanned:
        con.execute("DELETE FROM skill_evidence WHERE repo = ?", [repo])

    added = 0
    for term, repo, kind in rows:
        con.execute(
            "INSERT INTO skill_evidence (term, repo, kind) VALUES (?, ?, ?) ON CONFLICT DO NOTHING",
            [term, repo, kind])
        if con.execute("SELECT 1 FROM skill_terms WHERE term = ?", [term]).fetchone() is None:
            con.execute(
                """INSERT INTO skill_terms (term, first_seen, last_seen, total_count)
                   VALUES (?, ?, ?, 0)""", [term, week, week])
            added += 1
    for term, sents in contexts.items():
        for sent in sents:
            con.execute(
                "INSERT INTO skill_contexts (term, snippet, week) VALUES (?, ?, ?) ON CONFLICT DO NOTHING",
                [term, sent[:400], week])
    for repo, pushed in pushed_map.items():
        con.execute(
            """INSERT INTO repo_scan (repo, pushed_at, detector, scanned_at)
               VALUES (?, ?, ?, ?)
               ON CONFLICT DO UPDATE SET pushed_at = excluded.pushed_at,
                                         detector = excluded.detector,
                                         scanned_at = excluded.scanned_at""",
            [repo, pushed, DETECTOR_VERSION, now])

    total = con.execute("SELECT COUNT(*) FROM skill_evidence").fetchone()[0]
    proven = con.execute("SELECT COUNT(DISTINCT term) FROM skill_evidence").fetchone()[0]
    con.close()
    print(f"[github] {len(scanned)} Repos gescannt, {total} Belege fuer {proven} Skills "
          f"({added} neu ins Netz aufgenommen).")
    return proven
