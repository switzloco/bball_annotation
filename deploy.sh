#!/bin/bash

# Exit on error
set -e

# Hardcoded for your current session
PROJECT_ID="qwiklabs-gcp-04-b5171aa68bec"
REGION="us-central1"
SERVICE_NAME="bball-agent"

echo "🏀 Deploying $SERVICE_NAME to Cloud Run (Safe Mode)..."

# Enable APIs (Just in case)
gcloud services enable run.googleapis.com cloudbuild.googleapis.com aiplatform.googleapis.com --project $PROJECT_ID

# Deploy from source with STRICT QUOTA LIMITS
# We limit max-instances to 4 to stay under the 16 CPU limit
# min-instances 1 keeps service warm (no cold starts)
gcloud run deploy $SERVICE_NAME \
  --source . \
  --project $PROJECT_ID \
  --region $REGION \
  --allow-unauthenticated \
  --min-instances 1 \
  --max-instances 4 \
  --memory 2Gi \
  --cpu 1 \
  --set-env-vars GCP_PROJECT_ID=$PROJECT_ID,GCP_REGION=$REGION,GCP_BUCKET_NAME=bball_project

echo "✅ Deployment complete! Check the URL above."
