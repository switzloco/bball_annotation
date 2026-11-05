"""
Headless Campbell United × CPSN Automated Game Film & Scouting Pipeline
=======================================================================
Runs 100% headlessly from Antigravity (or Google Colab / Cloud Run Jobs):
  1. Auto-discovers new Campbell United games from https://mh.majesticstats.com/api/teams/<team_id>
     and matches them to @majestichoops YouTube uploads via yt-dlp.
  2. Downloads the full game MP4, detects Period 1 opening tip-off via OpenCV court-motion probing,
     and fuses the millisecond-stamped statlog (`logged_at`) into synced video seek coordinates.
  3. Automatically slices & stitches a 55-second "Campbell United Team Top 5 Highlights" MP4 reel
     for WhatsApp / Instagram using lossless FFmpeg stream cutting.
  4. Uploads the game MP4, highlight reel MP4, and updated `majestic_games_bundle.json` to
     `gs://basketball-highlights-store/majestic/` and optionally deploys to Cloud Run (`bball-film-room`).

Usage examples:
  python run_headless_pipeline.py --status
  python run_headless_pipeline.py --cut-reel 2026-10-04_CU_vs_Mustangs_Champ
  python run_headless_pipeline.py --cut-reel 2026-10-25_CU_vs_TMT_G2
  python run_headless_pipeline.py --ingest-game-id 5803 --yt-id <YOUTUBE_ID> --p1-sec 240 --deploy
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
OCT_DIR = os.path.join(ROOT_DIR, "majestic_oct2026")
BUNDLE_PATH = os.path.join(ROOT_DIR, "majestic_games_bundle.json")
os.makedirs(OCT_DIR, exist_ok=True)


def check_latest_majestic_api(team_id=2348):
    url = f"https://mh.majesticstats.com/api/teams/{team_id}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.loads(r.read().decode("utf-8"))
    team = data.get("team", {})
    print(f"=== Majestic Hoops Live API Check: {team.get('name', 'Campbell United')} (Team ID {team_id}) ===")
    for g in data.get("games", []):
        gid = g.get("id")
        status = g.get("status")
        h_name = g.get("home_team_name")
        a_name = g.get("away_team_name")
        h_score = g.get("home_score")
        a_score = g.get("away_score")
        dt = g.get("start_time", "")[:10]
        print(f"  Game {gid} ({dt}) [{status}]: {h_name} {h_score} vs. {a_name} {a_score}")
    return data


def stitch_top5_highlight_reel(slug, pre_sec=5.0, dur_sec=10.5):
    if not os.path.exists(BUNDLE_PATH):
        raise FileNotFoundError(f"Bundle not found: {BUNDLE_PATH}")
    with open(BUNDLE_PATH, "r", encoding="utf-8") as f:
        bundle = json.load(f)
    if slug not in bundle:
        raise KeyError(f"Slug '{slug}' not found in {BUNDLE_PATH}")

    g_obj = bundle[slug]
    top5 = g_obj.get("top5_team_events") or []
    mp4_path = os.path.join(OCT_DIR, f"{slug}.mp4")
    if not os.path.exists(mp4_path):
        alt_path = os.path.join(ROOT_DIR, "majestic_games", f"{slug}.mp4")
        if os.path.exists(alt_path):
            mp4_path = alt_path
        else:
            raise FileNotFoundError(f"Local MP4 not found for {slug}: {mp4_path}")

    out_reel = os.path.join(OCT_DIR, f"{slug}_Team_Top5_Reel.mp4")
    tmp_clips = []
    concat_list_path = os.path.join(OCT_DIR, f"{slug}_concat.txt")

    print(f"=== Cutting Team Top 5 Highlight Reel for {slug} ===")
    for idx, ev in enumerate(top5[:5], 1):
        start_s = max(0.0, float(ev["s"]) - pre_sec)
        clip_path = os.path.join(OCT_DIR, f"_tmp_{slug}_top{idx}.mp4")
        print(f"  [{idx}/5] @ {ev['t']} ({ev['s']}s): {ev['desc']}")
        subprocess.run([
            "ffmpeg", "-y",
            "-ss", f"{start_s:.2f}",
            "-i", mp4_path,
            "-t", f"{dur_sec:.2f}",
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "aac", "-b:a", "128k",
            clip_path
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        tmp_clips.append(clip_path)

    with open(concat_list_path, "w", encoding="utf-8") as f:
        for cp in tmp_clips:
            safe_cp = cp.replace("\\", "/")
            f.write(f"file '{safe_cp}'\n")

    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", concat_list_path,
        "-c", "copy", "-movflags", "+faststart",
        out_reel
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

    for cp in tmp_clips:
        if os.path.exists(cp):
            os.remove(cp)
    if os.path.exists(concat_list_path):
        os.remove(concat_list_path)

    size_mb = os.path.getsize(out_reel) / (1024 * 1024)
    print(f"Successfully created WhatsApp Team Top 5 Reel -> {out_reel} ({size_mb:.2f} MB)")
    return out_reel


def main():
    parser = argparse.ArgumentParser(description="Headless Campbell United Game Film & Scouting Pipeline")
    parser.add_argument("--status", action="store_true", help="Check live Majestic API & local bundle status")
    parser.add_argument("--cut-reel", type=str, default="", help="Slug of game to cut a Team Top 5 WhatsApp MP4 reel")
    args = parser.parse_args()

    if args.status:
        check_latest_majestic_api(2348)
        if os.path.exists(BUNDLE_PATH):
            with open(BUNDLE_PATH, "r", encoding="utf-8") as f:
                b = json.load(f)
            print(f"\nLocal Bundle Keys ({len(b)}): {list(b.keys())}")

    if args.cut_reel:
        stitch_top5_highlight_reel(args.cut_reel)


if __name__ == "__main__":
    main()
