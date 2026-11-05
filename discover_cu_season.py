import subprocess
import sys
import json
import urllib.request
from bs4 import BeautifulSoup

sys.stdout.reconfigure(encoding="utf-8")

# 1. Check all videos on Eugene's YouTube channel
cmd = [
    sys.executable,
    "-m",
    "yt_dlp",
    "--flat-playlist",
    "--dump-single-json",
    "https://www.youtube.com/channel/UCI8v9R91lAVPvl4eWEQHksw/videos",
]
out = subprocess.check_output(cmd, text=True, encoding="utf-8", errors="replace")
data = json.loads(out)
entries = data.get("entries", [])
print(f"Total channel videos: {len(entries)}")
for i, e in enumerate(entries):
    t = e.get("title", "")
    if any(k in t.lower() for k in ["campbell", "mustang", "oct", "nov", "champ", "final"]) or i < 35:
        print(f"{i:3d}: {e.get('id')} | {t} | {e.get('duration')}s")

# 2. Check Campbell United team pages across seasons on RecLeague
team_paths = [
    ("Spring 26 (431571)", "/leagues/majestichoops/teams/431571"),
    ("Winter 26 (419266)", "/leagues/91937/teams/419266"),
    ("Holiday 25 (404980)", "/leagues/88571/teams/404980"),
    ("Fall 25 (393302)", "/leagues/85790/teams/393302"),
    ("Summer 25 (384597)", "/leagues/83779/teams/384597"),
]

for label, path in team_paths:
    url = "https://www.recleague.net" + path
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    html = urllib.request.urlopen(req).read().decode("utf-8", errors="replace")
    soup = BeautifulSoup(html, "html.parser")
    print(f"\n=== {label}: {url} ===")
    for a in soup.find_all("a", href=True):
        if "/games/" in a["href"]:
            parent_text = " ".join(a.parent.parent.get_text(" ", strip=True).split())
            print(f"  GAME: {a['href']} -> {parent_text[:140]}")
    # Also print schedule rows without game links (future games!)
    for div in soup.select(".c-schedule-game, .m-game, tr, li"):
        txt = " ".join(div.get_text(" ", strip=True).split())
        if any(m in txt for m in ["Oct", "Nov", "Mustang", "Ricecooker", "Berksan", "PM @", "AM @"]):
            if len(txt) < 220:
                print(f"  SCHED: {txt}")
