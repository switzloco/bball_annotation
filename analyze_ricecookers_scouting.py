import sys
import json
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

def get_json(path):
    url = "https://mh.majesticstats.com" + path
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return json.loads(urllib.request.urlopen(req).read().decode("utf-8"))

# Search Ricecookers across all seasons
sr = get_json("/api/search?q=Ricecookers")
print("=== SEARCH RICECOOKERS ===")
print(json.dumps(sr, indent=2))

for t in sr.get("teams", []):
    tid = t["id"]
    td = get_json(f"/api/teams/{tid}?bootstrap=1")
    team_info = td.get("team", {})
    rec = td.get("record", {})
    print(f"Team {tid}: {team_info.get('name')} | Season: {team_info.get('season')} | Div: {team_info.get('division')} | Record: {rec.get('wins')}-{rec.get('losses')}")
    if team_info.get("season") == "Fall 2026":
        with open("majestic_oct2026/ricecookers_fall2026_team.json", "w", encoding="utf-8") as f:
            json.dump(td, f, indent=2)

# Inspect the 3 Holiday 2026 Ricecookers games
for gid in [5508, 5804, 5801]:
    with open(f"majestic_oct2026/ricecookers_game_{gid}_full.json", "r", encoding="utf-8") as f:
        d = json.load(f)
    g = d["game"]
    print(f"\n=== RICECOOKERS GAME {gid}: {g['home_team']} {g['home_score']} vs {g['away_team']} {g['away_score']} ({g['scheduled_at'][:10]}) ===")
    for b in d["boxscore"]:
        if b["team_name"] == "Ricecookers":
            print(f"  #{b.get('jersey_number')} {b['name']}: {b.get('points')} PTS | FG {b.get('fgm')}/{b.get('fga')} | 3PT {b.get('three_pm')}/{b.get('three_pa')} | FT {b.get('ftm')}/{b.get('fta')} | {b.get('rebounds')} REB | {b.get('assists')} AST | {b.get('steals')} STL | {b.get('blocks')} BLK | {b.get('turnovers')} TO | {b.get('fouls')} PF")
