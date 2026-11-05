import os
import subprocess
import time

SRC = r"c:\dev\bball_annotation\20261031_full_game.mp4"
OUT_DIR = r"C:\Users\Nick\.gemini\antigravity\brain\92e691fb-4334-4d76-9835-87d6d959086f\scratch\web_chunks"
FINAL_WEB = r"c:\dev\bball_annotation\20261031_full_game_web.mp4"

os.makedirs(OUT_DIR, exist_ok=True)

# 4 slices covering 0..2254.5s
SLICES = [
    (0, 0.0, 565.0),
    (1, 565.0, 565.0),
    (2, 1130.0, 565.0),
    (3, 1695.0, 560.0),
]

t0 = time.time()
procs = []
chunk_files = []

print("Starting 4 parallel AVX-512 720p30 web encodes...")
for idx, start, dur in SLICES:
    out_path = os.path.join(OUT_DIR, f"web_part_{idx}.mp4")
    chunk_files.append(out_path)
    cmd = [
        "ffmpeg", "-y",
        "-ss", str(start),
        "-t", str(dur),
        "-i", SRC,
        "-vf", "scale=1280:720",
        "-c:v", "libx264",
        "-preset", "superfast",
        "-crf", "27",
        "-g", "60",
        "-keyint_min", "60",
        "-sc_threshold", "0",
        "-c:a", "aac",
        "-b:a", "128k",
        out_path
    ]
    procs.append(subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))

for p in procs:
    p.wait()

print(f"Encoded 4 chunks in {time.time() - t0:.1f}s. Concatenating with +faststart...")
concat_txt = os.path.join(OUT_DIR, "web_concat.txt")
with open(concat_txt, "w", encoding="utf-8") as f:
    for cp in chunk_files:
        f.write(f"file '{cp.replace(os.sep, '/')}'\n")

subprocess.run([
    "ffmpeg", "-y",
    "-f", "concat",
    "-safe", "0",
    "-i", concat_txt,
    "-c", "copy",
    "-movflags", "+faststart",
    FINAL_WEB
], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

size_mb = os.path.getsize(FINAL_WEB) / (1024 * 1024)
print(f"Created {FINAL_WEB} ({size_mb:.1f} MB) in {time.time() - t0:.1f}s total!")
print("Uploading to gs://basketball-highlights-store/runs/2026-10-31/20261031_full_game.mp4 ...")

env = os.environ.copy()
env["CLOUDSDK_METRICS_ENVIRONMENT"] = "datacloud.antigravity"
subprocess.run([
    "gcloud.cmd", "storage", "cp",
    FINAL_WEB,
    "gs://basketball-highlights-store/runs/2026-10-31/20261031_full_game.mp4",
    "--project=basketball-annotater"
], check=True, env=env)

# Also make the video object publicly readable for direct full-game downloads & fast streaming
subprocess.run([
    "gcloud.cmd", "storage", "objects", "update",
    "gs://basketball-highlights-store/runs/2026-10-31/20261031_full_game.mp4",
    "--add-acl-grant=entity=AllUsers,role=READER",
    "--project=basketball-annotater"
], check=False, env=env)

print(f"DONE! Total elapsed: {time.time() - t0:.1f}s")
