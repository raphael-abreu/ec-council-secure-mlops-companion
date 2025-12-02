#!/bin/bash
set -e

# Ensure we are in the project root (parent of infrastructure)
cd "$(dirname "$0")/.."
source .env

IMAGE_URI="${IMAGE_URI:-gcr.io/${PROJECT_ID}/secure-tfx:latest}"

echo "Building image ${IMAGE_URI} from $(pwd)..."
gcloud builds submit --tag "${IMAGE_URI}" .