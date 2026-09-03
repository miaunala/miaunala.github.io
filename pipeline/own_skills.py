"""Die eigenen Skills (src/data/skills.json) in die Pipeline einspeisen.

Damit das eine Netz vollstaendig ist: Skills, die der Markt (noch) nicht nennt,
sollen trotzdem als Punkt erscheinen -- mit echten Embedding-Koordinaten, nicht
irgendwo hingesetzt. Als Kontext dient ihre Herkunft aus der eigenen Hierarchie
("DAGs: Airflow, Data Engineering"), damit die Einordnung sauber wird.
"""
from __future__ import annotations

import json

from config import ROOT

OWN_SKILLS_PATH = ROOT / "src" / "data" / "skills.json"


def own_skills() -> list[dict]:
    """[{label, hint}] fuer jeden eigenen Skill inkl. Sub-Skills."""
    if not OWN_SKILLS_PATH.exists():
        return []
    data = json.loads(OWN_SKILLS_PATH.read_text(encoding="utf-8"))
    out: list[dict] = []
    for cat in data.get("categories", []):
        cat_label = cat.get("label", "")
        for sk in cat.get("skills", []):
            label = sk.get("label", "")
            if label:
                out.append({"label": label, "hint": f"{label}: {cat_label}"})
            for ch in sk.get("children", []) or []:
                child = ch.get("label", "")
                if child:
                    # Sub-Skill bekommt Eltern-Skill UND Kategorie als Kontext.
                    out.append({"label": child, "hint": f"{child}: {label}, {cat_label}"})
    return out


def own_labels() -> set[str]:
    return {s["label"] for s in own_skills()}
