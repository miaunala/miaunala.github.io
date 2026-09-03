"""Zentrale Konfiguration der Skill-Pipeline.

Alles, was man beim Weiterbauen anfassen will, steht hier: die festen
Anker-Kategorien, die Rollen, nach denen gesucht wird, Pfade und Schwellenwerte.
"""
from __future__ import annotations

from pathlib import Path

# --- Pfade -----------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
PIPELINE_DIR = ROOT / "pipeline"
DB_PATH = PIPELINE_DIR / "warehouse.duckdb"          # das "Warehouse in einer Datei"
SAMPLE_POSTINGS = PIPELINE_DIR / "sample_data" / "postings.json"
EXPORT_PATH = ROOT / "src" / "data" / "market_skills.json"

# --- Feste Anker-Kategorien (Zero-shot-Klassifikation) ---------------------
# Jeder extrahierte Begriff wird dem Anker mit der hoechsten Cosine-Aehnlichkeit
# zugeordnet. Die Beschreibung rechts wird eingebettet -> je praeziser, desto
# besser trennen die Kategorien. Anker aendern = Kategorien der Webseite aendern.
ANCHORS: dict[str, str] = {
    "Data Engineering": "data engineering: building data pipelines, ETL and ELT, "
    "orchestration, data warehousing, batch and streaming ingestion",
    "Data Science": "data science: statistics, forecasting, experimentation, "
    "exploratory analysis, predictive modeling, visualization",
    "Machine Learning": "machine learning: model training and evaluation, "
    "classification, regression, deep learning, feature engineering",
    "NLP": "natural language processing: text processing, embeddings, "
    "large language models, named entity recognition, text classification",
}

# Kurzbeschreibung pro Kategorie fuers Frontend-Panel.
ANCHOR_DESCRIPTIONS: dict[str, str] = {
    "Data Engineering": "Robuste Datenbasis: Pipelines, Modellierung, Orchestrierung.",
    "Data Science": "Analysen, Prognosen und aussagekraeftige Auswertungen.",
    "Machine Learning": "Modelle von Klassifikation bis Deep Learning.",
    "NLP": "Sprache verstehen: Embeddings, LLMs, Textklassifikation.",
}

# Rollen, nach denen bei der Job-API / im Sample gesucht wird.
TARGET_ROLES = ["data engineer", "data scientist", "machine learning engineer"]

# --- Schwellenwerte --------------------------------------------------------
# Liegt die beste Anker-Aehnlichkeit darunter, gilt ein Begriff als
# "Uncategorized" -> Kandidat fuer eine kuenftig neue Kategorie.
# WICHTIG: Muss an echten Daten kalibriert werden (siehe classify.py, das die
# Score-Verteilung ausgibt). Der Startwert ist eine Schaetzung fuer bge-small.
ANCHOR_THRESHOLD = 0.30

# --- Mehrfach-Zuordnung (Soft Assignment) ----------------------------------
# Ein Begriff gehoert zu mehreren Ankern, wenn deren Cosine-Aehnlichkeit
# hoechstens MEMBERSHIP_MARGIN unter dem besten Anker liegt. Kleiner Wert =
# nur sehr aehnliche Anker (scharfe Zuordnung); groesser = mehr Kanten.
# So bekommt "Python" Kanten zu allen vier, "NER" nur zu NLP.
MEMBERSHIP_MARGIN = 0.045
MAX_MEMBERSHIPS = 4      # Deckel, wie viele Kategorien ein Begriff maximal bekommt

# Wie viele Skills pro Kategorie maximal ins Frontend-JSON exportiert werden.
TOP_N_PER_CATEGORY = 16

# Embedding-Modell (fastembed / ONNX, leichtgewichtig, 384 Dimensionen).
EMBED_MODEL = "BAAI/bge-small-en-v1.5"

# --- GitHub-Belege ---------------------------------------------------------
# Aus welchen Repos Skills belegt werden. Das Portfolio-Repo selbst ist
# ausgeschlossen: seine README *diskutiert* Skills als Thema (Snowflake, dbt,
# ...) und wuerde sonst Koennen vortaeuschen, das nicht belegt ist.
GITHUB_USER = "miaunala"
EXCLUDE_REPOS = {"miaunala.github.io"}

# Hochzaehlen, wenn sich die Erkennungslogik aendert -- erzwingt einen
# vollstaendigen Neu-Scan trotz unveraenderter Repos.
DETECTOR_VERSION = "3"
