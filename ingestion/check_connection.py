"""Smoke test: can this machine authenticate to BigQuery?"""

from google.cloud import bigquery

client = bigquery.Client()
print(f"Connected to project: {client.project}")

print("Datasets:")
for ds in client.list_datasets():
    print(f"  {ds.dataset_id}")

result = client.query("SELECT 1 AS ok").result()
print(f"Test query returned: {list(result)[0].ok}")