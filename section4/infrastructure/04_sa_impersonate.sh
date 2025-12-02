#!/bin/bash
set -e

source "$(dirname "$0")/../.env"

# De-impersonate at the beginning
gcloud config unset auth/impersonate_service_account 2>/dev/null || true

SA_NAME="${SERVICE_ACCOUNT_NAME:-secure-ml-pipeline-sa}"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
USER_EMAIL=$(gcloud config get-value account)

# --- 2. GRANT PERMISSION ---
# Allow the USER to create tokens (for local dev/impersonation)
gcloud iam service-accounts add-iam-policy-binding ${SA_EMAIL} \
    --member="user:${USER_EMAIL}" \
    --role="roles/iam.serviceAccountTokenCreator" > /dev/null

# Allow the SA to "act as" itself (Required for the SA to submit jobs that run as itself)
gcloud iam service-accounts add-iam-policy-binding ${SA_EMAIL} \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/iam.serviceAccountUser" > /dev/null

# --- 3. SAVE KEY AND SET ENV ---
KEY_FILE="$(pwd)/secure-ml-pipeline-sa.json"
gcloud iam service-accounts keys create "${KEY_FILE}" \
    --iam-account="${SA_EMAIL}"

export GOOGLE_APPLICATION_CREDENTIALS="${KEY_FILE}"
echo "Key saved to ${KEY_FILE}"
echo "GOOGLE_APPLICATION_CREDENTIALS=${GOOGLE_APPLICATION_CREDENTIALS}"