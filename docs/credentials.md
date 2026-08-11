# Credential Inventory

Tracks every system holding or referencing the GCP service account key for this project.

## pipeline-runner service account

- Purpose: local Prefect and dbt Core development
- Key created: July 22, 2026
- Role granted: BigQuery Admin

### Systems holding or referencing a copy

| System | Purpose | Date added |
|---|---|---|
| Local machine — gcp-key.json | The key file itself, in the project root (gitignored) | July 22, 2026 |
| ~/.zshrc — GOOGLE_APPLICATION_CREDENTIALS export | Points the Prefect flow's BigQuery client at the key | Aug 2026 |
| ~/.dbt/profiles.yml — keyfile path | Points dbt Core at the key for its BigQuery connection | July 2026 |

### Notes

- Execution is local (Prefect `serve`), so the key never leaves this machine. Prefect Cloud stores only run metadata and logs, not credentials.
- To rotate: replace gcp-key.json, and no other locations need editing since both references point at that one file path. Confirm with a test run afterward.