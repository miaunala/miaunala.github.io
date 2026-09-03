"""Orchestriert die ganze Pipeline in Reihenfolge.

Genau dieser Ablauf laeuft woechentlich in GitHub Actions. Der Airflow-DAG in
dags/skill_pipeline.py ruft dieselben Funktionen als einzelne Tasks auf.

    python pipeline/run.py
"""
from __future__ import annotations

from classify import classify
from credentials import store as store_credentials
from duolingo import duolingo
from export import export
from llm_evidence import llm_evidence
from extract import extract
from github_skills import evidence
from ingest import ingest


def main() -> None:
    print("=== Skill-Pipeline ===")
    ingest()
    extract()
    evidence()             # Belege aus den eigenen GitHub-Repos
    store_credentials()    # Belege aus Zertifikaten
    llm_evidence()         # implizite Skills per lokalem LLM (optional)
    duolingo()             # Streak fuer die Sprachen-Karte (optional)
    classify()
    export()
    print("=== fertig ===")


if __name__ == "__main__":
    main()
