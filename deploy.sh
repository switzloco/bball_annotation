#!/bin/bash

# Basketball Video Agent - Cloud Run Deployment Script
# Usage: ./deploy.sh [PROJECT_ID] [REGION]

set -e

# Configuration
PROJECT_ID=${1:-$(gcloud config get-value project)}
REGION=${2:-us-central1}
SERVICE_NAME="bball-agent"
IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

echo "🏀 Basketball Video Agent - Deployment"
echo "======================================"
echo "Project: ${PROJECT_ID}"
echo "Region: ${REGION}"
echo "Service: ${SERVICE_NAME}"
echo ""

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo "❌ Error: gcloud CLI not found. Please install it first."
    exit 1
fi

# Check if project ID is set
if [ -z "$PROJECT_ID" ]; then
    echo "❌ Error: GCP Project ID not set."
    echo "Usage: ./deploy.sh [PROJECT_ID] [REGION]"
    exit 1
fi

# Load environment variables
if [ -f .env ]; then
    echo "📋 Loading environment variables from .env..."
    export $(cat .env | grep -v '^#' | xargs)
else
    echo "⚠️  Warning: .env file not found"
fi

# Enable required APIs
echo "🔧 Enabling required Google Cloud APIs..."
gcloud services enable \
    cloudbuild.googleapis.com \
    run.googleapis.com \
    aiplatform.googleapis.com \
    storage.googleapis.com \
    --project=${PROJECT_ID}

# Build and push the container
echo "🐳 Building container image..."
gcloud builds submit \
    --tag ${IMAGE_NAME} \
    --project=${PROJECT_ID} \
    .

echo "✅ Container built successfully: ${IMAGE_NAME}"

# Deploy to Cloud Run
echo "🚀 Deploying to Cloud Run..."
gcloud run deploy ${SERVICE_NAME} \
    --image ${IMAGE_NAME} \
    --platform managed \
    --region ${REGION} \
    --project ${PROJECT_ID} \
    --allow-unauthenticated \
    --memory 4Gi \
    --cpu 2 \
    --timeout 3600 \
    --max-instances 10 \
    --set-env-vars "GCP_PROJECT_ID=${GCP_PROJECT_ID:-$PROJECT_ID},GCP_BUCKET_NAME=${GCP_BUCKET_NAME:-bball_project},GCP_LOCATION=${GCP_LOCATION:-$REGION}"

echo ""
echo "🎉 Deployment complete!"
echo ""
echo "Your Basketball Video Agent is now live at:"
gcloud run services describe ${SERVICE_NAME} \
    --platform managed \
    --region ${REGION} \
    --project ${PROJECT_ID} \
    --format 'value(status.url)'

echo ""
echo "📊 View logs:"
echo "gcloud run services logs read ${SERVICE_NAME} --region ${REGION} --project ${PROJECT_ID}"
