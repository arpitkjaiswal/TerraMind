# Synthetic field document pack

18 CSV documents: six each for the wheat, corn, and soybean demo fields.
Each field includes soil observations, crop establishment, input applications,
weather observations, irrigation events, and three years of yields (24 rows per field).
All measurements, dates, products, and field names are fictional examples.
Every CSV row carries SYNTHETIC_DEMO_NOT_REAL_FARM_DATA. These are not agronomic recommendations.

Open the local demo to see these records and their graph connections automatically.
In a signed-in workspace, Ingest & Review offers a sample pack selector and an
Import button. That action uploads six CSVs to the selected real field through the
normal authenticated ingestion flow. Duplicate content is deduplicated per field.
Samples remain labeled as synthetic. Processing requires the configured backend,
storage, worker, and model services. A saved record is not a verified agronomic claim.

Regenerate with python scripts/generate_sample_documents.py.
