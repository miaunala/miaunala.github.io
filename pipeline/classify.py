"""Schritt 3 -- Klassifikation: jeden Begriff einem festen Anker zuordnen.

Das ist Zero-shot-Klassifikation per Embeddings (kein k-Means!):
1. Anker-Beschreibungen und alle Begriffe werden eingebettet.
2. Fuer jeden Begriff -> Cosine-Aehnlichkeit zu jedem Anker.
3. Zuordnung zum naechsten Anker; liegt die beste Aehnlichkeit unter der
   Schwelle, wird der Begriff "Uncategorized" -> Signal fuer eine neue Kategorie.

Am Ende laeuft optional k-Means NUR auf den Uncategorized-Begriffen -- so
findet man Gruppen, die noch keine Kategorie haben (Wachstums-Mechanismus).
"""
from __future__ import annotations

import datetime as dt

import numpy as np

from config import (ANCHOR_THRESHOLD, ANCHORS, EMBED_MODEL, MAX_MEMBERSHIPS,
                    MEMBERSHIP_MARGIN)
from db import connect
from seed_skills import SEED_GLOSS


def _normalize(vecs: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    return vecs / np.clip(norms, 1e-9, None)


def _embed(texts: list[str]) -> np.ndarray:
    """L2-normalisierte Embeddings (dann ist Skalarprodukt = Cosine)."""
    from fastembed import TextEmbedding

    model = TextEmbedding(model_name=EMBED_MODEL)
    vecs = np.array(list(model.embed(texts)), dtype=np.float32)
    return _normalize(vecs)


def _store_coords(con, terms, term_emb, anchor_names, anchor_emb) -> None:
    """PCA der Embeddings auf 2D -- Anker und Begriffe im selben Raum, damit die
    Scatter-Ansicht die echte semantische Naehe zeigt (Punkte nah = aehnlich)."""
    from sklearn.decomposition import PCA

    stacked = np.vstack([anchor_emb, term_emb])
    coords = PCA(n_components=2, random_state=42).fit_transform(stacked)
    # auf ~[-1, 1] skalieren, damit das Frontend leicht positionieren kann
    span = np.abs(coords).max() or 1.0
    coords = coords / span

    a = len(anchor_names)
    con.execute("DELETE FROM anchor_coords")
    con.execute("DELETE FROM skill_coords")
    for i, name in enumerate(anchor_names):
        con.execute("INSERT INTO anchor_coords (anchor, x, y) VALUES (?, ?, ?)",
                    [name, float(coords[i, 0]), float(coords[i, 1])])
    for j, term in enumerate(terms):
        con.execute("INSERT INTO skill_coords (term, x, y) VALUES (?, ?, ?)",
                    [term, float(coords[a + j, 0]), float(coords[a + j, 1])])


def _term_texts(con, term: str) -> list[str]:
    """Begriff angereichert um Hand-Gloss und echte Kontext-Saetze."""
    texts = [term]
    gloss = SEED_GLOSS.get(term)
    if gloss:
        texts.append(f"{term}: {gloss}")
    snippets = con.execute(
        "SELECT snippet FROM skill_contexts WHERE term = ? LIMIT 5", [term]
    ).fetchall()
    texts.extend(s[0] for s in snippets)
    return texts


def classify() -> dict[str, str]:
    con = connect()
    terms = [r[0] for r in con.execute("SELECT term FROM skill_terms ORDER BY term").fetchall()]
    if not terms:
        print("[classify] Keine Begriffe -- erst extract laufen lassen.")
        con.close()
        return {}

    anchor_names = list(ANCHORS.keys())
    anchor_emb = _embed(list(ANCHORS.values()))       # (A, d)

    # Pro Begriff: alle angereicherten Texte einbetten und MITTELN.
    # Ein Flach-Batch fuer fastembed, danach gruppenweise gemittelt.
    flat_texts: list[str] = []
    groups: list[tuple[int, int]] = []                # (start, end) je Begriff
    for term in terms:
        tt = _term_texts(con, term)
        groups.append((len(flat_texts), len(flat_texts) + len(tt)))
        flat_texts.extend(tt)
    flat_emb = _embed(flat_texts)
    term_emb = _normalize(np.array([flat_emb[a:b].mean(axis=0) for a, b in groups]))

    _store_coords(con, terms, term_emb, anchor_names, anchor_emb)  # 2D fuer die Scatter-Ansicht

    sims = term_emb @ anchor_emb.T                    # (T, A) Cosine

    run_at = dt.datetime.now()
    con.execute("DELETE FROM skill_clusters")         # abgeleitet -> jedes Mal neu
    assignments: dict[str, str] = {}                  # Begriff -> primaerer Anker
    report: list[tuple[str, str, list[str], float]] = []

    for i, term in enumerate(terms):
        row = sims[i]
        best = float(row.max())
        if best < ANCHOR_THRESHOLD:
            memberships = [("Uncategorized", best)]
            primary = "Uncategorized"
        else:
            # Alle Anker behalten, die nah genug am besten liegen (Mehrfach-Zuordnung).
            order = row.argsort()[::-1]
            memberships = [
                (anchor_names[j], float(row[j]))
                for j in order
                if row[j] >= ANCHOR_THRESHOLD and (best - row[j]) <= MEMBERSHIP_MARGIN
            ][:MAX_MEMBERSHIPS]
            primary = memberships[0][0]

        assignments[term] = primary
        for anchor, score in memberships:
            con.execute(
                """INSERT INTO skill_clusters (term, anchor, confidence, is_primary, run_at)
                   VALUES (?, ?, ?, ?, ?)""",
                [term, anchor, score, anchor == primary, run_at],
            )
        report.append((term, primary, [a for a, _ in memberships[1:]], best))

    con.close()

    # --- Report zur Schwellen-Kalibrierung ---------------------------------
    print(f"[classify] {len(terms)} Begriffe, Schwelle = {ANCHOR_THRESHOLD}, "
          f"Margin = {MEMBERSHIP_MARGIN}")
    for term, primary, also, score in sorted(report, key=lambda x: x[3]):
        extra = f"  (+ {', '.join(also)})" if also else ""
        print(f"    {score:.3f}  {term:<28} -> {primary}{extra}")

    _suggest_new_clusters(assignments, terms, term_emb, anchor_names)
    return assignments


def _suggest_new_clusters(assignments, terms, term_emb, anchor_names) -> None:
    """k-Means NUR auf Uncategorized: gibt es dort schon eine Gruppe?"""
    unc = [t for t in terms if assignments[t] == "Uncategorized"]
    if len(unc) < 4:
        return
    from sklearn.cluster import KMeans

    idx = [terms.index(t) for t in unc]
    sub = term_emb[idx]
    k = min(3, len(unc) // 2)
    labels = KMeans(n_clusters=k, n_init=10, random_state=42).fit_predict(sub)
    print(f"[classify] Uncategorized-Gruppen (Kandidaten fuer neue Kategorien):")
    for c in range(k):
        members = [unc[i] for i in range(len(unc)) if labels[i] == c]
        print(f"    Gruppe {c}: {', '.join(members)}")


if __name__ == "__main__":
    classify()
