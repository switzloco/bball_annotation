import sys
import json
import urllib.request
import urllib.parse

sys.stdout.reconfigure(encoding="utf-8")

def get_json(path):
    url = "https://mh.majesticstats.com" + path
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return json.loads(urllib.request.urlopen(req).read().decode("utf-8"))

for tid in [2348, 1539, 559, 532, 510, 409, 375, 291, 58]:
    try:
        d = get_json(f"/api/teams/{tid}?bootstrap=1")
        team = d.get("team", {})
        games = d.get("games", [])
        print(f"Team ID {tid}: {team.get('name')} | Season: {team.get('season')} | Div: {team.get('division')} | Games: {len(games)}")
        if team.get("season") in ("Fall 2026", "Holiday 2026", "Summer 2026"):
            for g in games:
                print("  GAME:", json.dumps(g))
    except Exception as e:
        print(f"Team {tid} err: {e}")
