#!/bin/bash

# Basketball Video Agent - Local Development Runner
# Usage: ./run_local.sh

set -e

echo "🏀 Basketball Video Agent - Local Development"
echo "=============================================="
echo ""

# Check if .env file exists
if [ ! -f .env ]; then
    echo "⚠️  .env file not found. Creating from .env.example..."
    if [ -f .env.example ]; then
        cp .env.example .env
        echo "✅ Created .env file. Please edit it with your GCP credentials."
        echo ""
        read -p "Press Enter after updating .env file..."
    else
        echo "❌ Error: .env.example not found"
        exit 1
    fi
fi

# Load environment variables
echo "📋 Loading environment variables..."
export $(cat .env | grep -v '^#' | xargs)

# Check required environment variables
if [ -z "$GCP_PROJECT_ID" ]; then
    echo "❌ Error: GCP_PROJECT_ID not set in .env"
    exit 1
fi

if [ -z "$GCP_BUCKET_NAME" ]; then
    echo "❌ Error: GCP_BUCKET_NAME not set in .env"
    exit 1
fi

echo "✅ Environment configured"
echo "   Project: ${GCP_PROJECT_ID}"
echo "   Bucket: ${GCP_BUCKET_NAME}"
echo "   Location: ${GCP_LOCATION:-us-central1}"
echo ""

# Check if uv is installed
if command -v uv &> /dev/null; then
    echo "🚀 Using uv for package management..."

    # Check if dependencies are installed
    if ! uv pip list | grep -q streamlit; then
        echo "📦 Installing dependencies with uv..."
        uv pip install -r pyproject.toml
    fi
else
    echo "⚠️  uv not found. Using pip..."

    # Check if dependencies are installed
    if ! pip list | grep -q streamlit; then
        echo "📦 Installing dependencies with pip..."
        pip install -r requirements.txt
    fi
fi

echo ""
echo "🎬 Starting Streamlit app..."
echo "   URL: http://localhost:8501"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Run Streamlit
streamlit run app.py
