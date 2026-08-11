"""Daily ingestion flow for the Northline HR pipeline.

Runs the source system generators for a given as-of date, then loads
both exports into the hr_raw dataset in BigQuery in parallel.

Usage:
    python ingestion/flow.py               # as of today
    python ingestion/flow.py 2026-08-15    # as of a chosen date
"""

import json
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

from google.cloud import bigquery
from prefect import flow, get_run_logger, task

PROJECT_ROOT = Path(__file__).resolve().parent.parent
GENERATORS_DIR = PROJECT_ROOT / "generators"
DATA_DIR = PROJECT_ROOT / "data"

RAW_DATASET = "hr_raw"
HRIS_TABLE = "peoplecore_employees"
ATS_TABLE = "talentflow_candidates"


@task(retries=2, retry_delay_seconds=30)
def generate_exports(as_of: str) -> None:
    """Run both source system generators, simulating the arrival of
    the nightly exports. Subprocess rather than import: the pipeline
    treats the generators as external systems it does not control."""
    logger = get_run_logger()
    for script in ["generate_hris.py", "generate_ats.py"]:
        logger.info(f"Running {script} as of {as_of}")
        subprocess.run(
            [sys.executable, script, as_of],
            cwd=GENERATORS_DIR,
            check=True,
        )


@task(retries=2, retry_delay_seconds=30)
def load_hris(as_of: str) -> int:
    """Load employees.csv into BigQuery, replacing the previous
    export. History is dbt's job, not the raw layer's."""
    logger = get_run_logger()
    client = bigquery.Client()
    table_id = f"{client.project}.{RAW_DATASET}.{HRIS_TABLE}"

    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.CSV,
        skip_leading_rows=1,
        autodetect=True,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
    )
    with open(DATA_DIR / "employees.csv", "rb") as f:
        job = client.load_table_from_file(f, table_id, job_config=job_config)
    job.result()  # blocks until the load finishes, raises on failure

    rows = client.get_table(table_id).num_rows
    logger.info(f"Loaded {rows} rows into {table_id}")
    return rows


@task(retries=2, retry_delay_seconds=30)
def load_ats(as_of: str) -> int:
    """Load candidates.json into BigQuery. BigQuery ingests
    newline-delimited JSON, not JSON arrays, so the file is converted
    on the way in. The nested applications stay nested: BigQuery
    stores them as a REPEATED RECORD column."""
    logger = get_run_logger()
    client = bigquery.Client()
    table_id = f"{client.project}.{RAW_DATASET}.{ATS_TABLE}"

    candidates = json.loads((DATA_DIR / "candidates.json").read_text())

    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
        autodetect=True,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
    )
    with tempfile.NamedTemporaryFile(mode="w", suffix=".ndjson") as tmp:
        for candidate in candidates:
            tmp.write(json.dumps(candidate) + "\n")
        tmp.flush()
        with open(tmp.name, "rb") as f:
            job = client.load_table_from_file(f, table_id, job_config=job_config)
        job.result()

    rows = client.get_table(table_id).num_rows
    logger.info(f"Loaded {rows} candidates into {table_id}")
    return rows

@task
def run_dbt() -> None:
    """Run the full dbt build: models, tests, seeds, and snapshots,
    in dependency order. No retries: a dbt failure means bad data or
    broken logic, and rerunning won't change either."""
    logger = get_run_logger()
    result = subprocess.run(
        ["dbt", "build"],
        cwd=PROJECT_ROOT / "dbt" / "northline_hr",
        capture_output=True,
        text=True,
    )
    logger.info(result.stdout)
    if result.returncode != 0:
        raise RuntimeError("dbt build failed; see log above for the failing step")

@flow(name="hr-daily-ingestion")
def hr_ingestion(as_of: str | None = None) -> None:
    """Generate the day's exports, then load both sources in
    parallel. The task graph: generate -> (load_hris, load_ats)."""
    if as_of is None:
        as_of = date.today().isoformat()

    generate_exports(as_of)

    hris_future = load_hris.submit(as_of)
    ats_future = load_ats.submit(as_of)
    hris_rows = hris_future.result()
    ats_rows = ats_future.result()

    run_dbt()

    logger = get_run_logger()
    logger.info(f"Ingestion complete for {as_of}: "
                f"{hris_rows} employment records, {ats_rows} candidates")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "serve":
        hr_ingestion.serve(name="hr-daily")
    else:
        hr_ingestion(sys.argv[1] if len(sys.argv) > 1 else None)