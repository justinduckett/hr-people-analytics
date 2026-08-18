# Credential Inventory

Tracks every system holding or referencing credentials for this project.

## pipeline-runner service account (GCP)

- Purpose: BigQuery access for the Prefect flow and dbt Core
- Key created: July 22, 2026
- Role granted: BigQuery Admin

### Systems holding or referencing a copy

| System | Purpose | Date added |
|---|---|---|
| Local machine — gcp-key.json | The key file itself, in the project root (gitignored) | July 22, 2026 |
| ~/.zshrc — GOOGLE_APPLICATION_CREDENTIALS export | Points the local Prefect flow's BigQuery client at the key | Aug 2026 |
| ~/.dbt/profiles.yml — keyfile path | Original dbt profile, superseded by the in-project profile below | July 2026 |
| dbt/northline_hr/profiles.yml — env var reference | Reads the keyfile path from GOOGLE_APPLICATION_CREDENTIALS, so it works locally and in CI. Contains no credentials. | Aug 2026 |
| GitHub Actions secret — GCP_SA_KEY | A full copy of the key contents, written to a file at the start of each scheduled run | Aug 2026 |

## Prefect Cloud API key

- Purpose: lets the scheduled GitHub Actions run report flow state and logs to Prefect Cloud
- Created: Aug 2026

| System | Purpose | Date added |
|---|---|---|
| GitHub Actions secret — PREFECT_API_KEY | Authenticates CI runs to the Prefect Cloud workspace | Aug 2026 |
| Local machine — Prefect CLI profile | Created by `prefect cloud login`, stored in ~/.prefect | Aug 2026 |

(`PREFECT_API_URL` is also stored as a GitHub Actions secret. It identifies the workspace rather than authenticating, so it is not sensitive, but it is kept alongside the key for convenience.)

### Notes

- The service account key now exists in two places: the local file and the GitHub Actions secret. Rotating it means updating both. This is the exact situation that broke a previous project's pipeline, where three systems held a key and only two were updated.
- Prefect Cloud stores run metadata and logs only, never credentials. Execution happens either on the local machine or on a GitHub Actions runner, and the key is supplied by whichever environment is running.
- To rotate: create a new key in GCP, replace the local gcp-key.json, update the GCP_SA_KEY secret in GitHub, delete the old key in the GCP console, then confirm with both a local run and a manually triggered Actions run.