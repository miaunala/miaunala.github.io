# miaunala.github.io

Persönliche Portfolio-Website von Nathalie Guibert (Nathi). Statisch, gebaut mit
[Astro](https://astro.build), gehostet auf GitHub Pages.

## Kernprinzip: eine Datenquelle speist alles

Die Dateien in `src/data/` sind die einzige Wahrheit:

- **`profile.json`** — Person, Bio, Kontakt, Engagement, Veranstaltungen.
- **`projects.json`** — alle Projekte mit nach Ebenen getrennten Tags
  (`method` / `domain` / `tool`).

Aus diesen Daten entstehen Projekt-Karten, der Tag-Filter und (später) das
Skill-Netzwerk sowie die tag-gefilterten CVs. Ein neues Projekt = ein Eintrag in
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
  data/         profile.json, projects.json  (einzige Datenquelle)
  layouts/      Layout.astro                  (<head>, Fonts, Grundgerüst)
  components/   Header, Hero, About, ProjectGrid, ProjectCard, CvSection, Footer
  pages/        index.astro                   (setzt die Startseite zusammen)
  styles/       global.css                    (Design-Tokens, hell/dunkel)
```

## Deployment

`.github/workflows/deploy.yml` baut bei jedem Push auf `main` und deployt nach
GitHub Pages. **Einmalig einstellen:** GitHub → Repo → *Settings → Pages →
Build and deployment → Source = "GitHub Actions"*.

## Roadmap (Build-Reihenfolge)

- [x] Statisches Gerüst: Hero, About, Projekt-Grid + Tag-Filter aus JSON
- [x] Interessen, Sprachen, Testimonials, Booking-Sektion
- [x] Cytoscape-Skill-Netzwerk mit Drill-down (Oberbegriff → Skill → Sub-Skill → Projekt),
      Hierarchie in `src/data/skills.json`, Blätter matchen auf Projekt-Tags
- [ ] Skills ↔ CV: aus dem Kategorie-Knoten zum passenden CV verlinken
- [ ] Druck-gestylte CV-Routen (`/cv/...`), pro Tag gefiltert
- [ ] Automatische CV-PDFs via Playwright in der GitHub Action
- [ ] Mehrsprachigkeit (DE + EN/FR, evtl. UK in Interessen)
