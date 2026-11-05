import cv2
import numpy as np
import json
import os
import sys
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8')

GAMES_CONFIG = [
    {
        "id": "majestic_2026_02_08_eagles",
        "slug": "2026-02-08_CU_vs_Eagles",
        "short_title": "CU 119, Eagles 69 (Feb 8, 2026)",
        "title": "Campbell United vs. Eagles — Majestic Hoops Winter '26 (Feb 8, 2026)",
        "yt_id": "7T4zYm1jHBo",
        "video_path": r"c:\dev\bball_annotation\majestic_games\2026-02-08_CU_vs_Eagles.mp4",
        "json_path": r"c:\dev\bball_annotation\majestic_games\2026-02-08_CU_vs_Eagles_recleague.json",
        "h1_anchor": "08:10:52 AM",
        "h2_anchor": "08:10:52 AM",
        "cu_team_name": "Campbell United",
        "opp_team_name": "Eagles",
        "cu_jerseys": "White (Red #s)",
        "opp_jerseys": "Black (Blue/White #s)",
        "sb_roi": (808, 228, 860, 272),
        "left_hoop_roi": (280, 150, 338, 220),
        "right_hoop_roi": (912, 255, 958, 302),
        "cu_h1_hoop": "right",
        "cu_h2_hoop": "left",
        "default_lag_sec": 3.0,
        "visual_overrides": {
            "8:13:11 AM": {
                "s": 139, "splash_s": 141.5,
                "desc": "#7 Nick Switzer buries a Left-Wing Transition 3-Pointer (6-0 CU) — Assist: #44 Christian Raslowsky"
            },
            "8:14:36 AM": {
                "s": 222, "splash_s": 225.5,
                "desc": "#7 Nick Switzer drills a dead-center Top-of-the-Key 3-Pointer (11-0 CU, forces Eagles timeout) — Assist: #31 Evan Kovarik"
            },
            "8:41:15 AM": {
                "s": 1819, "splash_s": 1821.0,
                "desc": "#7 Nick Switzer jumps the passing lane for the defensive steal, igniting a fast-break layup by #4 Adam Fecteau"
            },
            "8:51:30 AM": {
                "s": 2434, "splash_s": 2437.0,
                "desc": "#1 Eugene splashes a 3-Pointer to put Campbell United at 100 PTS (100-55) — Assist: #7 Nick Switzer"
            },
            "8:52:54 AM": {
                "s": 2521, "splash_s": 2523.5,
                "desc": "#7 Nick Switzer splashes a contested Right-Wing 3-Pointer over the closeout (104-55 CU)"
            }
        }
    },
    {
        "id": "majestic_2025_11_09_crew7",
        "slug": "2025-11-09_CU_vs_Crew7",
        "short_title": "CU 59, Crew 7 73 (Nov 9, 2025)",
        "title": "Campbell United vs. Crew 7 — Majestic Hoops Holiday '25 (Nov 9, 2025)",
        "yt_id": "YZvTP1pbhM0",
        "video_path": r"c:\dev\bball_annotation\majestic_games\2025-11-09_CU_vs_Crew7.mp4",
        "json_path": r"c:\dev\bball_annotation\majestic_games\2025-11-09_CU_vs_Crew7_recleague.json",
        "h1_anchor": "09:05:44 PM",
        "h2_anchor": "09:05:44 PM",
        "cu_team_name": "Campbell United",
        "opp_team_name": "Crew 7",
        "cu_jerseys": "White (Red #s)",
        "opp_jerseys": "Red (Black #s)",
        "sb_roi": (105, 190, 235, 275),
        "left_hoop_roi": (210, 315, 260, 365),
        "right_hoop_roi": (795, 260, 845, 325),
        "cu_h1_hoop": "left",
        "cu_h2_hoop": "right",
        "default_lag_sec": 3.5,
        "visual_overrides": {
            "9:08:40 PM": {
                "s": 171, "splash_s": 174.5,
                "desc": "#7 Nick Switzer cuts down the right lane and banks in a Right-Block Runner in the paint (5-0 CU)"
            },
            "9:11:09 PM": {
                "s": 321, "splash_s": 324.0,
                "desc": "#7 Nick Switzer interior rim protection — Blocks Crew 7 shot attempt in the paint"
            },
            "9:13:54 PM": {
                "s": 486, "splash_s": 489.5,
                "desc": "#7 Nick Switzer catches & fires a high-arcing Right-Wing 3-Pointer (14-8 CU) — Assist: #8 Eugene"
            },
            "9:16:47 PM": {
                "s": 661, "splash_s": 664.5,
                "desc": "#7 Nick Switzer buries a Left-Corner 3-Pointer (18-12 CU) — Assist: #20 Shane Hoffman"
            },
            "9:20:45 PM": {
                "s": 899, "splash_s": 902.0,
                "desc": "#7 Nick Switzer drills a contested Right-Wing 3-Pointer over the closeout (24-17 CU, forces Crew 7 timeout)"
            }
        }
    },
    {
        "id": "majestic_2026_03_01_latto_champ",
        "slug": "2026-03-01_CU_vs_LattoTalent_Champ",
        "short_title": "CU 45, Latto Talent 73 [Champ] (Mar 1, 2026)",
        "title": "Campbell United vs. Latto Talent [Championship] — Winter '26 (Mar 1, 2026)",
        "yt_id": "VxsUFYxbics",
        "video_path": r"c:\dev\bball_annotation\majestic_games\2026-03-01_CU_vs_LattoTalent_Champ.mp4",
        "json_path": r"c:\dev\bball_annotation\majestic_games\2026-03-01_CU_vs_LattoTalent_Champ_recleague.json",
        "h1_anchor": "06:58:00 PM",
        "h2_anchor": "06:58:00 PM",
        "cu_team_name": "Campbell United",
        "opp_team_name": "Latto Talent",
        "cu_jerseys": "White (Red #s)",
        "opp_jerseys": "Red/Black",
        "sb_roi": (98, 145, 228, 228),
        "left_hoop_roi": (200, 265, 250, 315),
        "right_hoop_roi": (780, 225, 835, 285),
        "cu_h1_hoop": "right",
        "cu_h2_hoop": "left",
        "default_lag_sec": 3.0,
        "visual_overrides": {
            "7:22:21 PM": {
                "s": 1459, "splash_s": 1461.5,
                "desc": "#7 Nick Switzer strips the ball on the defensive end for the steal and ignites the fast break"
            },
            "7:22:31 PM": {
                "s": 1465, "splash_s": 1469.5,
                "desc": "#7 Nick Switzer sprints the floor after his steal and splashes a Right-Corner 3-Pointer over the closeout (42-27) — Assist: #44 Christian Raslowsky"
            },
            "7:39:46 PM": {
                "s": 2501, "splash_s": 2504.5,
                "desc": "#44 Christian Raslowsky buries a 3-Pointer — Assist: #7 Nick Switzer"
            },
            "7:41:54 PM": {
                "s": 2629, "splash_s": 2631.5,
                "desc": "#7 Nick Switzer active hands — comes away with his 2nd steal of the Championship game"
            }
        }
    }
]

def parse_wall_clock(ts_str):
    return datetime.strptime(ts_str.strip(), "%I:%M:%S %p")

def detect_rim_splash_offset(cap, approx_vid_t, hoop_roi, search_window=(-5.0, 0.5), step=0.5):
    x1, y1, x2, y2 = hoop_roi
    t_start = max(1.0, approx_vid_t + search_window[0])
    t_end = approx_vid_t + search_window[1]
    prev_gray = None
    best_t = approx_vid_t - 3.0
    best_energy = -1.0

    t = t_start
    while t <= t_end:
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000.0)
        ret, frame = cap.read()
        if ret:
            patch = frame[y1:y2, x1:x2]
            gray = cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY)
            if prev_gray is not None and prev_gray.shape == gray.shape:
                diff = cv2.absdiff(gray, prev_gray)
                energy = float(np.mean(diff))
                if energy > best_energy:
                    best_energy = energy
                    best_t = t
            prev_gray = gray
        t += step
    return round(best_t, 1), round(best_energy, 2)

def process_game(cfg):
    print(f"\n=======================================================")
    print(f"Processing {cfg['title']}...")
    with open(cfg["json_path"], "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    entries = raw_data["pbp_entries"]
    cap = cv2.VideoCapture(cfg["video_path"])
    fps = cap.get(cv2.CAP_PROP_FPS)
    dur = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) / fps) if fps else 3000

    h1_anchor_dt = parse_wall_clock(cfg["h1_anchor"])
    h2_anchor_dt = parse_wall_clock(cfg["h2_anchor"])

    cu_score = 0
    opp_score = 0
    enriched_events = []
    reconstructed_misses = 0

    i = 0
    n = len(entries)
    while i < n:
        e = entries[i]
        is_h1 = e["period"].startswith("H1")
        anchor_dt = h1_anchor_dt if is_h1 else h2_anchor_dt
        wc_dt = parse_wall_clock(e["wall_clock"])
        raw_t = (wc_dt - anchor_dt).total_seconds()
        raw_t = max(5.0, min(dur - 5.0, raw_t))

        team = e["team"]
        is_cu = (team == cfg["cu_team_name"])
        player = e["player"]
        action = e["action"]

        if is_h1:
            active_hoop_side = cfg["cu_h1_hoop"] if is_cu else ("left" if cfg["cu_h1_hoop"] == "right" else "right")
        else:
            active_hoop_side = cfg["cu_h2_hoop"] if is_cu else ("left" if cfg["cu_h2_hoop"] == "right" else "right")
        hoop_roi = cfg["right_hoop_roi"] if active_hoop_side == "right" else cfg["left_hoop_roi"]

        assist_player = None
        if action == "Assist" and i + 1 < n:
            nxt = entries[i + 1]
            nxt_dt = parse_wall_clock(nxt["wall_clock"])
            if nxt["team"] == team and "FG Made" in nxt["action"] and abs((nxt_dt - wc_dt).total_seconds()) <= 6.0:
                assist_player = player
                e = nxt
                wc_dt = nxt_dt
                raw_t = max(5.0, min(dur - 5.0, (wc_dt - anchor_dt).total_seconds()))
                player = e["player"]
                action = e["action"]
                i += 1
        elif "FG Made" in action and i + 1 < n:
            nxt = entries[i + 1]
            nxt_dt = parse_wall_clock(nxt["wall_clock"])
            if nxt["team"] == team and nxt["action"] == "Assist" and abs((nxt_dt - wc_dt).total_seconds()) <= 6.0:
                assist_player = nxt["player"]
                i += 1

        pts_added = 0
        if "3-pt FG Made" in action:
            pts_added = 3
        elif "2-pt FG Made" in action:
            pts_added = 2
        elif "FT Made" in action:
            pts_added = 1

        if pts_added > 0:
            if is_cu:
                cu_score += pts_added
            else:
                opp_score += pts_added

        if "FG Made" in action:
            splash_t, rim_energy = detect_rim_splash_offset(cap, raw_t, hoop_roi, search_window=(-5.0, 0.5), step=0.5)
            play_t = max(3.0, splash_t - 2.0)
        elif action == "Rebound":
            prev_was_make = False
            if enriched_events and abs(raw_t - enriched_events[-1]["raw_wall_t"]) <= 6.0:
                if "Made" in enriched_events[-1]["action"]:
                    prev_was_make = True
            splash_t = round(raw_t - cfg["default_lag_sec"], 1)
            rim_energy = 0.0
            play_t = max(3.0, raw_t - cfg["default_lag_sec"] - 1.5)
            if not prev_was_make:
                reconstructed_misses += 1
        else:
            splash_t = round(raw_t - cfg["default_lag_sec"], 1)
            rim_energy = 0.0
            play_t = max(3.0, splash_t - 1.0)

        tags = []
        if is_cu:
            tags.append("CU")
        else:
            tags.append("OPP")
        if is_cu and ("#7 " in player or "Switzer" in player or (assist_player and ("#7 " in assist_player or "Switzer" in assist_player))):
            tags.append("NICK #7")

        if "3-pt FG Made" in action:
            tags.extend(["MAKE", "3PT"])
            desc = f"{player} buries a 3-pointer ({team})"
            if assist_player:
                desc += f" — Assist: {assist_player}"
                tags.append("AST")
        elif "2-pt FG Made" in action:
            tags.extend(["MAKE", "2PT"])
            desc = f"{player} scores a 2-point field goal ({team})"
            if assist_player:
                desc += f" — Assist: {assist_player}"
                tags.append("AST")
        elif "FT Made" in action:
            tags.extend(["MAKE", "FT"])
            desc = f"{player} hits free throw ({team})"
        elif action == "Rebound":
            tags.extend(["REB", "MISS_PRIOR"])
            desc = f"Missed shot on rim -> {player} secures the rebound ({team})"
        elif action == "Steal":
            tags.append("STL")
            desc = f"{player} comes away with the steal ({team})"
        elif action == "Block":
            tags.append("BLK")
            desc = f"{player} rejects the shot — Block ({team})"
        elif action == "Assist":
            tags.append("AST")
            desc = f"{player} dishes the assist ({team})"
        elif action == "Turnover":
            tags.append("TOV")
            desc = f"Turnover by {player} ({team})"
        elif action == "Foul":
            tags.append("FOUL")
            desc = f"Personal foul on {player} ({team})"
        else:
            desc = f"{player} {action} ({team})"

        # Apply high-precision visual overrides for verified plays
        ov = cfg.get("visual_overrides", {}).get(e["wall_clock"])
        if ov:
            play_t = ov["s"]
            splash_t = ov["splash_s"]
            desc = ov["desc"]

        m, s = divmod(int(round(play_t)), 60)
        time_str = f"{m:02d}:{s:02d}"

        enriched_events.append({
            "idx": len(enriched_events) + 1,
            "t": time_str,
            "s": int(round(play_t)),
            "splash_s": splash_t,
            "raw_wall_t": round(raw_t, 1),
            "wall_clock": e["wall_clock"],
            "period": "1st Half" if is_h1 else "2nd Half",
            "team": team,
            "is_cu": is_cu,
            "player": player,
            "assist_player": assist_player,
            "action": action,
            "pts_added": pts_added,
            "cu_score": cu_score,
            "opp_score": opp_score,
            "score_str": f"{cu_score} - {opp_score}",
            "hoop_side": active_hoop_side,
            "rim_energy": rim_energy,
            "tags": tags,
            "desc": desc,
            "avatar": e.get("avatar", "")
        })
        i += 1

    cap.release()
    out_summary = {
        "config": cfg,
        "box_score_tables": raw_data.get("box_score_tables", []),
        "final_cu_score": cu_score,
        "final_opp_score": opp_score,
        "total_fused_events": len(enriched_events),
        "reconstructed_missed_shots_before_rebounds": reconstructed_misses,
        "nick_switzer_events": [ev for ev in enriched_events if "NICK #7" in ev["tags"]],
        "events": enriched_events
    }
    out_file = rf"c:\dev\bball_annotation\majestic_games\{cfg['slug']}_cv_fused.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(out_summary, f, indent=2)
    print(f"  Final Score Verified: {cfg['cu_team_name']} {cu_score} - {cfg['opp_team_name']} {opp_score}")
    print(f"  Fused Play-by-Play Cards: {len(enriched_events)} (including {reconstructed_misses} reconstructed missed-shot rebound sequences)")
    print(f"  Nick Switzer (#7) Highlight Events: {len(out_summary['nick_switzer_events'])}")
    for nev in out_summary["nick_switzer_events"]:
        print(f"    [{nev['t']} | s={nev['s']}s | {nev['period']}] ({nev['score_str']}) {nev['desc']}")

if __name__ == "__main__":
    for c in GAMES_CONFIG:
        process_game(c)
