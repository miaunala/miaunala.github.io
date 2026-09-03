"""Optionaler Schritt -- Duolingo-Streak fuer die Sprachen-Karte.

Kein offizieller API-Zugang: Duolingo hat einen inoffiziellen JSON-Endpunkt, den
Community-Tools nutzen. Entsprechend defensiv behandelt -- faellt er aus, bleibt
die zuletzt geschriebene Datei einfach stehen (kein Ueberschreiben mit Leere).

Bewusst NICHT abgeleitet: ein CEFR-Niveau. Der Endpunkt liefert nur XP, und XP
misst aufgewendete Zeit, nicht Koennen. Niveaus bleiben handgepflegt in
profile.json.
"""
from __future__ import annotations

import datetime as dt
import json
import urllib.request

from config import ROOT

USERNAME = "nathalie898983"
API = "https://www.duolingo.com/2017-06-30/users?username="
OUT_PATH = ROOT / "src" / "data" / "duolingo.json"
TIMEOUT = 15
MIN_XP = 1000          # Kurse darunter sind Ausprobieren, nicht Lernen


def _ssl_ctx():
    import ssl
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def duolingo() -> int:
    req = urllib.request.Request(API + USERNAME, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT, context=_ssl_ctx()) as r:
            users = json.loads(r.read()).get("users", [])
        user = users[0] if users else None
        if not user or not user.get("streak"):
            raise ValueError("keine brauchbaren Daten")
    except Exception as exc:
        print(f"[duolingo] Abruf fehlgeschlagen ({type(exc).__name__}) -- "
              f"bestehende Datei bleibt unveraendert.")
        return 0

    courses = sorted((c for c in user.get("courses", []) if c.get("xp", 0) >= MIN_XP),
                     key=lambda c: c.get("xp", 0), reverse=True)
    payload = {
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "profile": f"https://www.duolingo.com/profile/{USERNAME}",
        "streak": int(user["streak"]),
        "total_xp": int(user.get("totalXp") or 0),
        "top_course": courses[0]["title"] if courses else "",
    }
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"[duolingo] {payload['streak']} Tage Streak, "
          f"{payload['total_xp']:,} XP -> {OUT_PATH.name}")
    return payload["streak"]
