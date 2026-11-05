import sys
import os
import json
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

os.makedirs("majestic_oct2026", exist_ok=True)

def get_json(path):
    url = "https://mh.majesticstats.com" + path
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return json.loads(urllib.request.urlopen(req).read().decode("utf-8"))

# 1. Fetch Campbell United Fall 2026 team (1767) and Holiday 2026 team (2348) and Ricecookers (2336)
for tid, slug in [(1767, "cu_fall2026"), (2348, "cu_holiday2026"), (2336, "ricecookers_holiday2026"), (1830, "mustangs_fall2026")]:
    d = get_json(f"/api/teams/{tid}?bootstrap=1")
    with open(f"majestic_oct2026/{slug}_team.json", "w", encoding="utf-8") as f:
        json.dump(d, f, indent=2)
    print(f"Saved {slug}_team.json: keys={list(d.keys())}")

# 2. Fetch full game data + boxscore for CU's games: 5211 (Mustangs Champ), 5505 (HH Wk1), 5893 (TMT Wk2), 5858 (Misfits2 Wk3)
for gid, name in [
    (5211, "2026-10-04_CU_vs_Mustangs_Champ"),
    (5505, "2026-10-18_CU_vs_HalalHoopers_G1"),
    (5893, "2026-10-25_CU_vs_TMT_G2"),
    (5858, "2026-11-01_CU_vs_Misfits2_G3"),
]:
    full_g = get_json(f"/api/games/{gid}/full")
    with open(f"majestic_oct2026/{name}_full.json", "w", encoding="utf-8") as f:
        json.dump(full_g, f, indent=2)
    print(f"Game {gid} ({name}): keys={list(full_g.keys())}")
    for k, v in full_g.items():
        if isinstance(v, list):
            print(f"  {k}: list of {len(v)} items; sample={str(v[0])[:180] if v else 'empty'}")
        elif isinstance(v, dict):
            print(f"  {k}: dict keys={list(v.keys())}")
