#!/bin/bash
set -e

source "$(dirname "$0")/../.env"

SA_NAME="${SERVICE_ACCOUNT_NAME:-secure-ml-pipeline-sa}"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
PROJECT_NUMBER=$(gcloud projects describe "${PROJECT_ID}" --format="value(projectNumber)")
STORAGE_AGENT="service-${PROJECT_NUMBER}@gs-project-accounts.iam.gserviceaccount.com"

echo "Running for Project: ${PROJECT_ID}"

gcloud projects remove-iam-policy-binding "${PROJECT_ID}" \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/storage.admin"

# Create KMS Keyring & Key
gcloud kms keyrings create ${KMS_KEY_RING} --location ${LOCATION} 2>/dev/null || echo "KeyRing exists."
gcloud kms keys create ${KMS_KEY} --location ${LOCATION} --keyring ${KMS_KEY_RING} --purpose=encryption 2>/dev/null || echo "Key exists."

# Create Bucket
gsutil mb -p $PROJECT_ID -l $LOCATION gs://${BUCKET_NAME} 2>/dev/null || echo "Bucket exists."

# Create Service Account
gcloud iam service-accounts create ${SA_NAME} --display-name="Secure ML Pipeline Service Account" 2>/dev/null || echo "Service Account exists."

# Storage Agent Identity
gcloud beta services identity create --service=storage.googleapis.com --project=$PROJECT_ID 2>/dev/null || echo "Storage Agent already active."

# --- GRANT PERMISSIONS (MINIMIZED) ---

# Grant KMS access to Storage Service Agent (Required for CMEK)
gcloud kms keys add-iam-policy-binding ${KMS_KEY} --location=${LOCATION} --keyring=${KMS_KEY_RING} --member="serviceAccount:${STORAGE_AGENT}" --role="roles/cloudkms.cryptoKeyEncrypterDecrypter" > /dev/null

# Grant KMS access to Pipeline SA (Scoped to specific Key only)
gcloud kms keys add-iam-policy-binding ${KMS_KEY} --location=${LOCATION} --keyring=${KMS_KEY_RING} --member="serviceAccount:${SA_EMAIL}" --role="roles/cloudkms.cryptoKeyEncrypterDecrypter" > /dev/null

# Grant Storage access to Pipeline SA (Scoped to specific Bucket only)
gsutil iam ch serviceAccount:${SA_EMAIL}:objectUser gs://${BUCKET_NAME}

# Grant Vertex AI User (Project level required for job submission)
gcloud projects add-iam-policy-binding ${PROJECT_ID} --member="serviceAccount:${SA_EMAIL}" --role="roles/aiplatform.user" > /dev/null

# Grant legacy AI Platform (ml.googleapis.com) admin so Pusher can create models
gcloud projects add-iam-policy-binding ${PROJECT_ID} --member="serviceAccount:${SA_EMAIL}" --role="roles/ml.admin" > /dev/null

# Grant Cloud Build Builder (Reduced from Editor)
gcloud projects add-iam-policy-binding ${PROJECT_ID} --member="serviceAccount:${SA_EMAIL}" --role="roles/cloudbuild.builds.builder" > /dev/null

# --- ENFORCE CMEK ---
gsutil kms encryption -k projects/${PROJECT_ID}/locations/${LOCATION}/keyRings/${KMS_KEY_RING}/cryptoKeys/${KMS_KEY} gs://${BUCKET_NAME}