import sys
import json
import urllib.request
import subprocess

sys.stdout.reconfigure(encoding="utf-8")

def get_json(path):
    url = "https://mh.majesticstats.com" + path
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return json.loads(urllib.request.urlopen(req).read().decode("utf-8"))

with open("majestic_oct2026/ricecookers_holiday2026_team.json", "r", encoding="utf-8") as f:
    rc = json.load(f)

print("=== RICECOOKERS HOLIDAY 2026 (Team 2336) ===")
print("Team:", rc.get("team"))
print("Record:", rc.get("record"))
print("Roster:", json.dumps(rc.get("roster"), indent=2))
print("Games:")
for g in rc.get("games", []):
    print(" ", json.dumps(g))
    if g.get("status") == "final":
        fg = get_json(f"/api/games/{g['id']}/full")
        with open(f"majestic_oct2026/ricecookers_game_{g['id']}_full.json", "w", encoding="utf-8") as out_f:
            json.dump(fg, out_f, indent=2)
        print(f"    Saved ricecookers_game_{g['id']}_full.json: {g.get('home_team')} {g.get('home_score')} - {g.get('away_score')} {g.get('away_team')}")

print("Upcoming:")
for u in rc.get("upcoming", []):
    print(" ", json.dumps(u))

# Also search @majestichoops for RIC (Ricecookers) and CU videos
cmd = [
    sys.executable,
    "-m",
    "yt_dlp",
    "--flat-playlist",
    "--dump-single-json",
    "--playlist-end",
    "120",
    "https://www.youtube.com/@majestichoops/videos",
]
out = subprocess.check_output(cmd, text=True, encoding="utf-8", errors="replace")
yt_data = json.loads(out)
print("\n=== MATCHING @majestichoops VIDEOS (CU, MUS, HH, TMT, RIC, MIS) ===")
for i, e in enumerate(yt_data.get("entries", [])):
    t = e.get("title", "")
    if any(k in t.upper() for k in ["CU ", " V CU", "RIC", "MUS", "RICE"]):
        print(f"  {i:3d}: {e.get('id')} | {t} | {e.get('duration')}s")
