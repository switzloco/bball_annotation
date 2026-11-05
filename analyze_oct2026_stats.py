import sys
import json

sys.stdout.reconfigure(encoding="utf-8")

games = [
    ("2026-10-04_CU_vs_Mustangs_Champ", "majestic_oct2026/2026-10-04_CU_vs_Mustangs_Champ_full.json"),
    ("2026-10-18_CU_vs_HalalHoopers_G1", "majestic_oct2026/2026-10-18_CU_vs_HalalHoopers_G1_full.json"),
    ("2026-10-25_CU_vs_TMT_G2", "majestic_oct2026/2026-10-25_CU_vs_TMT_G2_full.json"),
    ("2026-11-01_CU_vs_Misfits2_G3", "majestic_oct2026/2026-11-01_CU_vs_Misfits2_G3_full.json"),
]

for slug, path in games:
    with open(path, "r", encoding="utf-8") as f:
        d = json.load(f)
    g = d["game"]
    print(f"\n=======================================================")
    print(f"{slug}: {g['home_team']} {g['home_score']} vs {g['away_team']} {g['away_score']} ({g['season']} {g['division']} @ {g['venue']})")
    print(f"Settings track_missed_shots: {d.get('settings', {}).get('track_missed_shots')}")
    print("--- BOXSCORE ---")
    for b in d["boxscore"]:
        if int(b.get("points", 0) or 0) > 0 or int(b.get("rebounds", 0) or 0) > 0 or int(b.get("assists", 0) or 0) > 0 or int(b.get("fga", 0) or 0) > 0:
            print(f"  [{b['team_name']}] #{b.get('jersey_number')} {b['name']}: {b.get('points')} PTS | FG {b.get('fgm')}/{b.get('fga')} | 3PT {b.get('three_pm')}/{b.get('three_pa')} | FT {b.get('ftm')}/{b.get('fta')} | {b.get('rebounds')} REB | {b.get('assists')} AST | {b.get('steals')} STL | {b.get('blocks')} BLK | {b.get('turnovers')} TO | {b.get('fouls')} PF")
    statlog = d.get("statlog", [])
    print(f"--- STATLOG ({len(statlog)} entries) ---")
    if statlog:
        # Print first 8 and last 8 chronologically (note: check if statlog is reverse-chronological or chronological)
        print("  First 5 in array:")
        for s in statlog[:5]:
            print("   ", s)
        print("  Last 5 in array:")
        for s in statlog[-5:]:
            print("   ", s)
