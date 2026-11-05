FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY index.html server.py play_by_play.md youtube_description.txt training_feedback.json training_corrections.jsonl majestic_games_bundle.json /app/

ENV PORT=8080
EXPOSE 8080

CMD ["python", "server.py"]
