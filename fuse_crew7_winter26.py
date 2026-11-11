import json
import os

BUNDLE_PATH = r"c:\dev\bball_annotation\majestic_games_bundle.json"

with open(BUNDLE_PATH, "r", encoding="utf-8") as f:
    bundle = json.load(f)


def fmt_mmss(sec):
    sec = max(0, int(round(sec)))
    return f"{sec // 60:02d}:{sec % 60:02d}"


def build_box_tables(boxscore, our_team, opp_team, our_rec, opp_rec):
    header = ["Player", "Pts", "FTM", "FGM", "2PM", "3PM", "Reb", "Ast", "Stl", "Blk", "Fls", "T-Fls", "TOs", "PPR"]

    def team_rows(tname):
        rows = [header]
        players = [b for b in boxscore if b.get("team_name") == tname and not b.get("dnp")]
        players.sort(key=lambda x: (int(x.get("points") or 0), int(x.get("rebounds") or 0), int(x.get("assists") or 0)), reverse=True)
        tot = [0] * 12
        for p in players:
            num = p.get("jersey_number")
            num_str = f"#{num} " if num is not None and str(num) != "" else ""
            pname = f"{num_str}{p.get('name', 'Player')}".strip()
            pts = int(p.get("points") or 0)
            ftm = int(p.get("ftm") or 0)
            fgm = int(p.get("fgm") or 0)
            threepm = int(p.get("three_pm") or 0)
            twopm = max(0, fgm - threepm)
            reb = int(p.get("rebounds") or 0)
            ast = int(p.get("assists") or 0)
            stl = int(p.get("steals") or 0)
            blk = int(p.get("blocks") or 0)
            fls = int(p.get("fouls") or 0)
            tfls = int(p.get("techs") or p.get("tech_fouls") or 0)
            tos = int(p.get("turnovers") or 0)
            # Skip 0-across-the-board inactive bench entries so boxscore stays crisp
            if pts == 0 and reb == 0 and ast == 0 and stl == 0 and blk == 0 and fls == 0 and tos == 0 and int(p.get("fga") or 0) == 0:
                continue
            ppr = round(pts + reb * 1.2 + ast * 1.5 + stl * 2.0 + blk * 2.0 - tos * 1.0 - fls * 0.5, 1)
            vals = [pts, ftm, fgm, twopm, threepm, reb, ast, stl, blk, fls, tfls, tos]
            for idx_v, v in enumerate(vals):
                tot[idx_v] += v
            rows.append([pname] + [str(v) for v in vals] + [str(ppr)])
        tot_ppr = round(tot[0] + tot[5] * 1.2 + tot[6] * 1.5 + tot[7] * 2.0 + tot[8] * 2.0 - tot[11] * 1.0 - tot[9] * 0.5, 1)
        rows.append(["Team Totals"] + [str(v) for v in tot] + [str(tot_ppr)])
        return rows

    return [
        [[f"{our_team} ({our_rec})"]],
        team_rows(our_team),
        [[f"{opp_team} ({opp_rec})"]],
        team_rows(opp_team),
    ]


MO_C7_REEL_GCS = "https://storage.googleapis.com/basketball-highlights-store/majestic/reels/2026-02-01_C7_Mo_Winter26_Reel.mp4?v=1080p1"

# Exact LED-Scoreboard Binary-Searched Buckets (86/86 exact score jumps across W2, W3, W4!)
# Format: (half, pts, cu_score, opp_est, shot_s, led_s, player, assist_player, verified, desc_override)
W2_LED_EVENTS = [
    (1, 1,  1,  7,  535.0,  538.0, "#00 Arman", None, False, None),
    (1, 1,  2,  7,  552.0,  555.0, "#00 Arman", None, False, None),
    (1, 3,  5,  9,  642.8,  646.9, "#2 Mohamed", None, True,
     "#2 Mohamed pulls up in the right-wing foreground (cyan kicks!) & splashes 3-Pointer #1 of 4! (5-9 Crew 7)"),
    (1, 2,  7,  9,  660.2,  663.1, "#8 Nate Watkins", None, False, None),
    (1, 3, 10,  9,  683.8,  686.9, "#10 Shain", None, False, None),
    (1, 2, 12, 15,  861.5,  864.8, "#23 Tharon", None, False, None),
    (1, 2, 14, 15,  874.8,  878.0, "#8 Nate Watkins", None, False, None),
    (1, 3, 17, 18,  943.5,  946.9, "#10 Shain", None, False, None),
    (1, 3, 20, 21, 1074.0, 1077.5, "#00 Arman", None, False, None),
    (1, 2, 22, 37, 1306.0, 1309.4, "#23 Tharon", None, False, None),
    (1, 1, 23, 35, 1615.0, 1618.0, "#9 Aaron Sletten", None, False, None),
    (1, 1, 24, 35, 1633.0, 1636.0, "#9 Aaron Sletten", None, False, None),
    (2, 3, 27, 38, 1927.6, 1931.9, "#2 Mohamed", None, True,
     "#2 Mohamed opens the 2nd Half drilling a deep left-corner 3-Pointer #2 of 4! (27-38 Crew 7)"),
    (2, 3, 30, 43, 2041.5, 2045.0, "#8 Nate Watkins", None, False, None),
    (2, 2, 32, 48, 2228.5, 2231.9, "#9 Aaron Sletten", None, False, None),
    (2, 2, 34, 48, 2253.0, 2256.2, "#8 Nate Watkins", None, False, None),
    (2, 3, 37, 50, 2333.2, 2337.5, "#2 Mohamed", None, True,
     "#2 Mohamed rises from top-of-the-arc & buries rainbow 3-Pointer #3 of 4! (37-50 Crew 7)"),
    (2, 3, 40, 50, 2375.2, 2378.8, "#10 Shain", None, False, None),
    (2, 3, 43, 54, 2562.8, 2566.2, "#00 Arman", None, False, None),
    (2, 3, 46, 57, 2624.5, 2628.8, "#2 Mohamed", None, True,
     "FLAMETHROWER! #2 Mohamed catches on the left wing & drains 3-Pointer #4 of 4 (4/4 3PT — 100%!)"),
    (2, 3, 49, 61, 2859.0, 2862.5, "#10 Shain", None, False, None),
    (2, 2, 51, 63, 3008.5, 3011.9, "#24 Pete Drodrolagi", None, False, None),
    (2, 3, 54, 63, 3125.2, 3128.8, "#00 Arman", None, False, None),
    (2, 2, 56, 63, 3151.0, 3154.4, "#8 Nate Watkins", None, False, None),
    (2, 2, 58, 69, 3295.8, 3298.1, "#2 Mohamed", None, True,
     "#2 Mohamed skies above 3 defenders in the lane for an acrobatic floater! (14 PTS, 5/5 FG, 7 REB, 3 STL, 1 BLK)"),
]

W3_LED_EVENTS = [
    (1, 2,  2, 21,  681.5,  685.0, "#23 Tharon", None, False, None),
    (1, 2,  4, 26,  761.5,  765.0, "#00 Arman", "#2 Mohamed", False, None),
    (1, 2,  6, 29,  832.5,  835.0, "#2 Mohamed", None, True,
     "#2 Mohamed splits the BTA defense down the heart of the lane & finishes high in traffic! (6-29 Crew 7)"),
    (1, 2,  8, 29,  862.8,  866.2, "#2 Mohamed", None, True,
     "#2 Mohamed attacks the left block again for back-to-back interior buckets! (8-29 Crew 7)"),
    (1, 1,  9, 29,  886.5,  889.4, "#2 Mohamed", None, True,
     "#2 Mohamed completes the And-1 / Free Throw at the line (9-29 Crew 7)"),
    (1, 3, 12, 31,  962.2,  965.6, "#8 Nate Watkins", "#2 Mohamed", False, None),
    (1, 3, 15, 37, 1049.8, 1053.1, "#8 Nate Watkins", None, False, None),
    (1, 3, 18, 39, 1083.0, 1086.2, "#10 Shain", None, False, None),
    (1, 2, 20, 39, 1103.5, 1106.9, "#0 Cam", None, False, None),
    (1, 2, 22, 45, 1150.5, 1153.8, "#23 Tharon", None, False, None),
    (1, 3, 25, 45, 1167.2, 1170.6, "#8 Nate Watkins", "#2 Mohamed", False, None),
    (1, 2, 27, 49, 1324.8, 1328.1, "#00 Arman", None, False, None),
    (1, 1, 28, 49, 1343.0, 1345.6, "#23 Tharon", None, False, None),
    (1, 1, 29, 55, 1406.5, 1409.4, "#0 Cam", None, False, None),
    (1, 2, 31, 55, 1454.2, 1457.5, "#0 Cam", None, False, None),
    (1, 3, 34, 59, 1558.8, 1563.1, "#2 Mohamed", None, True,
     "END-OF-HALF DAGGER! #2 Mohamed walks into a deep transition pull-up 3-Pointer with 25s left in H1! (34-59)"),
    (2, 3, 37, 59, 1766.0, 1769.4, "#8 Nate Watkins", None, False, None),
    (2, 3, 40, 59, 1814.0, 1817.5, "#0 Cam", "#2 Mohamed", False, None),
    (2, 2, 42, 59, 1824.2, 1827.5, "#23 Tharon", None, False, None),
    (2, 2, 44, 59, 1847.2, 1850.6, "#00 Arman", None, False, None),
    (2, 2, 46, 61, 1963.7, 1966.2, "#2 Mohamed", None, True,
     "#2 Mohamed DOUBLE-DOUBLE! Streaks coast-to-coast & finishes high off glass (13 PTS, 11 REB, 5 AST, STL, BLK!)"),
    (2, 2, 48, 63, 1994.2, 1997.5, "#23 Tharon", None, False, None),
    (2, 2, 50, 69, 2251.5, 2255.0, "#0 Cam", None, False, None),
    (2, 3, 53, 73, 2381.5, 2385.0, "#8 Nate Watkins", "#2 Mohamed", False, None),
    (2, 3, 56, 79, 2604.8, 2608.1, "#2 Mohamed", None, True,
     "#2 Mohamed splashes 2nd 3-Pointer of the night from the right arc! (56-79 Crew 7)"),
    (2, 3, 59, 82, 2663.5, 2666.9, "#8 Nate Watkins", None, False, None),
    (2, 2, 61, 82, 2735.5, 2738.8, "#23 Tharon", None, False, None),
    (2, 2, 63, 82, 2759.8, 2763.1, "#00 Arman", None, False, None),
    (2, 2, 65, 84, 2784.8, 2788.1, "#8 Nate Watkins", None, False, None),
    (2, 2, 67, 84, 2806.0, 2809.4, "#23 Tharon", None, False, None),
    (2, 2, 69, 86, 2946.0, 2949.4, "#0 Cam", None, False, None),
]

W4_LED_EVENTS = [
    (1, 3,  3,  2,  526.5,  531.2, "#2 Mohamed", None, True,
     "#2 Mohamed initiates Crew 7's opening possession — 3-Pointer puts Crew 7 on the board! (3-2)"),
    (1, 3,  6, 21,  911.8,  915.0, "#2 Mohamed", None, True,
     "#2 Mohamed spots up on the right wing & buries a high-arcing 3-Pointer! (6-21 Crew 7)"),
    (1, 3,  9, 21,  938.5,  942.5, "#9 Aaron Sletten", None, False, None),
    (1, 2, 11, 21,  963.0,  966.2, "#2 Mohamed", None, True,
     "25-PT EXPLOSION! #2 Mohamed sprints ahead in transition & lays it high off the left glass! (11-21)"),
    (1, 2, 13, 25, 1022.5, 1025.6, "#8 Nate Watkins", None, False, None),
    (1, 2, 15, 32, 1306.5, 1311.2, "#23 Tharon", None, False, None),
    (1, 2, 17, 45, 1637.5, 1646.2, "#9 Aaron Sletten", None, False, None),
    (1, 2, 19, 45, 1681.5, 1690.6, "#2 Mohamed", None, True,
     "#2 Mohamed slashes into the left paint & finishes in traffic! (19-45 Crew 7)"),
    (1, 3, 22, 51, 1841.5, 1846.9, "#10 Shain", None, True,
     "#10 Shain rises from deep right wing & splashes a 3-Pointer! (22-51 Crew 7)"),
    (1, 2, 24, 51, 1866.4, 1870.0, "#2 Mohamed", None, True,
     "HALFTIME BUZZER BREAKAWAY! #2 Mohamed goes solo down the left lane & scores before the horn! (24-51)"),
    (2, 2, 26, 55, 2103.5, 2106.2, "#9 Aaron Sletten", None, False, None),
    (2, 2, 28, 60, 2231.0, 2233.8, "#8 Nate Watkins", None, False, None),
    (2, 3, 31, 62, 2268.5, 2271.2, "#8 Nate Watkins", "#2 Mohamed", True,
     "#2 Mohamed pushes in the foreground & dishes to the left corner for a 3-Pointer! (Assist #1 of 2)"),
    (2, 2, 33, 66, 2341.5, 2349.4, "#2 Mohamed", None, True,
     "#2 Mohamed seals deep inside the right paint & finishes at the rim! (33-66 Crew 7)"),
    (2, 3, 36, 68, 2388.0, 2391.2, "#8 Nate Watkins", None, True,
     "#8 Nate Watkins pulls up at the top of the key & drains a 3-Pointer! (36-68 Crew 7)"),
    (2, 3, 39, 68, 2412.5, 2415.6, "#8 Nate Watkins", "#2 Mohamed", True,
     "PLAYMAKER MO! #2 Mohamed blows baseline past #24, collapses the paint & kicks out for a 3PT splash! (Assist #2)"),
    (2, 2, 41, 70, 2444.5, 2456.9, "#9 Aaron Sletten", None, False, None),
    (2, 2, 43, 72, 2480.5, 2489.4, "#9 Aaron Sletten", None, False, None),
    (2, 2, 45, 74, 2529.5, 2532.5, "#9 Aaron Sletten", None, False, None),
    (2, 2, 47, 82, 2710.5, 2713.8, "#9 Aaron Sletten", None, False, None),
    (2, 2, 49, 85, 2766.5, 2770.0, "#23 Tharon", None, False, None),
    (2, 2, 51, 85, 2795.8, 2797.5, "#2 Mohamed", None, True,
     "#2 Mohamed Euro-steps down the right lane & scores softly off the glass over the contest! (51-85)"),
    (2, 2, 53, 89, 2881.5, 2890.6, "#2 Mohamed", None, True,
     "#2 Mohamed drives the right baseline & converts at the cup! (53-89 Crew 7)"),
    (2, 2, 55, 93, 3027.0, 3030.0, "#9 Aaron Sletten", None, False, None),
    (2, 3, 58, 95, 3069.5, 3073.8, "#2 Mohamed", None, True,
     "#2 Mohamed buries his 3rd 3-Pointer of the game! (58-95 Crew 7)"),
    (2, 2, 60, 95, 3104.5, 3117.5, "#2 Mohamed", None, True,
     "UNSTOPPABLE! #2 Mohamed rips past his defender on the right sideline & takes it all the way to the rim! (60-95)"),
    (2, 2, 62, 97, 3161.5, 3177.5, "#2 Mohamed", None, True,
     "SEASON-HIGH 25 POINTS! #2 Mohamed streaks solo down the middle for a breakaway layup! (11/11 FG Made, 9 REB!)"),
    (2, 2, 64, 98, 3186.5, 3190.0, "#8 Nate Watkins", None, False, None),
    (2, 3, 67, 100, 3204.0, 3206.9, "#23 Tharon", None, False, None),
    (2, 2, 69, 100, 3226.5, 3230.0, "#8 Nate Watkins", None, False, None),
]


def build_led_fused_game(cfg, led_rows):
    with open(cfg["json_path"], "r", encoding="utf-8") as f:
        data = json.load(f)
    boxscore = data.get("boxscore", [])
    our_team = cfg["cu_team_name"]
    opp_team = cfg["opp_team_name"]

    events = []
    for idx, (half, pts, cu_sc, opp_sc, shot_s, led_s, player, ast_p, verified, custom_desc) in enumerate(led_rows, 1):
        per_label = "1st Half" if half == 1 else "2nd Half"
        hoop_side = cfg["cu_h1_hoop"] if half == 1 else cfg["cu_h2_hoop"]
        play_s = int(round(shot_s))
        score_str = f"{cu_sc} - {opp_sc}"
        action = "3-pt FG Made" if pts == 3 else ("2-pt FG Made" if pts == 2 else "FT Made")
        ast_suffix = f" — Assist: {ast_p}" if ast_p else ""

        if custom_desc:
            desc = custom_desc
        else:
            collab_hint = " [LED-Synced • Tap 🤝 Collab to Verify Scorer]"
            if pts == 3:
                desc = f"{player} splashes a 3-Pointer ({score_str} {our_team}){ast_suffix}{collab_hint}"
            elif pts == 2:
                desc = f"{player} scores a 2-PT bucket ({score_str} {our_team}){ast_suffix}{collab_hint}"
            else:
                desc = f"{player} sinks Free Throw ({score_str} {our_team}){collab_hint}"

        tags = ["CU", "MAKE"]
        if pts == 3:
            tags.extend(["FG_MADE", "3PT"])
        elif pts == 2:
            tags.extend(["FG_MADE", "2PT"])
        else:
            tags.extend(["FT", "FT_MADE"])
        if ast_p:
            tags.append("AST")
        if "#2 Mohamed" in player or (ast_p and "#2 Mohamed" in ast_p):
            tags.append("MO_HIGHLIGHT")
        if not verified:
            tags.append("COLLAB_NEEDS_VERIFY")

        events.append({
            "idx": idx,
            "t": fmt_mmss(play_s),
            "s": play_s,
            "splash_s": round(float(shot_s), 1),
            "led_flip_s": round(float(led_s), 1),
            "raw_wall_t": round(float(led_s), 1),
            "wall_clock": f"LED@{fmt_mmss(led_s)}",
            "game_clock": f"LED {fmt_mmss(led_s)}",
            "period": per_label,
            "team": our_team,
            "is_cu": True,
            "isMajesticVerified": bool(verified),
            "collab_status": "verified_1080p" if verified else "needs_player_verify",
            "player": player,
            "assist_player": ast_p,
            "action": action,
            "pts_added": pts,
            "cu_score": cu_sc,
            "opp_score": opp_sc,
            "score_str": score_str,
            "hoop_side": hoop_side,
            "rim_energy": 9.8 if verified else 8.5,
            "tags": tags,
            "desc": desc,
            "avatar": ""
        })

    mo_evs = [e for e in events if "MO_HIGHLIGHT" in e["tags"]]
    other_evs = [e for e in events if e not in mo_evs]
    cu_highlights = mo_evs + other_evs
    top5 = [e for e in mo_evs if e.get("isMajesticVerified") and e["pts_added"] >= 2][:5]
    if len(top5) < 5:
        top5.extend([e for e in cu_highlights if e not in top5][: 5 - len(top5)])

    box_tables = build_box_tables(boxscore, our_team, opp_team, cfg["cu_record"], cfg["opp_record"])
    active_roster = [
        f"#{b.get('jersey_number')} {b.get('name')}".strip()
        for b in boxscore
        if b.get("team_name") == our_team and not b.get("dnp") and (int(b.get("points") or 0) > 0 or int(b.get("rebounds") or 0) > 0)
    ]

    return {
        "config": {
            "id": cfg["id"],
            "slug": cfg["slug"],
            "short_title": cfg["short_title"],
            "title": cfg["title"],
            "yt_id": cfg["yt_id"],
            "video_path": cfg["video_path"],
            "json_path": cfg["json_path"],
            "p1_first_sec": cfg["tipoff_sec"],
            "cu_team_name": our_team,
            "opp_team_name": opp_team,
            "cu_record": cfg["cu_record"],
            "opp_record": cfg["opp_record"],
            "cu_jerseys": cfg["cu_jerseys"],
            "opp_jerseys": cfg["opp_jerseys"],
            "cu_h1_hoop": cfg["cu_h1_hoop"],
            "cu_h2_hoop": cfg["cu_h2_hoop"],
            "default_lag_sec": 3.0,
            "has_video": cfg["has_video"],
            "video_url": cfg["video_url"],
            "tipoff_sec": cfg["tipoff_sec"],
            "tipoff_mmss": fmt_mmss(cfg["tipoff_sec"]),
            "mo_reel_url": MO_C7_REEL_GCS,
            "cu_reel": MO_C7_REEL_GCS,
            "team_top5_reel": MO_C7_REEL_GCS,
            "zero_timestamp_recovery": "Physical LED Wall Scoreboard Binary Search (100% Score Jump Recovery)",
            "active_roster": active_roster,
        },
        "box_score_tables": box_tables,
        "final_cu_score": cfg["final_cu_score"],
        "final_opp_score": cfg["final_opp_score"],
        "total_fused_events": len(events),
        "reconstructed_missed_shots_before_rebounds": 0,
        "top5_team_events": top5,
        "cu_highlight_events": cu_highlights,
        "events": events,
    }


C7_CONFIGS = [
    (
        {
            "id": "majestic_2026_02_01_c7_w4",
            "slug": "2026-02-01_C7_vs_OutOfShape_W4",
            "short_title": "🔥 Crew 7 W4: #2 Mohamed 25 PTS (11 FG, 3× 3PM, 9 REB) vs. Out Of Shape (Feb 1)",
            "title": "Crew 7 (#2 Mohamed — 25 PTS, 9 REB) vs. Out Of Shape — Winter '26 Week 4 (Feb 1, 2026)",
            "yt_id": "si_67Wy2FaQ",
            "video_path": r"c:\dev\bball_annotation\majestic_crew7\2026-02-01_C7_vs_OutOfShape_W4.mp4",
            "json_path": r"c:\dev\bball_annotation\majestic_crew7\2026-02-01_C7_vs_OutOfShape_W4_full.json",
            "tipoff_sec": 485,
            "cu_team_name": "Crew 7",
            "opp_team_name": "Out Of Shape",
            "cu_record": "Winter '26 Black",
            "opp_record": "Winter '26 Black",
            "cu_jerseys": "Red (#2 Mohamed [White Sleeves + Red Shorts], #8 Nate, #9 Aaron [Blue Tee], #10 Shain, #23 Tharon, #24 Pete)",
            "opp_jerseys": "Black/Green",
            "cu_h1_hoop": "left",
            "cu_h2_hoop": "right",
            "has_video": True,
            "video_url": "https://storage.googleapis.com/basketball-highlights-store/majestic/2026-02-01_C7_vs_OutOfShape_W4.mp4?v=1080p",
            "final_cu_score": 69,
            "final_opp_score": 100,
        },
        W4_LED_EVENTS,
    ),
    (
        {
            "id": "majestic_2026_01_25_c7_w3",
            "slug": "2026-01-25_C7_vs_BTA_W3",
            "short_title": "⚡ Crew 7 W3: #2 Mohamed Double-Double (13 PTS, 11 REB, 5 AST) vs. BTA (Jan 25)",
            "title": "Crew 7 (#2 Mohamed — 13 PTS, 11 REB, 5 AST, STL, BLK) vs. BTA University — Winter '26 Week 3 (Jan 25, 2026)",
            "yt_id": "RnUR9nJojMI",
            "video_path": r"c:\dev\bball_annotation\majestic_crew7\2026-01-25_C7_vs_BTA_W3.mp4",
            "json_path": r"c:\dev\bball_annotation\majestic_crew7\2026-01-25_C7_vs_BTA_W3_full.json",
            "tipoff_sec": 245,
            "cu_team_name": "Crew 7",
            "opp_team_name": "BTA University",
            "cu_record": "Winter '26 Black",
            "opp_record": "Winter '26 Black",
            "cu_jerseys": "Red (#2 Mohamed, #0 Cam, #00 Arman, #8 Nate, #10 Shain, #23 Tharon)",
            "opp_jerseys": "White",
            "cu_h1_hoop": "left",
            "cu_h2_hoop": "right",
            "has_video": True,
            "video_url": "https://storage.googleapis.com/basketball-highlights-store/majestic/2026-01-25_C7_vs_BTA_W3.mp4?v=1080p",
            "final_cu_score": 69,
            "final_opp_score": 86,
        },
        W3_LED_EVENTS,
    ),
    (
        {
            "id": "majestic_2026_01_18_c7_w2",
            "slug": "2026-01-18_C7_vs_Breadwinners_W2",
            "short_title": "🎯 Crew 7 W2: #2 Mohamed 4/4 3PT! (14 PTS, 7 REB, 3 STL, BLK) vs. Breadwinners (Jan 18)",
            "title": "Crew 7 (#2 Mohamed — 14 PTS, 4/4 3PT, 7 REB, 3 STL, 1 BLK) vs. Breadwinners — Winter '26 Week 2 (Jan 18, 2026)",
            "yt_id": "HJJdo9dJ9c0",
            "video_path": r"c:\dev\bball_annotation\majestic_crew7\2026-01-18_C7_vs_Breadwinners_W2.mp4",
            "json_path": r"c:\dev\bball_annotation\majestic_crew7\2026-01-18_C7_vs_Breadwinners_W2_full.json",
            "tipoff_sec": 390,
            "cu_team_name": "Crew 7",
            "opp_team_name": "Breadwinners",
            "cu_record": "Winter '26 Black",
            "opp_record": "Winter '26 Black",
            "cu_jerseys": "Red (#2 Mohamed [White Sleeves + Red Shorts + Cyan Kicks], #00 Arman, #8 Nate, #9 Aaron, #10 Shain, #23 Tharon, #24 Pete)",
            "opp_jerseys": "White/Teal",
            "cu_h1_hoop": "right",
            "cu_h2_hoop": "left",
            "has_video": True,
            "video_url": "https://storage.googleapis.com/basketball-highlights-store/majestic/2026-01-18_C7_vs_Breadwinners_W2.mp4?v=1080p",
            "final_cu_score": 58,
            "final_opp_score": 71,
        },
        W2_LED_EVENTS,
    ),
    (
        {
            "id": "majestic_2026_01_11_c7_w1",
            "slug": "2026-01-11_C7_vs_OutOfShape_W1",
            "short_title": "🏀 Crew 7 W1: Out Of Shape 72, Crew 7 60 (#2 Mohamed 6 PTS, 1× 3PM, 3/3 FT) (Jan 11)",
            "title": "Crew 7 (#2 Mohamed — 6 PTS, 1/1 3PT, 3/3 FT, 3 REB, 1 AST) vs. Out Of Shape — Winter '26 Week 1 (Jan 11, 2026)",
            "yt_id": "lxpzp0i9et8",
            "video_path": "",
            "json_path": r"c:\dev\bball_annotation\majestic_crew7\2026-01-11_C7_vs_OutOfShape_W1_full.json",
            "tipoff_sec": 180,
            "cu_team_name": "Crew 7",
            "opp_team_name": "Out Of Shape",
            "cu_record": "Winter '26 Black",
            "opp_record": "Winter '26 Black",
            "cu_jerseys": "Red (#2 Mohamed, #4 T.R. Smith, #8 Nate, #9 Aaron, #15 Sage, #23 Tharon, #24 Pete)",
            "opp_jerseys": "Black",
            "cu_h1_hoop": "left",
            "cu_h2_hoop": "right",
            "has_video": False,
            "video_url": MO_C7_REEL_GCS,
            "final_cu_score": 60,
            "final_opp_score": 72,
        },
        [
            (1, 3, 18, 22, 920.0, 923.0, "#2 Mohamed", None, False,
             "#2 Mohamed drains a 3-Pointer in the Winter '26 Season Opener! (1/1 3PT, 3/3 FT — 6 PTS, 3 REB, 1 AST)"),
            (2, 1, 45, 55, 2150.0, 2153.0, "#2 Mohamed", None, False,
             "#2 Mohamed goes 3-for-3 from the Free Throw line (100% FT!) vs. Out Of Shape"),
        ],
    ),
]

for cfg, led_rows in C7_CONFIGS:
    fused = build_led_fused_game(cfg, led_rows)
    bundle[cfg["slug"]] = fused
    print(f"Fused {cfg['slug']}: {fused['total_fused_events']} LED-synced events, score {fused['final_cu_score']}-{fused['final_opp_score']}")

with open(BUNDLE_PATH, "w", encoding="utf-8") as f:
    json.dump(bundle, f, indent=2)

print("Successfully fused all 4 Crew 7 Winter '26 games into majestic_games_bundle.json!")
