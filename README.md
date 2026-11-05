# 🏀 CPSN × Campbell United — AI Basketball Film Room & Scouting Hub

[![Live Film Room](https://img.shields.io/badge/🏀_Live_Film_Room-Cloud_Run-ff5722?style=for-the-badge)](https://bball-film-room-615717094211.us-central1.run.app)
[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/switzloco/bball_annotation/blob/main/campbell_united_colab_pipeline.ipynb)

Live production deployment: **[bball-film-room-615717094211.us-central1.run.app](https://bball-film-room-615717094211.us-central1.run.app)**

An ESPN-style interactive game film, play-by-play synchronization, highlight reel, and opponent scouting platform built for **Campbell United** (Majestic Hoops / CPSN).

---

## ✨ Key Features

- **10 Synced Game Film Sessions**: Frame-accurate play-by-play timestamps, automated warmup skipping (`tipoff_sec`), and live scorebugs across Fall & Holiday seasons.
- **Broadcast Auto-Crop & Pan-and-Scan**: Dynamic `1.85x`–`2.1x` court zoom and hoop-side tracking (`cu_h1_hoop` / `cu_h2_hoop`) so action on the far court fills the viewport.
- **Smart Highlight Curation**: Automatically filters out routine free throws (`isHighlightEligiblePlay`) unless it is a clutch late-game situation (`<= 1:30` left in 2nd Half/OT within 6 points), surfacing 3PT daggers, steals, blocks, and transition buckets.
- **Opponent Scouting Report (`RiceCookers`)**: Interactive player tendency cards, shot profile breakdowns, and broadcast-zoomed scouting tape reels.
- **WhatsApp & Mobile Deep-Linking**: Shareable play links (`?game=...&play=...`) that jump straight to the exact video timestamp without scrolling away from the player.

---

## 📂 Repository Structure

- [`index.html`](index.html) — Main single-page ESPN broadcast film room application.
- [`server.py`](server.py) — Python HTTP backend supporting byte-range video streaming, training feedback logging, and roster endpoints.
- [`majestic_games_bundle.json`](majestic_games_bundle.json) — Master 10-game play-by-play, box score, highlight, and scouting dataset.
- [`campbell_united_colab_pipeline.ipynb`](campbell_united_colab_pipeline.ipynb) — Google Colab analytics & GPU computer-vision notebook.
- [`cloud_run_deploy/`](cloud_run_deploy/) — Production container (`Dockerfile` + synced assets) deployed to Google Cloud Run (`basketball-annotater`).
- `majestic_games/` & `majestic_oct2026/` — Per-game RecLeague/Majestic JSON play logs, CV fusion outputs, and scouting card assets (heavy `.mp4`/`.MOV` raw video files are excluded via `.gitignore` and hosted on Google Cloud Storage at `gs://basketball-highlights-store`).

---

## 🚀 Running Locally

```bash
python server.py
# Open http://localhost:8090
```

## ☁️ Deploying to Google Cloud Run

```powershell
Copy-Item index.html, majestic_games_bundle.json, server.py cloud_run_deploy/
gcloud run deploy bball-film-room --source ./cloud_run_deploy --region us-central1 --project basketball-annotater --allow-unauthenticated
```
