# miaunala.github.io

Persönliche Portfolio-Website von Nathalie Guibert (Nathi). Statisch, gebaut mit
[Astro](https://astro.build), gehostet auf GitHub Pages.

## Kernprinzip: eine Datenquelle speist alles

Die Dateien in `src/data/` sind die einzige Wahrheit:

- **`profile.json`** — Person, Bio, Kontakt, Engagement, Veranstaltungen.
- **`projects.json`** — alle Projekte mit nach Ebenen getrennten Tags
  (`method` / `domain` / `tool`).
- **`skills.json`** — *eigenes* Skill-Netz (handgepflegt): „was Nathalie kann".
- **`market_skills.json`** — *Markt*-Skill-Netz, von der Pipeline generiert
  (siehe [Skill-Pipeline](#skill-pipeline-pipeline)): „was der Markt verlangt".

Aus diesen Daten entstehen Projekt-Karten, der Tag-Filter, das Skill-Netzwerk und
(später) die tag-gefilterten CVs. Ein neues Projekt = ein Eintrag in
`projects.json`.

## Lokal entwickeln

Voraussetzung: Node.js 20+.

```bash
npm install      # Abhängigkeiten installieren (einmalig)
npm run dev      # Entwicklungsserver auf http://localhost:4321
npm run build    # Produktions-Build nach ./dist
npm run preview  # Build lokal ansehen
```

## Struktur

```
src/
  data/         profile, projects, skills, market_skills  (einzige Datenquelle)
  layouts/      Layout.astro                  (<head>, Fonts, Grundgerüst)
  components/   Header, Hero, About, ProjectGrid, ProjectCard, SkillGraph, CvSection, Footer
  pages/        index.astro                   (setzt die Startseite zusammen)
  styles/       global.css                    (Design-Tokens, hell/dunkel)
pipeline/       Skill-Pipeline (ingest → extract → classify → export), DuckDB
dags/           Airflow-DAG der Pipeline (optional, "Airflow im Portfolio")
.github/workflows/  deploy.yml (Pages) + skill-pipeline.yml (wöchentlicher Lauf)
```

## Deployment

`.github/workflows/deploy.yml` baut bei jedem Push auf `main` und deployt nach
GitHub Pages. **Einmalig einstellen:** GitHub → Repo → *Settings → Pages →
Build and deployment → Source = "GitHub Actions"*.

## Skill-Pipeline (`pipeline/`)

Ein datengetriebenes **Markt-Skill-Netz**: Job-Anzeigen → Skills extrahieren →
per Embeddings festen Kategorien zuordnen → als `market_skills.json` für die
Webseite exportieren. Läuft wöchentlich in GitHub Actions, komplett gratis.

**Zwei getrennte Netze** (bewusst nicht vermischen):

| | Markt-Netz | Eigenes Netz |
|---|---|---|
| Quelle | Pipeline (auto-generiert) | handgepflegt (`skills.json`) |
| Datei | `src/data/market_skills.json` | `src/data/skills.json` |
| Zweck | „Was der Markt verlangt" | „Was Nathalie kann" |

Idee: das Markt-Netz zeigen und die eigenen Skills darin hervorheben.

### Ablauf (`pipeline/run.py`)

```
ingest → extract → classify → export
```

1. **ingest** (`ingest.py`) — Job-Anzeigen holen. Ohne `ADZUNA_*`-Key laufen die
   Beispiel-Anzeigen in `sample_data/`; mit Key die echte
   [Adzuna-API](https://developer.adzuna.com/) (Gratis-Tier).
2. **extract** (`extract.py`) — Skills per Seed-Wörterbuch (`seed_skills.py`)
   aus dem Freitext ziehen; Wochen-Häufigkeit in DuckDB.
3. **classify** (`classify.py`) — jeden Begriff per Embedding (`fastembed`) den
   festen **Ankern** zuordnen (Zero-shot, kein k-Means). Eingebettet wird nicht
   das nackte Wort, sondern der Mittelwert aus **Begriff + Kontext-Sätzen** (aus
   den Anzeigen) + optionalem Hand-Gloss — das disambiguiert Marken wie
   „Snowflake". **Mehrfach-Zuordnung:** ein Begriff gehört zu allen Ankern, deren
   Ähnlichkeit höchstens `MEMBERSHIP_MARGIN` unter dem besten liegt — so bekommt
   `pandas` Kanten zu allen vier Kategorien, `Named Entity Recognition` nur zu
   NLP. Zu weit von allen Ankern → `Uncategorized`; k-Means läuft nur auf diesem
   Rest, um Gruppen für *neue* Kategorien vorzuschlagen. Alles in `config.py`.
4. **export** (`export.py`) — Ergebnis als `market_skills.json` (Struktur
   kompatibel zum SkillGraph). Je Skill: `count`, `trend`, `also` (weitere
   Kategorien der Mehrfach-Zuordnung) und `lang` (Sprache einer Library, für eine
   spätere „Sprache → Library"-Gruppierung).

`warehouse.duckdb` ist Speicher *und* Transformations-Engine in einer Datei
(ersetzt Snowflake/Databricks für dieses Volumen) und wird **absichtlich
mitversioniert**, damit die Wochen-Trends zwischen den Läufen erhalten bleiben.

### Lokal ausführen

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r pipeline/requirements.txt
cd pipeline && python run.py        # erzeugt src/data/market_skills.json
```

### Design-Entscheidungen (bewusst so gewählt)

- **DuckDB statt Snowflake/Databricks** — deren Free Tiers laufen ab / haben
  schlafende Cluster; DuckDB ist dauerhaft gratis, gleiche ELT-Story. dbt als
  Modellierungs-Layer ist der nächste Ausbauschritt.
- **GitHub Actions statt Airflow-Server** — ein Monats-/Wochenjob braucht keinen
  24/7-Server. Der Airflow-DAG (`dags/skill_pipeline.py`) existiert als
  „Airflow-im-Portfolio"-Variante und läuft per `airflow dags test` ohne Server.
- **APIs statt Scraping** — Adzuna & Co. sind erlaubt und strukturiert; LinkedIn/
  Indeed-Scraping verstößt gegen deren ToS (auch nicht-kommerziell).
- **`fastembed` (ONNX) statt `sentence-transformers`** — kein 800-MB-PyTorch,
  CI-freundlich.
- **Zero-shot statt eigenem Modell-Training** — ein selbst trainiertes kleines
  Modell wäre hier *schlechter*: das vortrainierte Embedding-Modell bringt bereits
  das Weltwissen mit, das „cloud data warehouse such as Snowflake" korrekt
  einordnet. Training würde erst lohnen, wenn (1) über Monate viele echte Daten
  vorliegen, (2) ein systematisches Fehlermuster besteht und (3) Labels da sind.
  Der elegante Pfad: der geplante **Editor liefert die Labels von selbst** (jede
  Bestätigung/Korrektur = ein Label) → später **contrastive Fine-tuning** des
  Embedding-Modells. Für Härtefälle *jetzt* eher ein gehostetes LLM pro
  unbekanntem Begriff (Cluster benennen, Einordnung) als Eigen-Training.

## Ideen für später

- **Editor mit Gamification** — bestätigte Skills per Klick pflegen; Skills aus
  dem Markt-Netz, die noch nicht „meine" sind, erscheinen als Vorschlags-Feed.
  Speicherung: `localStorage` + JSON-Export (kein Backend nötig).
- **Lern-/Zertifizierungs-Seite** — für Skills aus dem Markt-Netz, die man
  *noch nicht* hat, eine Seite mit Ressourcen und Zertifizierungen, um sie
  gezielt zu lernen (aus „habe ich nicht" wird ein Lern-Backlog).
- **Idee 2** — _(TODO: von Nathalie nachtragen)._

### Upgrade-Pfade

- **Term-Extraktion mit vortrainiertem Skill-NER** — die schwächste Stelle ist,
  dass das Seed-Wörterbuch nur *Bekanntes* findet. Vortrainierte Modelle für
  „skill extraction from job postings" (Feld: **SkillSpan**) fangen *neue*,
  unbekannte Skills im Freitext. Umsetzung als Feature-Flag `EXTRACTOR =
  "dictionary" | "jobbert"` in `config.py`: Default bleibt das schlanke
  Dictionary (für Demo & CI), optional der schwerere JobBERT-Pfad (`transformers`
  + PyTorch) für den „echten" Lauf mit vielen Anzeigen. Kandidaten (HF, vor
  Einsatz Lizenz/Downloads/Stand prüfen):
  - [`jjzha/jobbert_skill_extraction`](https://huggingface.co/jjzha/jobbert_skill_extraction) — Skill-Spans (Token-Classification), der Klassiker.
  - [`AchrafSoltani/jobbert-ner-haiku-v1`](https://huggingface.co/AchrafSoltani/jobbert-ner-haiku-v1) — 8 Entitäten inkl. `SKILL`, `CERT`, `EDUCATION` (Letztere speisen die Lern-/Zertifizierungs-Seite).
  - Diese sind **NER-Encoder**, keine Klassifikatoren → sie ersetzen nur den
    *extract*-Schritt; das *classify*-Bucketing bleibt bei Embeddings + Ankern.
  - Caveat: die meisten sind **englisch**. Für deutsche Anzeigen nach
    `ESCOXLM-R` / `jobBERT-de` (mehrsprachig) suchen.
- Alternativ leichter: spaCy `noun_chunks` für neue Begriffe (ohne PyTorch).
- ESCO-Taxonomie der EU als großes Seed-Wörterbuch laden (+ ESCO-Mapping zur
  Normalisierung/Aliasing extrahierter Skills).
- Anker-Klassifikation: `MEMBERSHIP_MARGIN` justieren (größer = mehr
  Mehrfach-Kanten); Hand-Gloss in `seed_skills.py` für hartnäckige Grenzfälle
  (z.B. `seaborn` → Data Science).
- dbt (`dbt-duckdb`) als `raw → staging → marts`-Layer mit Tests.
- Rohdaten als Parquet versionieren statt der binären DuckDB-Datei.
- Embedding-Fine-tuning aus den Editor-Labels (siehe Design-Entscheidungen).

## Roadmap (Build-Reihenfolge)

- [x] Statisches Gerüst: Hero, About, Projekt-Grid + Tag-Filter aus JSON
- [x] Interessen, Sprachen, Testimonials, Booking-Sektion
- [x] Cytoscape-Skill-Netzwerk mit Drill-down (Oberbegriff → Skill → Sub-Skill → Projekt),
      Hierarchie in `src/data/skills.json`, Blätter matchen auf Projekt-Tags
- [x] Skill-Pipeline: ingest → extract → classify → export (`pipeline/`, GitHub Actions)
- [x] Kontext-Embeddings (Marken-Begriffe), Mehrfach-Zuordnung (`also`),
      Libraries + `lang`-Tags im Wörterbuch
- [ ] `market_skills.json` im SkillGraph rendern (Markt-Netz + eigene Skills
      überlagern; `also`-Kanten zu mehreren Kategorien zeichnen)
- [ ] Gamifizierter Skill-Editor (localStorage + Export)
- [ ] Skills ↔ CV: aus dem Kategorie-Knoten zum passenden CV verlinken
- [ ] Druck-gestylte CV-Routen (`/cv/...`), pro Tag gefiltert
- [ ] Automatische CV-PDFs via Playwright in der GitHub Action
- [ ] Mehrsprachigkeit (DE + EN/FR, evtl. UK in Interessen)
