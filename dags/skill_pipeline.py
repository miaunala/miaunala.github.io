"""Airflow-DAG der Skill-Pipeline (woechentlich).

Zeigt dieselbe Logik wie pipeline/run.py, aber als vier orchestrierte Tasks --
so, wie man es in einer echten Airflow-Umgebung fahren wuerde. In GitHub Actions
laeuft aus Kostengruenden run.py; dieser DAG ist die "Airflow im Portfolio"-
Variante und laesst sich ohne dauerhaften Server per

    airflow dags test skill_pipeline

durchspielen.

Damit die Imports aus pipeline/ funktionieren, muss das pipeline-Verzeichnis
im PYTHONPATH liegen (siehe README).
"""
from __future__ import annotations

import datetime as dt

from airflow.decorators import dag, task


@dag(
    dag_id="skill_pipeline",
    schedule="@weekly",
    start_date=dt.datetime(2026, 1, 1),
    catchup=False,
    tags=["skills", "portfolio"],
)
def skill_pipeline():
    @task
    def ingest_task() -> int:
        from ingest import ingest
        return ingest()

    @task
    def extract_task(_prev: int) -> int:
        from extract import extract
        return extract()

    @task
    def classify_task(_prev: int) -> None:
        from classify import classify
        classify()

    @task
    def export_task() -> None:
        from export import export
        export()

    ing = ingest_task()
    ext = extract_task(ing)
    cls = classify_task(ext)
    cls >> export_task()


skill_pipeline()
