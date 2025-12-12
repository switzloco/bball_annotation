# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A sports video analysis system that uses Google's Gemini AI models to analyze basketball and ultimate frisbee game footage. Videos are processed in configurable chunks with real-time streaming analysis via a Streamlit web interface.

## Development Commands

```bash
# Run the app locally (handles env setup automatically)
./run_local.sh

# Or run directly with Streamlit
streamlit run app.py

# Install dependencies with uv (preferred)
uv pip install -r pyproject.toml

# Install dependencies with pip (fallback)
pip install -r requirements.txt
```

**Environment Setup**: Copy `.env.example` to `.env` and configure GCP credentials. The app requires `GCP_PROJECT_ID` and `GCP_BUCKET_NAME`.

## Architecture

### Two-File Core Design
- **`agent.py`**: All AI/analysis logic. Contains `BaseSportAgent` (abstract base), `BasketballAgent`, `UltimateAgent`, and `VideoAnalysisTool` classes
- **`app.py`**: Streamlit UI. Handles video input (GCS/YouTube/upload), progress tracking, and result display

### Sport Agent Pattern
`BaseSportAgent` provides shared infrastructure (video duration detection, streaming analysis, segment classification). Sport-specific subclasses implement:
- `get_system_instruction()` - AI persona prompt
- `get_analysis_prompt()` - Per-segment analysis prompt
- `parse_events()` - Extract structured events from text (regex-based)
- `apply_classification_heuristic()` - GAME vs WARMUP logic based on event frequency
- `get_compilation_prompt()` - Final summary generation

Factory function: `create_coach_agent(model_name, sport)` returns the appropriate agent.

### Two-Pass High Fidelity Mode
When enabled (`high_fidelity=True`):
1. **Pass 1 (Temporal Filter)**: Native video analysis to identify active segments
2. **Pass 2 (Tiled Vision)**: For segments above activity threshold, extracts frames, splits into vertical tiles (3 tiles with 20% overlap), sends as image sequence to avoid token compression visual erasure

### Event Parsing Format
Basketball shots: `SHOT: [MM:SS] - [Player] - [type] - [MADE/MISSED]`
Ultimate events: `GOAL:`, `CATCH:`, `LAYOUT:`, `DEFLECTION:`, `BLOCK:`, `TURNOVER:`, `HUCK:` formats

### Segment Classification
Uses retroactive heuristic based on events-per-minute to override AI classification:
- Basketball: >10 shots/min = WARMUP, 2-6 = GAME
- Ultimate: checks for turnovers/goals to distinguish game from drills

## Key Technical Details

- Videos stored in GCS, accessed via signed URLs
- `ffprobe` used for duration detection (60s timeout)
- Segment analysis uses low temperature (0.2) for factual accuracy
- Summary generation uses high temperature (0.8) for strategic insights
- Token usage tracked per-segment and aggregated
