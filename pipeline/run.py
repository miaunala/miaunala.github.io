"""Orchestriert die ganze Pipeline in Reihenfolge.

Genau dieser Ablauf laeuft woechentlich in GitHub Actions. Der Airflow-DAG in
dags/skill_pipeline.py ruft dieselben Funktionen als einzelne Tasks auf.

    python pipeline/run.py
"""
from __future__ import annotations

from classify import classify
from export import export
from extract import extract
from ingest import ingest


def main() -> None:
    print("=== Skill-Pipeline ===")
    ingest()
    extract()
    classify()
    export()
    print("=== fertig ===")


if __name__ == "__main__":
    main()
