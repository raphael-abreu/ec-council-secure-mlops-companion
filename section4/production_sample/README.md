# Production-Ready Secure TFX Pattern

A reference layout for students to see how the Section 4 pipeline can run continuously in production without manual intervention.

## 1. Data Partitioning & Runtime Parameter
- Land every batch in an immutable prefix such as `gs://secure-ml-data-<proj>/data/processed/{YYYY}/{MM}/{DD}/{HHMM}/batch.csv`.
- Add a pipeline parameter in `runner.py`:
  ```python
  DATA_URI = tfx.dsl.PipelineParameter(name="data_uri", default_value=DATA_GCS)
  example_gen = tfx.components.CsvExampleGen(input_base=DATA_URI)
  ```
- Automation passes the specific folder that just arrived, keeping training reproducible.

## 2. Event-Driven Trigger (New Data)
1. **Cloud Storage Notification** on `data/processed/**` publishes to Pub/Sub.
2. **Cloud Function** subscribes, reads the new object path, normalizes it to the folder to process, and calls Vertex AI Pipelines:
   ```python
   from google.cloud import aiplatform

   def trigger_pipeline(event, context):
       data_uri = f"gs://{event['bucket']}/{event['name'].rsplit('/', 1)[0]}"
       aiplatform.init(project=PROJECT_ID, location=REGION)
       job = aiplatform.PipelineJob(
           display_name="governance-auto",
           template_path="gs://secure-ml-data-<proj>/artifacts/governance_pipeline.json",
           pipeline_root=ROOT,
           parameter_values={"data_uri": data_uri},
           enable_caching=True,
       )
       job.submit(service_account=PIPELINE_SA)
   ```
3. Pipelines now run automatically whenever fresh files arrive.

## 3. Scheduled Trigger (Nightly)
- **Cloud Scheduler → Cloud Run job** hits the same Vertex AI API once per day, passing yesterday's partition.
- Useful when retraining is periodic rather than event-driven.

## 4. CI/CD + Service-Account Impersonation
- Source of truth stays in Git. A `cloudbuild.yaml` (sample below) rebuilds the custom TFX image, uploads code/data helpers, and submits the pipeline while impersonating the runtime SA.
- No developer credentials are used in prod; Cloud Build owns deployment.

```yaml
# production_sample/cloudbuild.yaml
steps:
  - name: 'python:3.10'
    entrypoint: pip
    args: ['install', 'tfx==1.15.0', 'google-cloud-aiplatform']

  - name: 'gcr.io/cloud-builders/gcloud'
    args: ['builds', 'submit', '--tag', 'gcr.io/$PROJECT_ID/secure-tfx:latest', '.']

  - name: 'python:3.10'
    entrypoint: python
    args: ['runner.py']
    env:
      - 'PROJECT_ID=$PROJECT_ID'
      - 'IMAGE_URI=gcr.io/$PROJECT_ID/secure-tfx:latest'
    serviceAccount: 'projects/$PROJECT_ID/serviceAccounts/secure-ml-pipeline-sa@$PROJECT_ID.iam.gserviceaccount.com'
```

Run it from repo root after committing any changes:
```bash
gcloud builds submit --config production_sample/cloudbuild.yaml .
```
Cloud Build uploads the entire workspace, executes the steps, and logs progress in Cloud Logging.

Grant Cloud Build the right to impersonate the runtime SA once:
```bash
gcloud iam service-accounts add-iam-policy-binding \
  secure-ml-pipeline-sa@$PROJECT_ID.iam.gserviceaccount.com \
  --member="serviceAccount:$PROJECT_NUMBER@cloudbuild.gserviceaccount.com" \
  --role="roles/iam.serviceAccountUser"
```

## 5. How Students Use This Folder
- **Step 1:** Read how data partitioning + parameters keep runs isolated.
- **Step 2:** Follow either the event-driven or scheduler workflow to wire auto triggers.
- **Step 3:** Adopt the Cloud Build config to deploy without local credentials.
- **Step 4:** Store the compiled JSON (`governance_pipeline.json`) in GCS so any automation-only client can trigger reruns via CLI or API without recompiling.

This end-to-end approach mirrors a realistic enterprise ML Ops setup, highlighting secure identity boundaries, continuous deployment, and hands-free retraining.
