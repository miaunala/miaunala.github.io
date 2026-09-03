"""Seed-Woerterbuch fuer die Term-Extraktion.

Bewusst klein und handgepflegt gehalten. In echt wuerde man hier die
ESCO-Taxonomie der EU laden (tausende Skills, gratis) -- die Struktur bleibt
gleich: canonical -> Liste von Schreibweisen/Aliasen.

Die Zuordnung zu einer Kategorie passiert NICHT hier, sondern spaeter ueber
Embeddings (classify.py). Dieses Woerterbuch dient nur dem Wiedererkennen
bekannter Begriffe im Freitext.
"""
from __future__ import annotations

# canonical -> Aliase (werden als \b<alias>\b, case-insensitive, gesucht)
SEED_SKILLS: dict[str, list[str]] = {
    "Airflow": ["airflow", "apache airflow", "mwaa"],
    "dbt": ["dbt", "data build tool"],
    "SQL": ["sql"],
    "Spark": ["spark", "apache spark", "pyspark"],
    "Kafka": ["kafka", "apache kafka"],
    "Snowflake": ["snowflake"],
    "Databricks": ["databricks"],
    "BigQuery": ["bigquery", "big query"],
    "Redshift": ["redshift"],
    "Airbyte": ["airbyte"],
    "Fivetran": ["fivetran"],
    "ETL": ["etl"],
    "ELT": ["elt"],
    "Data Modeling": ["data modeling", "data modelling", "dimensional modeling"],
    "Data Warehousing": ["data warehouse", "data warehousing", "dwh"],
    "Docker": ["docker", "containerization", "containerisation"],
    "Kubernetes": ["kubernetes", "k8s"],
    "Terraform": ["terraform"],
    "AWS": ["aws", "amazon web services"],
    "GCP": ["gcp", "google cloud"],
    "Azure": ["azure"],
    "Python": ["python"],
    "pandas": ["pandas"],
    "NumPy": ["numpy"],
    "scikit-learn": ["scikit-learn", "sklearn", "scikit learn"],
    "XGBoost": ["xgboost"],
    "PyTorch": ["pytorch"],
    "TensorFlow": ["tensorflow"],
    "Regression": ["regression"],
    "Classification": ["classification"],
    "Time Series Forecasting": ["time series", "forecasting", "time-series"],
    "A/B Testing": ["a/b testing", "ab testing", "experimentation"],
    "Statistics": ["statistics", "statistical analysis"],
    "Data Visualization": ["data visualization", "data visualisation", "dashboards"],
    "Power BI": ["power bi", "powerbi"],
    "Tableau": ["tableau"],
    "Hugging Face": ["hugging face", "huggingface", "transformers"],
    "LLM": ["llm", "large language model", "gpt"],
    "Embeddings": ["embeddings", "embedding"],
    "Named Entity Recognition": ["named entity recognition", "ner"],
    "Text Classification": ["text classification"],
    "spaCy": ["spacy"],
    "Zero-shot Classification": ["zero-shot", "zero shot"],
    "MLflow": ["mlflow"],
    "Feature Engineering": ["feature engineering"],
    "Deep Learning": ["deep learning", "neural network", "neural networks"],
    "Git": ["git", "version control"],
    "CI/CD": ["ci/cd", "cicd", "continuous integration"],
    # --- Python-Libraries ---------------------------------------------------
    "matplotlib": ["matplotlib"],
    "seaborn": ["seaborn"],
    "Plotly": ["plotly"],
    "SciPy": ["scipy"],
    "statsmodels": ["statsmodels"],
    "Polars": ["polars"],
    "Dask": ["dask"],
    "Ray": ["ray.io", "ray tune"],
    "LightGBM": ["lightgbm", "light gbm"],
    "CatBoost": ["catboost"],
    "Keras": ["keras"],
    "NLTK": ["nltk"],
    "Gensim": ["gensim"],
    "LangChain": ["langchain"],
    "Optuna": ["optuna"],
    "SQLAlchemy": ["sqlalchemy"],
    "FastAPI": ["fastapi"],
    "Flask": ["flask"],
    "Streamlit": ["streamlit"],
    "Pydantic": ["pydantic"],
    "Great Expectations": ["great expectations"],
    "Pandera": ["pandera"],
    "Prefect": ["prefect"],
    "Dagster": ["dagster"],
    "Selenium": ["selenium"],
    "Beautiful Soup": ["beautifulsoup", "beautiful soup"],
    # --- R-Libraries --------------------------------------------------------
    "tidyverse": ["tidyverse"],
    "ggplot2": ["ggplot2", "ggplot"],
    "dplyr": ["dplyr"],
    "caret": ["caret"],
    "Shiny": ["r shiny", "shiny app"],
    # --- Sprachen & Werkzeuge (Belege kommen v.a. aus GitHub, s. github_skills.py).
    # Aliase bewusst eng: "R" als Einzelbuchstabe wuerde ueberall falsch matchen.
    "R": ["r programming", "rstudio", "r markdown", "rmarkdown"],
    "Java": ["java"],
    "Stata": ["stata"],
    "TypeScript": ["typescript"],
    "JavaScript": ["javascript"],
    "Jupyter": ["jupyter", "jupyter notebook"],
    "LaTeX": ["latex"],
    "Web Scraping": ["web scraping", "webscraping", "web crawler"],
    "Topic Modeling": ["topic modeling", "topic modelling"],
    "Sentiment Analysis": ["sentiment analysis"],
    "Hypothesis Testing": ["hypothesis testing", "significance testing"],
    "Data Cleaning": ["data cleaning", "data wrangling"],
}

# Zuordnung Library -> Programmiersprache. Traegt die Sprach-Info in die Daten,
# damit spaeter eine "Sprache -> Library"-Gruppierung moeglich ist, ohne die
# Anker-Kategorien (DE/DS/ML/NLP) zu ersetzen.
SEED_LANGUAGE: dict[str, str] = {
    lib: "Python" for lib in [
        "pandas", "NumPy", "scikit-learn", "XGBoost", "PyTorch", "TensorFlow",
        "matplotlib", "seaborn", "Plotly", "SciPy", "statsmodels", "Polars",
        "Dask", "Ray", "LightGBM", "CatBoost", "Keras", "NLTK", "Gensim",
        "LangChain", "Optuna", "SQLAlchemy", "FastAPI", "Flask", "Streamlit",
        "Pydantic", "Great Expectations", "Pandera", "Prefect", "Dagster",
        "Selenium", "Beautiful Soup", "spaCy", "Hugging Face",
    ]
}
SEED_LANGUAGE.update({lib: "R" for lib in ["tidyverse", "ggplot2", "dplyr", "caret", "Shiny"]})

# Optionaler Hand-Gloss: nur fuer Begriffe, die im Freitext zu duenn vorkommen,
# um sich per Kontext selbst zu erklaeren. Die Klassifikation nutzt primaer den
# echten Kontext aus den Anzeigen (skill_contexts) und faellt hierauf zurueck.
# Leer lassen ist ok -- dann zaehlt nur der Kontext.
SEED_GLOSS: dict[str, str] = {
    "Snowflake": "cloud data warehouse platform",
    "BigQuery": "google cloud data warehouse",
    "Redshift": "aws cloud data warehouse",
    "Fivetran": "managed elt data ingestion tool",
    "Airbyte": "open source elt data ingestion tool",
    "Databricks": "unified data engineering and analytics platform",
    "Power BI": "business intelligence and data visualization tool",
    "Tableau": "business intelligence and data visualization tool",
}
