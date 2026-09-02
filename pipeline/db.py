"""DuckDB-Verbindung und Schema.

DuckDB ist hier Speicher UND Transformations-Engine in einer einzigen Datei
(warehouse.duckdb). Kein Server, kein Setup -- das ersetzt fuer unser Volumen
ein Snowflake/Databricks-Warehouse vollstaendig.
"""
from __future__ import annotations

import duckdb

from config import DB_PATH

SCHEMA = """
-- Rohe Job-Anzeigen, append-only (die "raw"-Schicht)
CREATE TABLE IF NOT EXISTS raw_job_postings (
    source       TEXT,
    external_id  TEXT,
    role         TEXT,
    title        TEXT,
    description  TEXT,
    ingest_week  DATE,
    PRIMARY KEY (source, external_id, ingest_week)
);

-- Normalisierte Begriffe (die "mart"-Schicht)
CREATE TABLE IF NOT EXISTS skill_terms (
    term        TEXT PRIMARY KEY,
    first_seen  DATE,
    last_seen   DATE,
    total_count INTEGER DEFAULT 0
);

-- Zeitreihe: wie oft ein Begriff pro Woche auftaucht (der Trend-Schatz)
CREATE TABLE IF NOT EXISTS skill_weekly_freq (
    term      TEXT,
    week      DATE,
    frequency INTEGER,
    PRIMARY KEY (term, week)
);

-- Kontext-Saetze, in denen ein Begriff vorkam (fuers Kontext-Embedding).
-- Genau diese echte Job-Sprache disambiguiert Marken wie "Snowflake".
CREATE TABLE IF NOT EXISTS skill_contexts (
    term    TEXT,
    snippet TEXT,
    week    DATE,
    PRIMARY KEY (term, snippet)
);

-- Ergebnis des Clustering-Laufs: Begriff -> Anker(n) + Konfidenz.
-- Mehrere Zeilen pro Begriff moeglich (Mehrfach-Zuordnung); is_primary
-- markiert den staerksten Anker.
CREATE TABLE IF NOT EXISTS skill_clusters (
    term       TEXT,
    anchor     TEXT,
    confidence REAL,
    is_primary BOOLEAN,
    run_at     TIMESTAMP,
    PRIMARY KEY (term, anchor)
);
"""


def connect() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(str(DB_PATH))
    con.execute(SCHEMA)
    return con
