import sys
import json
import urllib.request
import urllib.parse

sys.stdout.reconfigure(encoding="utf-8")

def get_json(path):
    url = "https://mh.majesticstats.com" + path
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return json.loads(urllib.request.urlopen(req).read().decode("utf-8"))

for s in ["Fall 2026", "Holiday 2026"]:
    qs = urllib.parse.urlencode({"season": s, "type": "all"})
    games = get_json(f"/api/games?{qs}")
    print(f"\n=== {s} (total games={len(games)}) ===")
    for g in games:
        ht = str(g.get("home_team", ""))
        at = str(g.get("away_team", ""))
        if "campbell" in ht.lower() or "campbell" in at.lower() or "mustang" in ht.lower() or "mustang" in at.lower():
            print(" ", json.dumps(g))
