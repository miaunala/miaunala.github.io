# miaunala.github.io

Persönliche Portfolio-Website von Nathalie Guibert (Nathi). Statisch, gebaut mit
[Astro](https://astro.build), gehostet auf GitHub Pages.

## Kernprinzip: eine Datenquelle speist alles

Die Dateien in `src/data/` sind die einzige Wahrheit:

- **`profile.json`** — Person, Bio, Kontakt, Engagement, Veranstaltungen.
- **`projects.json`** — alle Projekte mit nach Ebenen getrennten Tags
  (`method` / `domain` / `tool`).
- **`skills.json`** — *eigenes* Skill-Netz (handgepflegt): „was Nathalie kann".
- **`market_skills.json`** — das gerenderte Netz, von der Pipeline generiert
  (siehe [Skill-Pipeline](#skill-pipeline-pipeline)): Marktnachfrage **plus** die
  eigenen Skills samt Belegen.

Aus diesen Daten entstehen Projekt-Karten, der Tag-Filter, das Skill-Netzwerk und
(später) die tag-gefilterten CVs. Ein neues Projekt = ein Eintrag in
`projects.json`.

## Inhalte pflegen — welche Datei wofür

Alles Redaktionelle liegt in `src/data/`. **Diese fünf Dateien bearbeitest du
von Hand:**

| Datei | Inhalt |
|---|---|
| `profile.json` | `name`, `photo`, `headerImage`, `tagline`, `status`, `bio`, `current`, `links`, `languages`, `interests`, `engagement`, `events`, `booking`, `services` |
| `projects.json` | Liste je Projekt: `id`, `title`, `summary`, `repo`, `year`, `highlight`, `tags` (`method`/`domain`/`tool`), `cv_bullets` |
| `skills.json` | selbst deklarierte Skills (Kategorie → Skill → Sub-Skill) |
| `credentials.json` | Zertifikate: `title`, `issuer`, `year`, `url`, `file`, `skills` |
| `testimonials.json` | `quote`, `role`, `industry`, `year`, `project` |

⚠️ **`market_skills.json` niemals von Hand ändern** — die Datei wird bei jedem
Pipeline-Lauf neu erzeugt und überschrieben.

**Bilder und Dateien** kommen nach `public/` und werden 1:1 ausgeliefert:

```
public/portrait.svg          ->  in profile.json als "/portrait.svg"
public/certificates/xy.pdf   ->  in credentials.json als "/certificates/xy.pdf"
```

Also: Datei in `public/` legen, im JSON **mit führendem Slash** referenzieren.

Die `tags` in `projects.json` verbinden Projekte mit dem Skill-Netz: steht dort
`"tool": ["pandas"]`, taucht das Projekt beim Klick auf den pandas-Punkt auf.

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
pipeline/       Skill-Pipeline (ingest → extract → evidence → credentials → llm → classify → export), DuckDB
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

**Ein Netz, zwei Quellen.** Die Seite zeigt *einen* Graphen; die eigenen Skills
sind darin hervorgehoben:

| | Markt (Anzeigen) | Eigene Skills |
|---|---|---|
| Quelle | Job-API / Beispiel-Anzeigen | `skills.json` + Belege aus eigenen GitHub-Repos |
| Rolle im Graph | blasse Punkte — „was der Markt verlangt" | kräftige Punkte — „was ich kann" |

Ein Skill gilt als „meiner" (`mine`), wenn er **deklariert** *oder* **belegt**
ist:

- **deklariert** — steht in `skills.json` (z.B. `SQL`, `dbt`: ich sage, ich kann es)
- **belegt** — in einem eigenen Repo nachweisbar (siehe Schritt *evidence*)

Beides zusammen ergibt die kräftigen Punkte im Graph; alles andere bleibt blass.

`skills.json` wird von der Pipeline **mit eingelesen** (`own_skills.py`), damit
eigene Skills auch dann als Punkt erscheinen, wenn der Markt sie gerade nicht
nennt — mit echten Embedding-Koordinaten statt willkürlicher Platzierung. Als
Kontext dient ihre Herkunft aus der eigenen Hierarchie („DAGs: Airflow, Data
Engineering"). Ergebnis: `market_skills.json` enthält alles, jeder Skill mit
`mine`-Flag.

### Ablauf (`pipeline/run.py`)

```
ingest → extract → evidence → credentials → llm → classify → export
```

1. **ingest** (`ingest.py`) — Job-Anzeigen holen. Ohne `ADZUNA_*`-Key laufen die
   Beispiel-Anzeigen in `sample_data/`; mit Key die echte
   [Adzuna-API](https://developer.adzuna.com/) (Gratis-Tier).
2. **extract** (`extract.py`) — Skills per Seed-Wörterbuch (`seed_skills.py`)
   aus dem Freitext ziehen, samt **Kontext-Satz** je Begriff; Wochen-Häufigkeit in
   DuckDB. Zusätzlich werden die **eigenen Skills** aus `skills.json` ergänzt
   (`own_skills.py`), damit sie im Graphen nicht fehlen.
2b. **evidence** (`github_skills.py`) — **Belege statt Behauptungen.** Liest die
   eigenen GitHub-Repos (`GITHUB_USER`) und weist Skills in vier Stärken nach:

   | Art | Quelle | Beispiel |
   |---|---|---|
   | `language` | GitHub-Sprachstatistik | Python, R, Java, Stata |
   | `file` | Dateiendungen im Repo-Baum | `.sql`, `.Rmd`, `.ipynb`, `.pbix` |
   | `dependency` | `requirements.txt`, `DESCRIPTION`, … | pandas, ggplot2 |
   | `code` | Dateien werden **geöffnet**: Imports + Logik | ggplot2, dplyr, spaCy, LangChain |
   | `readme` | README + Repo-Beschreibung | **Regression**, Sentiment Analysis |

   Der `readme`-Kanal ist der wichtigste: Methoden wie „Regression" sieht man
   keinem Dateinamen an, sie stehen im Text. Belegte Skills werden im Graph
   hervorgehoben und listen im Panel ihre Repos.

   **Inkrementell:** `repo_scan` merkt sich `pushed_at` je Repo — beim Wochenlauf
   werden nur Repos mit neuen Commits neu gelesen (zweiter Lauf: 0 API-Calls).
   Ändert sich die Erkennungslogik, erzwingt `DETECTOR_VERSION` einen Neu-Scan.

   **Nachvollziehbare Beleg-Arten:** `left_join()`/`group_by()` in R sind dplyr —
   bewusst nach SQL-Verben modelliert (`dbplyr` übersetzt es sogar nach SQL).
   Das zählt als Beleg für **SQL**, aber unter der eigenen Art `sql-logic`, im
   Panel ausgewiesen als „SQL-Logik (dplyr/pandas)". So bleibt sichtbar, worauf
   der Beleg beruht, statt echte `.sql`-Dateien vorzutäuschen. Dieselben Funde
   belegen zusätzlich **Data Modeling**.

   Das Portfolio-Repo selbst ist per `EXCLUDE_REPOS` ausgenommen — seine README
   *diskutiert* Skills als Thema und würde sonst Können vortäuschen. Forks
   ebenso (fremder Code belegt nichts). Ohne Token/Netz wird der Schritt
   übersprungen.

2c. **credentials** (`credentials.py`) — Zertifikate aus `credentials.json` als
   Beleg-Art `certificate`. Damit werden Skills belegbar, die man im Code nie
   sieht (Power BI, Excel, Cloud-Zertifizierungen).

2d. **llm** (`llm_evidence.py`) — *optional, gratis, lokal.* Zeigt einem lokalen
   Ollama-Modell (Apertus, sonst was installiert ist) **das bestehende Netz plus
   ein Repo** und fragt: welche Knoten deckt dieses Repo ab? Geschlossene Liste,
   also keine erfundenen Skills.

   **Zwei harte Schutzmechanismen**, weil ein LLM sonst munter Kubernetes, Kafka
   und Spark behauptet (im Test: 21 frei erfundene Skills):
   1. Das Modell muss ein **wörtliches Zitat** aus dem Repo-Text liefern; steht
      es dort nicht buchstäblich, wird der Fund verworfen (im Test: 26 von 41).
   2. Ein LLM-Fund allein macht einen Skill **nicht** zu „meinem" — er wird nur
      als `suggested` markiert und muss bestätigt werden.

   Ohne laufendes Ollama wird der Schritt übersprungen. Analysiert werden nur
   Repos mit neuen Commits (`llm_scan`).

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
   Kategorien der Mehrfach-Zuordnung), `lang` (Sprache einer Library) und `x`/`y`
   — 2D-Koordinaten aus einer **PCA der Embeddings**, mit denen die Markt-Ansicht
   die Skills als Scatter positioniert (Nähe = semantische Ähnlichkeit), gefärbt
   nach Cluster, mit Linien zum Cluster-Zentrum.

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
- **LLM liest die READMEs** — die nächste Stufe der Belege. Das
  Dictionary-Matching findet nur *benannte* Begriffe („Regression"). Ein LLM
  könnte aus „predicted permit approval times" auf *Time Series Forecasting*
  schließen, also **implizite** Skills erkennen und je Repo eine Begründung
  liefern („belegt, weil …"). Ein Aufruf pro Repo, nur bei Änderung —
  entsprechend günstig. Ergebnis als weitere `kind = "llm"`-Beleg-Art, damit
  nachvollziehbar bleibt, was Text-Match und was Modell-Schluss ist.
- Skills ohne Code-Spur (SQL, Power BI, Excel): entweder in `skills.json`
  deklarieren, oder eine Spur schaffen — `.sql`-Dateien, ein `.pbix` im Repo,
  oder die Nennung in einer README. Dann greift der Beleg-Mechanismus.
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
- [x] SkillGraph als **ein** Embedding-Scatter: Punkte an PCA-Koordinaten, nach
      Themenfeld gefärbt, Labels an allen Punkten, eigene Skills kräftig / Markt
      blass, gepunktete Linien zum Themenfeld, Hover-„Pop"
- [x] GitHub-Belege: Skills aus eigenen Repos nachweisen (Sprache, Dateien,
      Abhängigkeiten, README), Belege im Panel mit Repo-Links
- [ ] Gamifizierter Skill-Editor (localStorage + Export)
- [ ] Skills ↔ CV: aus dem Kategorie-Knoten zum passenden CV verlinken
- [ ] Druck-gestylte CV-Routen (`/cv/...`), pro Tag gefiltert
- [ ] Automatische CV-PDFs via Playwright in der GitHub Action
- [ ] Mehrsprachigkeit (DE + EN/FR, evtl. UK in Interessen)
