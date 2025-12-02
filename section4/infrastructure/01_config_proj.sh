#!/bin/bash
set -e

source "$(dirname "$0")/../.env"

#priors:
# Project created with associated billing
# run on bash -> gcloud auth login

gcloud config set project "${PROJECT_ID}"
# 2. Enable APIs
gcloud services enable \
  aiplatform.googleapis.com \
  iam.googleapis.com \
  storage.googleapis.com \
  containerregistry.googleapis.com \
  cloudkms.googleapis.com \
  cloudbuild.googleapis.com \
  cloudresourcemanager.googleapis.com \
  ml.googleapis.com