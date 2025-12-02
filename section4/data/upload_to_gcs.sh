#!/bin/bash
set -e

# This script is a simple local uploader.
# In production, data typically streams in and ingestion pipelines are
# triggered by schedulers or event-driven systems. 
#Examples:
#  - Cloud Scheduler (cron) -> HTTP endpoint / Cloud Function to kick off a job
#  - Pub/Sub messages for streaming ingestion (e.g., IoT, Kafka -> Pub/Sub)
#  - Cloud Composer (Airflow) to orchestrate complex pipelines on a schedule
#  - Dataflow Streaming jobs or Dataflow Flex Templates launched from an orchestrator


PROJECT_ID=$(gcloud config get-value project)
BUCKET_NAME="secure-ml-data-${PROJECT_ID}"
DATA_GCS="gs://${BUCKET_NAME}/data"
SCHEMA_GCS="gs://${BUCKET_NAME}/schema"

echo "Cleaning up old data in Bucket: ${BUCKET_NAME}..."
gsutil -m rm -r "${DATA_GCS}/**" 2>/dev/null || true

echo "Uploading assets to Bucket: ${BUCKET_NAME}..."
echo "Note: this is a sample upload. In production, use scheduler or event-driven triggers (Cloud Scheduler, Pub/Sub, Cloud Functions, Composer, Dataflow, etc.) to drive ingestion."

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

# 1. Training Data
gsutil cp "$SCRIPT_DIR/data/kdd-with-columns.csv" "${DATA_GCS}/data/kdd-with-columns.csv"

# 2. Ingest Data (Simulation)
gsutil cp "$SCRIPT_DIR/ingest/good/good_data.csv" "${DATA_GCS}/ingest/good/good_data.csv"
gsutil cp "$SCRIPT_DIR/ingest/bad/bad_data.csv" "${DATA_GCS}/ingest/bad/bad_data.csv"

# 3. Schema
gsutil cp "$SCRIPT_DIR/schema/schema.pbtxt" "${SCHEMA_GCS}/schema.pbtxt"
