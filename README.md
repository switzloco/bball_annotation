# 🏀 Basketball Video Agent

[![GitHub](https://img.shields.io/badge/GitHub-Repository-blue?logo=github)](https://github.com/switzloco/bball_annotation)

An intelligent basketball video analysis system powered by **Gemini 2.5 Flash Lite**, **Google ADK (Agent Development Kit)**, and **Streamlit**.

**Repository**: https://github.com/switzloco/bball_annotation

## 🎯 Overview

This agent analyzes basketball game footage systematically, breaking down videos into 2-minute chunks to provide:

- **Play-by-play transcripts** - Detailed breakdown of every significant moment
- **Highlight reel identification** - Automatic detection of dunks, three-pointers, blocks, and steals
- **Strategic insights** - Analysis of offensive/defensive patterns and team performance
- **Interactive GUI** - Easy-to-use Streamlit interface for video selection and analysis

## 🏗️ Architecture

```
┌─────────────────┐
│   Streamlit UI  │ (app.py)
│  Model Selector │
│  File Upload    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│    CoachAI      │ (agent.py)
│  Agent (ADK)    │
│  - Video Tool   │
│  - Analysis     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Gemini 2.0     │
│  Flash Model    │
│  (Vertex AI)    │
└─────────────────┘
```

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- [uv](https://github.com/astral-sh/uv) package manager
- Google Cloud Project with Vertex AI API enabled
- GCS bucket for video storage

### Installation

1. **Clone the repository**

```bash
git clone https://github.com/switzloco/bball_annotation.git
cd bball_annotation
```

2. **Install dependencies using uv**

```bash
# Install uv if you haven't already
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install project dependencies
uv pip install -r pyproject.toml
```

3. **Configure environment variables**

```bash
cp .env.example .env
```

Edit `.env` with your GCP settings:

```env
GCP_PROJECT_ID=qwiklabs-gcp-04-b5171aa68bec
GCP_BUCKET_NAME=bball_project
GCP_LOCATION=us-central1
```

4. **Set up Google Cloud authentication**

```bash
# Option 1: Use gcloud CLI
gcloud auth application-default login

# Option 2: Use service account
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json
```

### Running Locally

```bash
streamlit run app.py
```

The app will be available at `http://localhost:8501`

## 🐳 Docker Deployment

### Build the image

```bash
docker build -t bball-agent .
```

### Run locally with Docker

```bash
docker run -p 8080:8080 \
  -e GCP_PROJECT_ID=qwiklabs-gcp-04-b5171aa68bec \
  -e GCP_BUCKET_NAME=bball_project \
  -v ~/.config/gcloud:/root/.config/gcloud \
  bball-agent
```

### Deploy to Google Cloud Run

```bash
# Build and push to Google Container Registry
gcloud builds submit --tag gcr.io/qwiklabs-gcp-04-b5171aa68bec/bball-agent

# Deploy to Cloud Run
gcloud run deploy bball-agent \
  --image gcr.io/qwiklabs-gcp-04-b5171aa68bec/bball-agent \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars GCP_PROJECT_ID=qwiklabs-gcp-04-b5171aa68bec,GCP_BUCKET_NAME=bball_project \
  --memory 4Gi \
  --timeout 3600
```

## 📖 Usage Guide

### Using the Web Interface

1. **Select a Model**
   - Choose from `gemini-2.5-flash-lite`, `gemini-2.0-flash-exp`, `gemini-1.5-pro`, or `gemini-1.5-flash`
   - Default: `gemini-2.5-flash-lite` (recommended)

2. **Provide Video Input**
   - **Option A**: Enter a GCS URI (e.g., `gs://bball_project/vids/GX010043.mp4`)
   - **Option B**: Upload a local video file (will be automatically uploaded to GCS)

3. **Configure Analysis Parameters**
   - **Video Duration**: Total length in seconds
   - **Chunk Size**: Segment length for analysis (default: 120s = 2 minutes)

4. **Run Analysis**
   - Click "Start Analysis"
   - Monitor real-time progress and logs
   - View comprehensive results:
     - Game summary
     - Segment-by-segment breakdown
     - Highlight moments
     - Performance statistics

### Using the Agent Programmatically

```python
from agent import create_coach_agent
import os

# Set environment variables
os.environ["GCP_PROJECT_ID"] = "qwiklabs-gcp-04-b5171aa68bec"
os.environ["GCP_LOCATION"] = "us-central1"

# Create agent
agent = create_coach_agent(model_name="gemini-2.5-flash-lite")

# Analyze video
result = agent.analyze_full_video(
    video_uri="gs://bball_project/vids/GX010043.mp4",
    duration_seconds=600,  # 10 minutes
    chunk_size=120  # 2-minute chunks
)

# Access results
print(result["game_summary"])
for segment in result["segment_analyses"]:
    print(f"Segment {segment['segment']}: {segment['analysis']}")
```

## 🧩 Project Structure

```
bball_annotation/
├── agent.py              # CoachAI agent implementation
├── app.py                # Streamlit web interface
├── pyproject.toml        # Project dependencies (uv)
├── Dockerfile            # Container image definition
├── .env.example          # Environment variables template
└── README.md             # This file
```

## 🔧 Configuration

### Environment Variables

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `GCP_PROJECT_ID` | Google Cloud Project ID | Yes | - |
| `GCP_BUCKET_NAME` | GCS bucket for videos | Yes | - |
| `GCP_LOCATION` | Vertex AI region | No | `us-central1` |
| `GOOGLE_APPLICATION_CREDENTIALS` | Service account key path | No | - |

### Model Options

- **gemini-2.5-flash-lite** (Recommended) - Latest, fastest, most efficient
- **gemini-2.0-flash-exp** - Experimental version with advanced features
- **gemini-1.5-pro** - More detailed analysis, slower
- **gemini-1.5-flash** - Faster, less detailed

## 📊 Features

### CoachAI Agent Capabilities

- **Systematic Video Analysis**: Breaks down videos into manageable chunks
- **Play-by-Play Generation**: Identifies and describes key plays
- **Highlight Detection**: Finds exciting moments (dunks, blocks, steals)
- **Strategic Insights**: Analyzes team patterns and performance
- **Interactive Chat**: Ask questions about specific plays or strategies

### Video Analysis Tool

The `analyze_video_segment` tool:
- Accepts GCS video URIs
- Processes specific time ranges
- Uses multimodal Gemini capabilities
- Returns structured analysis

## 🎨 Customization

### Modify Analysis Instructions

Edit the system instruction in `agent.py`:

```python
self.system_instruction = """Your custom instructions here..."""
```

### Adjust Chunk Size

Change the default chunk size in `app.py` or via the UI:

```python
chunk_size = 120  # seconds
```

### Add Custom Tools

Extend the `VideoAnalysisTool` class in `agent.py`:

```python
def custom_analysis_method(self, video_uri: str) -> str:
    # Your custom logic
    pass
```

## 🐛 Troubleshooting

### Common Issues

**Issue**: "Could not verify GCS file"
- **Solution**: Check that your GCS URI is correct and you have read permissions

**Issue**: "Missing required environment variables"
- **Solution**: Ensure `.env` file exists with `GCP_PROJECT_ID` and `GCP_BUCKET_NAME`

**Issue**: "Authentication error"
- **Solution**: Run `gcloud auth application-default login` or set `GOOGLE_APPLICATION_CREDENTIALS`

**Issue**: "Video analysis fails"
- **Solution**: Verify video is in supported format (MP4) and accessible in GCS

## 📝 Development

### Running with uv

```bash
# Sync dependencies
uv pip sync

# Add new dependency
uv pip install package-name

# Update dependencies
uv pip compile pyproject.toml
```

### Testing Locally

```bash
# Set test environment
export GCP_PROJECT_ID=test-project
export GCP_BUCKET_NAME=test-bucket

# Run Streamlit
streamlit run app.py
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## 📄 License

MIT License - see LICENSE file for details

## 🙏 Acknowledgments

- **Google ADK** - Agent Development Kit
- **Gemini 2.5 Flash Lite** - Multimodal AI model
- **Streamlit** - Web framework
- **uv** - Fast Python package installer

## 📧 Support

For issues or questions:
- Open an issue on GitHub
- Check the [Google ADK documentation](https://github.com/google/genai)
- Review [Vertex AI docs](https://cloud.google.com/vertex-ai/docs)

---

Built with ❤️ for basketball coaches and analysts
