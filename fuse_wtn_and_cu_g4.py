import json
import os
from datetime import datetime, timezone

BUNDLE_PATH = r"c:\dev\bball_annotation\majestic_games_bundle.json"

with open(BUNDLE_PATH, "r", encoding="utf-8") as f:
    bundle = json.load(f)

def parse_iso(ts):
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))

def fmt_wall_clock(ts):
    dt = parse_iso(ts).astimezone()
    return dt.strftime("%I:%M:%S %p").lstrip("0")

def fmt_mmss(sec):
    sec = max(0, int(round(sec)))
    return f"{sec // 60:02d}:{sec % 60:02d}"

def build_box_tables(boxscore, our_team, opp_team, our_rec, opp_rec):
    header = ["Player", "Pts", "FTM", "FGM", "2PM", "3PM", "Reb", "Ast", "Stl", "Blk", "Fls", "T-Fls", "TOs", "PPR"]
    def team_rows(tname):
        rows = [header]
        players = [b for b in boxscore if b.get("team_name") == tname and not b.get("dnp")]
        players.sort(key=lambda x: (int(x.get("points") or 0), int(x.get("rebounds") or 0), int(x.get("assists") or 0)), reverse=True)
        tot = [0]*12
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
            ppr = round(pts + reb * 1.2 + ast * 1.5 + stl * 2.0 + blk * 2.0 - tos * 1.0 - fls * 0.5, 1)
            vals = [pts, ftm, fgm, twopm, threepm, reb, ast, stl, blk, fls, tfls, tos]
            for idx_v, v in enumerate(vals):
                tot[idx_v] += v
            rows.append([pname] + [str(v) for v in vals] + [str(ppr)])
        tot_ppr = round(tot[0] + tot[5]*1.2 + tot[6]*1.5 + tot[7]*2.0 + tot[8]*2.0 - tot[11]*1.0 - tot[9]*0.5, 1)
        rows.append(["Team Totals"] + [str(v) for v in tot] + [str(tot_ppr)])
        return rows

    return [
        [[f"{our_team} ({our_rec})"]],
        team_rows(our_team),
        [[f"{opp_team} ({opp_rec})"]],
        team_rows(opp_team),
    ]

def stat_action_label(s):
    st = s.get("stat_type", "")
    val = int(s.get("value") or 0)
    made = s.get("made")
    pts = int(s.get("points") or 0)
    if st == "shot":
        if val == 3:
            return "3-pt FG Made" if made else "3-pt FG Missed"
        return "2-pt FG Made" if made else "2-pt FG Missed"
    if st == "freethrow":
        return "FT Made" if made else "FT Missed"
    if st in ("rebound", "reb"):
        return "Rebound"
    if st in ("assist", "ast"):
        return "Assist"
    if st in ("steal", "stl"):
        return "Steal"
    if st in ("block", "blk"):
        return "Block"
    if st in ("turnover", "to"):
        return "Turnover"
    if st == "foul":
        return "Foul"
    if "timeout" in st:
        return "Timeout"
    return st.replace("_", " ").title()

def norm_key_type(s):
    st = s.get("stat_type", "")
    val = int(s.get("value") or 0)
    if st == "shot":
        return "3pt" if val == 3 else "2pt"
    if st == "freethrow":
        return "ft"
    if st == "rebound":
        return "reb"
    if st == "assist":
        return "ast"
    if st == "steal":
        return "stl"
    if st == "block":
        return "blk"
    return st

def fuse_majestic_game(cfg):
    with open(cfg["json_path"], "r", encoding="utf-8") as f:
        data = json.load(f)
    boxscore = data.get("boxscore", [])
    pid_map = {}
    for b in boxscore:
        num = b.get("jersey_number")
        num_str = f"#{num} " if num is not None and str(num) != "" else ""
        pid_map[b["player_id"]] = f"{num_str}{b.get('name', 'Player')}".strip()

    raw_logs = [s for s in data.get("statlog", []) if s.get("stat_type") != "dnp" and s.get("period") in (1, 2, 3)]
    raw_logs.sort(key=lambda x: x["logged_at"])

    p1_logs = [s for s in raw_logs if s["period"] == 1]
    p2_logs = [s for s in raw_logs if s["period"] == 2]
    p3_logs = [s for s in raw_logs if s["period"] == 3]

    t1_0 = parse_iso(p1_logs[0]["logged_at"]) if p1_logs else parse_iso(raw_logs[0]["logged_at"])
    t2_0 = parse_iso(p2_logs[0]["logged_at"]) if p2_logs else t1_0
    t3_0 = parse_iso(p3_logs[0]["logged_at"]) if p3_logs else t2_0

    our_team = cfg["cu_team_name"]
    opp_team = cfg["opp_team_name"]

    our_score = 0
    opp_score = 0
    events = []
    overrides = cfg.get("exact_overrides", {})

    n = len(raw_logs)
    i = 0
    ev_idx = 0
    while i < n:
        s = raw_logs[i]
        st = s.get("stat_type", "")
        team = s.get("team_name", "")
        is_our = (team == our_team)
        player = pid_map.get(s.get("player_id")) or s.get("player_name") or team or "Player"
        dt = parse_iso(s["logged_at"])
        per = s.get("period", 1)
        per_label = "1st Half" if per == 1 else ("2nd Half" if per == 2 else "Overtime")

        atk_our = is_our if st != "block" else (not is_our)
        if per == 1:
            vid_s = cfg["p1_first_sec"] + (dt - t1_0).total_seconds() - cfg.get("lag_sec", 3.5)
            hoop_side = cfg["cu_h1_hoop"] if atk_our else ("right" if cfg["cu_h1_hoop"] == "left" else "left")
        elif per == 2 or "p3_first_sec" not in cfg:
            vid_s = cfg["p2_first_sec"] + (dt - t2_0).total_seconds() - cfg.get("lag_sec", 3.5)
            hoop_side = cfg["cu_h2_hoop"] if atk_our else ("right" if cfg["cu_h2_hoop"] == "left" else "left")
        else:
            ot_hoop = cfg.get("cu_ot_hoop", cfg["cu_h2_hoop"])
            vid_s = cfg["p3_first_sec"] + (dt - t3_0).total_seconds() - cfg.get("lag_sec", 3.5)
            hoop_side = ot_hoop if atk_our else ("right" if ot_hoop == "left" else "left")

        # Pair Assist + Made FG within 6s
        assist_player = None
        if st == "assist" and i + 1 < n:
            nxt = raw_logs[i + 1]
            nxt_dt = parse_iso(nxt["logged_at"])
            if nxt.get("team_name") == team and nxt.get("stat_type") == "shot" and nxt.get("made") and abs((nxt_dt - dt).total_seconds()) <= 6.0:
                assist_player = player
                s = nxt
                st = s.get("stat_type", "")
                player = pid_map.get(s.get("player_id")) or s.get("player_name") or team or "Player"
                dt = nxt_dt
                i += 1
        elif st == "shot" and s.get("made") and i + 1 < n:
            nxt = raw_logs[i + 1]
            nxt_dt = parse_iso(nxt["logged_at"])
            if nxt.get("team_name") == team and nxt.get("stat_type") == "assist" and abs((nxt_dt - dt).total_seconds()) <= 6.0:
                assist_player = pid_map.get(nxt.get("player_id")) or nxt.get("player_name") or team or "Player"
                i += 1

        action = stat_action_label(s)
        pts_added = int(s.get("points") or 0)
        if pts_added > 0:
            if is_our:
                our_score += pts_added
            else:
                opp_score += pts_added

        score_str = f"{our_score} - {opp_score}"
        gclock = s.get("clock") or "00:00"
        ktype = norm_key_type(s)

        ov_key = f"P{per}_{gclock}_{ktype}_{player.split()[0]}"
        ov = overrides.get(s.get("id")) or overrides.get(str(s.get("id"))) or overrides.get(ov_key)
        is_verified = bool(ov)
        if ov:
            play_s = int(round(ov["s"]))
            splash_s = float(ov["splash_s"])
            desc = ov["desc"]
            if ov.get("assist_player"):
                assist_player = ov["assist_player"]
            if ov.get("hoop_side"):
                hoop_side = ov["hoop_side"]
        else:
            splash_s = round(max(5.0, vid_s), 1)
            play_s = int(round(max(3.0, splash_s - 2.0)))
            ast_suffix = f" — Assist: {assist_player}" if assist_player else ""
            if pts_added == 3:
                desc = f"{player} splashes a 3-Pointer! ({score_str} {our_team}){ast_suffix} [{gclock} {per_label}]"
            elif pts_added == 2:
                desc = f"{player} scores a 2-PT bucket ({score_str} {our_team}){ast_suffix} [{gclock} {per_label}]"
            elif pts_added == 1:
                desc = f"{player} sinks Free Throw ({score_str} {our_team}) [{gclock} {per_label}]"
            elif ktype == "reb":
                desc = f"{player} grabs the rebound ({team}, {gclock} {per_label})"
            elif ktype == "stl":
                desc = f"{player} comes away with the defensive steal! ({team}, {gclock} {per_label})"
            elif ktype == "blk":
                desc = f"{player} swats the shot attempt! ({team}, {gclock} {per_label})"
            elif ktype == "ast":
                desc = f"{player} dishes an assist ({team}, {gclock} {per_label})"
            else:
                desc = f"{player} — {action} ({team}, {gclock} {per_label})"

        tags = ["CU" if is_our else "OPP"]
        if pts_added == 3:
            tags.extend(["MAKE", "FG_MADE", "3PT"])
        elif pts_added == 2:
            tags.extend(["MAKE", "FG_MADE", "2PT"])
        elif pts_added == 1:
            tags.extend(["MAKE", "FT", "FT_MADE"])
        elif "Missed" in action:
            tags.append("FG_MISS")
        elif ktype == "reb":
            tags.append("REB")
        elif ktype == "stl":
            tags.append("STL")
        elif ktype == "blk":
            tags.append("BLK")
        if assist_player:
            tags.append("AST")
        if "#2 Mo" in player or (assist_player and "#2 Mo" in assist_player):
            tags.append("MO_HIGHLIGHT")

        ev_idx += 1
        events.append({
            "idx": ev_idx,
            "t": fmt_mmss(play_s),
            "s": play_s,
            "splash_s": splash_s,
            "raw_wall_t": round((dt - t1_0).total_seconds(), 1),
            "wall_clock": fmt_wall_clock(s["logged_at"]),
            "game_clock": gclock,
            "period": per_label,
            "team": team,
            "is_cu": is_our,
            "player": player,
            "assist_player": assist_player,
            "action": action,
            "pts_added": pts_added,
            "cu_score": our_score,
            "opp_score": opp_score,
            "score_str": score_str,
            "hoop_side": hoop_side,
            "rim_energy": 9.5 if pts_added > 0 else 0.0,
            "tags": tags,
            "desc": desc,
            "avatar": "",
            "statlog_id": s.get("id"),
            "isMajesticVerified": True
        })
        i += 1

    if our_team == "WeTheNorth":
        mo_evs = [e for e in events if ("#2 Mo" in e["player"] or (e.get("assist_player") and "#2 Mo" in e["assist_player"])) and (e["pts_added"] > 0 or e["action"] in ("Block", "Steal", "Assist", "Rebound"))]
        other_wtn_makes = [e for e in events if e["is_cu"] and e["pts_added"] >= 2 and e not in mo_evs]
        cu_highlights = mo_evs + other_wtn_makes[:12]
        top5 = [e for e in mo_evs if e["pts_added"] >= 2 or e["action"] in ("Block", "Steal", "FT Made")][:5]
        if len(top5) < 5:
            for e in other_wtn_makes:
                if e not in top5:
                    top5.append(e)
                if len(top5) == 5:
                    break
    else:
        cu_highlights = [e for e in events if e["is_cu"] and (e["pts_added"] >= 2 or e["action"] in ("Block", "Steal"))]
        if cfg.get("top5_statlog_ids"):
            by_sid = {e.get("statlog_id"): e for e in events}
            top5 = [by_sid[sid] for sid in cfg["top5_statlog_ids"] if sid in by_sid]
        else:
            ot_3s = [e for e in cu_highlights if e["period"] in ("OT", "Overtime") and e["pts_added"] == 3]
            reg_3s = [e for e in cu_highlights if e["pts_added"] == 3 and e not in ot_3s]
            top5 = (ot_3s + reg_3s + cu_highlights)[:5]

    box_tables = build_box_tables(boxscore, our_team, opp_team, cfg["cu_record"], cfg["opp_record"])

    return {
        "config": {
            "id": cfg["id"],
            "slug": cfg["slug"],
            "short_title": cfg["short_title"],
            "title": cfg["title"],
            "yt_id": cfg["yt_id"],
            "video_path": cfg["video_path"],
            "json_path": cfg["json_path"],
            "p1_first_sec": cfg["p1_first_sec"],
            "cu_team_name": our_team,
            "opp_team_name": opp_team,
            "cu_record": cfg["cu_record"],
            "opp_record": cfg["opp_record"],
            "cu_jerseys": cfg["cu_jerseys"],
            "opp_jerseys": cfg["opp_jerseys"],
            "cu_h1_hoop": cfg["cu_h1_hoop"],
            "cu_h2_hoop": cfg["cu_h2_hoop"],
            "default_lag_sec": cfg.get("lag_sec", 3.5),
            "has_video": cfg["has_video"],
            "video_url": cfg["video_url"],
            "tipoff_sec": cfg["tipoff_sec"],
            "tipoff_mmss": fmt_mmss(cfg["tipoff_sec"]),
            "mo_reel_url": cfg.get("mo_reel_url", ""),
            "cu_reel": cfg.get("cu_reel", ""),
            "team_top5_reel": cfg.get("team_top5_reel", "")
        },
        "box_score_tables": box_tables,
        "final_cu_score": cfg["final_cu_score"],
        "final_opp_score": cfg["final_opp_score"],
        "total_fused_events": len(events),
        "reconstructed_missed_shots_before_rebounds": sum(1 for e in events if "FG_MISS" in e["tags"]),
        "top5_team_events": top5,
        "cu_highlight_events": cu_highlights,
        "events": events
    }

MO_REEL_GCS = "https://storage.googleapis.com/basketball-highlights-store/majestic/reels/2026-11-01_WTN_Mo_Highlight_Reel.mp4?v=1080p3"

CONFIGS = [
    {
        "id": "majestic_2026_10_18_wtn_g1",
        "slug": "2026-10-18_WTN_vs_OTFSelect_G1",
        "short_title": "🍁 WTN G1: OTF Select 67, WeTheNorth 43 (Oct 18, 2026)",
        "title": "WeTheNorth (#2 Mo) vs. OTF Select — Holiday '26 Game 1 (Oct 18, 2026)",
        "yt_id": "3cWe-us_Kv8",
        "video_path": r"c:\dev\bball_annotation\majestic_wtn\2026-10-18_WTN_vs_OTFSelect_G1.mp4",
        "json_path": r"c:\dev\bball_annotation\majestic_wtn\2026-10-18_WTN_vs_OTFSelect_G1_full.json",
        "p1_first_sec": 197.0,
        "p2_first_sec": 1742.0,
        "tipoff_sec": 177,
        "lag_sec": 3.0,
        "cu_team_name": "WeTheNorth",
        "opp_team_name": "OTF Select",
        "cu_record": "0-1 D6",
        "opp_record": "1-0 D6",
        "cu_jerseys": "White (#2 Mo, #26 Abadir, #27 Graeme, #28 Ahmed, #29 Deeno, #30 Abdullahi)",
        "opp_jerseys": "Black",
        "cu_h1_hoop": "right",
        "cu_h2_hoop": "left",
        "has_video": True,
        "video_url": "https://storage.googleapis.com/basketball-highlights-store/majestic/2026-10-18_WTN_vs_OTFSelect_G1.mp4",
        "mo_reel_url": MO_REEL_GCS,
        "cu_reel": MO_REEL_GCS,
        "team_top5_reel": MO_REEL_GCS,
        "final_cu_score": 43,
        "final_opp_score": 67,
        "exact_overrides": {
            "P1_0:10_ft_#2": {
                "s": 1595, "splash_s": 1598.0,
                "desc": "#2 Mo calmly sinks Free Throws at end of 1st Half (19-28 WeTheNorth)"
            },
            "P2_20:00_ft_#2": {
                "s": 1740, "splash_s": 1743.0,
                "desc": "#2 Mo converts technical Free Throw to open the 2nd Half (3/3 FT, 100% FT + 4 REB)"
            }
        }
    },
    {
        "id": "majestic_2026_10_25_wtn_g2",
        "slug": "2026-10-25_WTN_vs_NewAvengers_G2",
        "short_title": "🍁 WTN G2: New Avengers 66, WeTheNorth 61 (#2 Mo 3/3 FG, 7 PTS, 7 REB)",
        "title": "WeTheNorth (#2 Mo: 7 PTS on 3/3 FG, 7 REB, 1 AST, 1 STL) vs. New Avengers — Game 2 (Oct 25, 2026)",
        "yt_id": "HEvYhrBORTc",
        "video_path": r"c:\dev\bball_annotation\majestic_wtn\2026-10-25_WTN_vs_NewAvengers_G2.mp4",
        "json_path": r"c:\dev\bball_annotation\majestic_wtn\2026-10-25_WTN_vs_NewAvengers_G2_full.json",
        "p1_first_sec": 729.0,
        "p2_first_sec": 2277.0,
        "tipoff_sec": 716,
        "lag_sec": 3.5,
        "cu_team_name": "WeTheNorth",
        "opp_team_name": "New Avengers",
        "cu_record": "0-2 D6",
        "opp_record": "1-1 D6",
        "cu_jerseys": "Red (#2 Mo, #16 Naz, #27 Graeme, #29 Deeno, #30 Abdullahi, #33 Hamza, #34 Metals)",
        "opp_jerseys": "White/Grey",
        "cu_h1_hoop": "left",
        "cu_h2_hoop": "right",
        "has_video": True,
        "video_url": "https://storage.googleapis.com/basketball-highlights-store/majestic/2026-10-25_WTN_vs_NewAvengers_G2.mp4?v=1080p",
        "mo_reel_url": MO_REEL_GCS,
        "cu_reel": MO_REEL_GCS,
        "team_top5_reel": MO_REEL_GCS,
        "final_cu_score": 61,
        "final_opp_score": 66,
        "exact_overrides": {
            "P1_12:11_2pt_#2": {
                "s": 1181, "splash_s": 1185.0,
                "desc": "🔥 #2 Mo slashes down the left lane in red and finishes a tough runner in traffic! (1/1 FG)"
            },
            "P1_11:59_reb_#2": {
                "s": 1199, "splash_s": 1200.5,
                "desc": "💪 #2 Mo skies for the defensive rebound and immediately pushes the break coast-to-coast!"
            },
            "P1_11:50_3pt_#2": {
                "s": 1205, "splash_s": 1208.5,
                "desc": "🎯 #2 Mo pulls up in transition on the left wing and splashes a 3-Pointer! (5 straight PTS in 21 seconds!)"
            },
            "P1_6:44_2pt_#2": {
                "s": 1578, "splash_s": 1581.5,
                "desc": "⚡ #2 Mo attacks the left paint and scores his 3rd straight bucket! (7 PTS on 3/3 FG — 100% FG!)"
            },
            "P1_6:07_stl_#2": {
                "s": 1616, "splash_s": 1619.5,
                "desc": "🔒 #2 Mo strips the ball at the top of the key for the defensive steal and ignites the fast break!"
            },
            "P2_6:07_reb_#2": {
                "s": 3269, "splash_s": 3275.0,
                "desc": "🚀 #2 Mo snags his 7th rebound, sprints coast-to-coast down the middle, and dishes in the paint!"
            },
            "P2_3:05_2pt_#34": {
                "s": 3444, "splash_s": 3448.0,
                "desc": "🏀 #34 Metals finishes inside on the break! (Boxscore Assist credited to #2 Mo at 3:05 LED)"
            }
        }
    },
    {
        "id": "majestic_2026_11_01_wtn_g3",
        "slug": "2026-11-01_WTN_vs_CrunchTime_G3",
        "short_title": "🔥 WTN G3: #2 Mo 15 PTS (5× 3PM, 5 REB, 1 BLK) vs. Crunch Time (Nov 1, 2026)",
        "title": "WeTheNorth (#2 Mo 15 PTS on 5/10 3PT + 5 REB + 1 BLK!) vs. Crunch Time — Game 3 (Nov 1, 2026)",
        "yt_id": "r0n2sCGhd78",
        "video_path": r"c:\dev\bball_annotation\majestic_wtn\2026-11-01_WTN_vs_CrunchTime_G3.mp4",
        "json_path": r"c:\dev\bball_annotation\majestic_wtn\2026-11-01_WTN_vs_CrunchTime_G3_full.json",
        "p1_first_sec": 715.0,
        "p2_first_sec": 2274.0,
        "tipoff_sec": 672,
        "lag_sec": 3.5,
        "cu_team_name": "WeTheNorth",
        "opp_team_name": "Crunch Time",
        "cu_record": "0-3 D6",
        "opp_record": "2-1 D6",
        "cu_jerseys": "White (#2 Mo, #16 Naz, #27 Graeme, #28 Ahmed, #29 Deeno, #31 Dan, #33 Hamza, #34 Metals)",
        "opp_jerseys": "Red",
        "cu_h1_hoop": "left",
        "cu_h2_hoop": "right",
        "has_video": True,
        "video_url": "https://storage.googleapis.com/basketball-highlights-store/majestic/2026-11-01_WTN_vs_CrunchTime_G3.mp4?v=1080p",
        "mo_reel_url": MO_REEL_GCS,
        "cu_reel": MO_REEL_GCS,
        "team_top5_reel": MO_REEL_GCS,
        "final_cu_score": 60,
        "final_opp_score": 67,
        "exact_overrides": {
            "P1_15:00_blk_#2": {
                "s": 1012, "splash_s": 1016.0,
                "desc": "🛡️ #2 Mo rotates over in the right paint and swats away the Crunch Time layup attempt! (BLK @ 15:00 LED)"
            },
            "P2_12:54_3pt_#2": {
                "s": 2721, "splash_s": 2726.0,
                "desc": "🎯 #2 Mo (White #2) catches on the right wing and buries 3-Pointer #1 of 5! (Assist: #33 Hamza @ 12:54 LED)"
            },
            "P2_6:54_reb_#2": {
                "s": 3089, "splash_s": 3091.5,
                "desc": "💪 #2 Mo cleans the defensive glass and ignites the coast-to-coast break! (6:54 LED)"
            },
            "P2_6:45_3pt_#2": {
                "s": 3093, "splash_s": 3098.5,
                "desc": "🔥 #2 Mo goes coast-to-coast and splashes 3-Pointer #2 of 5 from the right wing! (6:45 LED)"
            },
            "P2_6:18_3pt_#2": {
                "s": 3121, "splash_s": 3126.5,
                "desc": "🔥🔥 BACK-TO-BACK TRIPLES! #2 Mo drills 3-Pointer #3 of 5 from top of the key! (2 3s in 27s, Assist: #29 Deeno @ 6:18 LED)"
            },
            "P2_5:53_3pt_#2": {
                "s": 3146, "splash_s": 3152.0,
                "desc": "🌋 HEAT CHECK! #2 Mo crosses over into a pull-up right-wing 3-Pointer #4 of 5 & high-fives! (3 straight triples in 52s @ 5:53 LED!)"
            },
            "P2_0:00_3pt_#2": {
                "s": 3669, "splash_s": 3673.5,
                "desc": "👑 CINCO DE MO! #2 Mo drains contested right-wing 3-Pointer #5 of 5 to finish with 15 PTS (5/10 3PT), 5 REB & 1 BLK! (Assist: #16 Naz)"
            }
        }
    },
    {
        "id": "majestic_2026_11_08_wtn_g4",
        "slug": "2026-11-08_WTN_vs_DomainExpansion_G4",
        "short_title": "🏆 WTN G4: WeTheNorth 55, Domain Expansion 53 [1080p WIN!] (Nov 8, 2026)",
        "title": "WeTheNorth 55, Domain Expansion 53 — Game 4 Victory (#2 Mo Two-Way Showcase, #34 Metals 20 PTS, #33 Hamza 18 PTS, Nov 8, 2026)",
        "yt_id": "qyTJnSw3kSQ",
        "video_path": r"c:\dev\bball_annotation\majestic_wtn\2026-11-08_WTN_vs_DomainExpansion_G4.mp4",
        "json_path": r"c:\dev\bball_annotation\majestic_wtn\2026-11-08_WTN_vs_DomainExpansion_G4_full.json",
        "p1_first_sec": 1300.8,
        "p2_first_sec": 2717.5,
        "tipoff_sec": 1288,
        "lag_sec": 4.5,
        "cu_team_name": "WeTheNorth",
        "opp_team_name": "Domain Expansion",
        "cu_record": "1-3 D6",
        "opp_record": "1-3 D6",
        "cu_jerseys": "Red (#2 Mo, #16 Naz, #27 Graeme, #28 Ahmed, #29 Deeno, #31 Dan, #33 Hamza, #34 Metals)",
        "opp_jerseys": "White (#4 Ankur, #5 Brandon, #6 Ty, #18 Muyi, #21 Jobin, #24 Sean, #25 Muji, #45 Kai)",
        "cu_h1_hoop": "right",
        "cu_h2_hoop": "left",
        "has_video": True,
        "video_url": "https://storage.googleapis.com/basketball-highlights-store/majestic/2026-11-08_WTN_vs_DomainExpansion_G4.mp4",
        "mo_reel_url": MO_REEL_GCS,
        "cu_reel": MO_REEL_GCS,
        "team_top5_reel": MO_REEL_GCS,
        "final_cu_score": 55,
        "final_opp_score": 53,
        "exact_overrides": {
            761388: {"s": 1292, "splash_s": 1296.0, "desc": "🏀 #34 Metals wins the opening sequence and finishes at the right rim! (2-0 WeTheNorth) [19:49 1st Half]"},
            761416: {"s": 1391, "splash_s": 1395.5, "desc": "🏀 #34 Metals attacks the right lane and scores! (4-0 WeTheNorth) [18:11 1st Half]"},
            761425: {"s": 1426, "splash_s": 1430.0, "desc": "🏀 #33 Hamza drives right and finishes off the glass! (6-0 WeTheNorth) [17:36 1st Half]"},
            761439: {"s": 1468, "splash_s": 1472.5, "desc": "🔥 #34 Metals finishes inside to extend the opening run to 8-0 WeTheNorth! [16:54 1st Half]"},
            761448: {"s": 1496, "splash_s": 1500.5, "desc": "🎯 #33 Hamza buries a right-wing 3-Pointer for an 11-0 start! [16:25 1st Half]"},
            761463: {"s": 1577, "splash_s": 1581.5, "desc": "🔥 #2 Mo slashes into the right paint in Red #2 and finishes a contested 2-PT runner to cap WeTheNorth's 13-0 opening run! [15:05 1st Half]"},
            761522: {"s": 1881, "splash_s": 1885.5, "desc": "🏀 #31 Dan finishes strong in the right paint! (16-7 WeTheNorth) [10:02 1st Half]"},
            761561: {"s": 2013, "splash_s": 2017.0, "desc": "🏀 #34 Metals converts at the right rim! (18-10 WeTheNorth) [7:51 1st Half]"},
            761586: {"s": 2195, "splash_s": 2199.0, "desc": "🎯 #33 Hamza splashes his 2nd 3-Pointer of the half! (21-14 WeTheNorth) [5:54 1st Half]"},
            761595: {"s": 2257, "splash_s": 2261.5, "desc": "🏀 #31 Dan scores inside on the right block! (23-15 WeTheNorth) [4:52 1st Half]"},
            761605: {"s": 2299, "splash_s": 2303.5, "desc": "💪 #31 Dan powers home back-to-back paint buckets! (25-15 WeTheNorth) [4:11 1st Half]"},
            761621: {"s": 2418, "splash_s": 2423.0, "assist_player": "#2 Mo", "desc": "🎯 #2 Mo dishes on the right perimeter to #33 Hamza, who splashes a deep 3-Pointer! (28-17 WeTheNorth — Assist: #2 Mo) [2:11 1st Half]"},
            761640: {"s": 2532, "splash_s": 2536.5, "desc": "🏀 #34 Metals finishes a tough drive in traffic! (30-22 WeTheNorth) [1:26 1st Half]"},
            761643: {"s": 2581, "splash_s": 2586.0, "desc": "🔥 #33 Hamza drains his 4th 3-Pointer to give WeTheNorth a 33-24 halftime lead! [0:37 1st Half]"},
            761667: {"s": 2771, "splash_s": 2774.5, "hoop_side": "right", "desc": "🔒 #34 Metals jumps the passing lane for the defensive steal! [18:52 2nd Half]"},
            761671: {"s": 2804, "splash_s": 2808.5, "desc": "🏀 #33 Hamza finishes at the left rim to open 2nd-half scoring! (35-26 WeTheNorth) [18:18 2nd Half]"},
            761673: {"s": 2815, "splash_s": 2819.5, "desc": "⚡ #34 Metals scores in transition at the left basket! (37-26 WeTheNorth) [18:09 2nd Half]"},
            761707: {"s": 2959, "splash_s": 2963.5, "desc": "🎯 #34 Metals steps into a left-wing 3-Pointer! (40-29 WeTheNorth) [16:35 2nd Half]"},
            761713: {"s": 3017, "splash_s": 3021.0, "desc": "🏀 #31 Dan finishes strong inside (4/4 2PT)! (42-32 WeTheNorth) [15:38 2nd Half]"},
            761738: {"s": 3126, "splash_s": 3130.5, "desc": "🏀 #34 Metals slashes down the left lane for two! (44-32 WeTheNorth) [13:49 2nd Half]"},
            761740: {"s": 3141, "splash_s": 3145.0, "hoop_side": "right", "desc": "🛡️ #34 Metals swats away Domain Expansion's shot in the right paint! [13:34 2nd Half]"},
            761747: {"s": 3180, "splash_s": 3183.5, "desc": "💪 #2 Mo skies for the defensive rebound and outlets to ignite the break! [12:56 2nd Half]"},
            761748: {"s": 3187, "splash_s": 3191.5, "desc": "🎯 #27 Graeme buries a big left-wing 3-Pointer right off #2 Mo's defensive board! (47-32 WeTheNorth) [12:48 2nd Half]"},
            761755: {"s": 3210, "splash_s": 3214.0, "hoop_side": "right", "desc": "🛡️ #2 Mo rotates into the right paint and SWATS away Domain Expansion's layup attempt! (BLK @ 12:26 2nd Half)"},
            761760: {"s": 3219, "splash_s": 3223.0, "desc": "💪 #2 Mo cleans the defensive glass right after his block! [12:17 2nd Half]"},
            761765: {"s": 3242, "splash_s": 3245.5, "desc": "🎯 #2 Mo calmly sinks the Free Throw at the left stripe! (48-32 WeTheNorth) [11:54 2nd Half]"},
            761772: {"s": 3278, "splash_s": 3282.5, "desc": "🔥 #34 Metals drills his 2nd 3-Pointer (team-high 20 PTS, 8 REB)! (51-34 WeTheNorth) [11:18 2nd Half]"},
            761837: {"s": 3668, "splash_s": 3671.5, "hoop_side": "right", "desc": "🔒 #34 Metals comes up with a clutch late-game steal (51-45)! [5:37 2nd Half]"},
            761884: {"s": 3920, "splash_s": 3924.0, "desc": "🧊 CLUTCH FT! Clinging to a 51-50 lead, #31 Dan sinks Free Throw #1 (52-50 WeTheNorth) [2:01 2nd Half]"},
            761888: {"s": 3932, "splash_s": 3936.5, "desc": "🧊 CLUTCH FT! #31 Dan drains both Free Throws for a 53-50 WeTheNorth lead! [2:01 2nd Half]"},
            761897: {"s": 4084, "splash_s": 4088.0, "desc": "🧊 CRUNCH-TIME FT! #31 Dan (11 PTS, 5 REB) hits a massive Free Throw for 54-50 WeTheNorth!"},
            761906: {"s": 4228, "splash_s": 4232.0, "desc": "🏆 GAME-SEALING FT! #33 Hamza (18 PTS, 4× 3PM) sinks the Free Throw to ice WeTheNorth's 55-53 Victory!"}
        }
    },
    {
        "id": "majestic_2026_11_08_cu_ricecookers_g4",
        "slug": "2026-11-08_CU_vs_Ricecookers_G4",
        "short_title": "🏆 Game 4: CU 66, Ricecookers 63 [OT WIN! 4-0 D2] (Nov 8, 2026)",
        "title": "Campbell United 66, Ricecookers 63 (OT) — #44 Christian 61-61 Buzzer 3PT + #20 Shane OT Winner! (4-0 D2, Nov 8, 2026)",
        "yt_id": "R8rJLAbmVV8",
        "video_path": r"c:\dev\bball_annotation\majestic_oct2026\2026-11-08_CU_vs_Ricecookers_G4.mp4",
        "json_path": r"c:\dev\bball_annotation\majestic_oct2026\2026-11-08_CU_vs_Ricecookers_G4_full.json",
        "p1_first_sec": 303.5,
        "p2_first_sec": 1838.5,
        "p3_first_sec": 4128.5,
        "tipoff_sec": 285,
        "lag_sec": 3.5,
        "cu_team_name": "Campbell United",
        "opp_team_name": "Ricecookers",
        "cu_record": "4-0 D2",
        "opp_record": "3-1 D2",
        "cu_jerseys": "White (#4 Adam, #9 Aaron, #12 Corey, #16 Chris, #20 Shane, #22 Matt, #24 George, #44 Christian)",
        "opp_jerseys": "Black/Navy (#3 Dustin, #7 Nate, #10 Mike, #11 Dylan, #12 AJ, #34 Aaron, #42 Yves, #99 Binh)",
        "cu_h1_hoop": "left",
        "cu_h2_hoop": "right",
        "cu_ot_hoop": "right",
        "has_video": True,
        "video_url": "https://storage.googleapis.com/basketball-highlights-store/majestic/2026-11-08_CU_vs_Ricecookers_G4.mp4",
        "cu_reel": "https://storage.googleapis.com/basketball-highlights-store/majestic/reels/2026-11-08_CU_vs_Ricecookers_G4_OT_Win_Reel.mp4?v=1080p1",
        "team_top5_reel": "https://storage.googleapis.com/basketball-highlights-store/majestic/reels/2026-11-08_CU_vs_Ricecookers_G4_OT_Win_Reel.mp4?v=1080p1",
        "final_cu_score": 66,
        "final_opp_score": 63,
        "top5_statlog_ids": [767392, 767320, 767281, 767369, 767104],
        "exact_overrides": {
            766395: {
                "s": 298, "splash_s": 300.0,
                "desc": "🎯 #4 Adam Fecteau splashes the game's opening 3-Pointer from the left wing! (3-0 Campbell United) — Assist: #20 Shane Hoffman [19:42 1st Half]"
            },
            766422: {
                "s": 382, "splash_s": 383.2,
                "desc": "🏀 #44 Christian Raslowsky elevates in the left lane for his first bucket! (5-4 Campbell United) [18:16 1st Half]"
            },
            766447: {
                "s": 450, "splash_s": 451.5,
                "desc": "🏀 #16 Chris attacks inside at the left hoop and finishes strong! (8-6 Campbell United) [16:58 1st Half]"
            },
            766482: {
                "s": 567, "splash_s": 569.0,
                "desc": "🏀 #44 Christian Raslowsky finishes inside off #16 Chris's interior pass! (10-8 Campbell United) [15:12 1st Half]"
            },
            766488: {
                "s": 597, "splash_s": 598.5, "hoop_side": "right",
                "desc": "🔒 #4 Adam Fecteau strips the ball on the perimeter and ignites the fast break! (10-8 Campbell United) [14:52 1st Half]"
            },
            766496: {
                "s": 608, "splash_s": 610.0,
                "desc": "🔥 #44 Christian Raslowsky attacks the left lane and finishes high off the glass! (12-8 Campbell United) [14:34 1st Half]"
            },
            766504: {
                "s": 630, "splash_s": 631.0, "hoop_side": "right",
                "desc": "🚫 #20 Shane Hoffman elevates in the right paint for a huge rim-protecting BLOCK! (12-8 Campbell United) [14:14 1st Half]"
            },
            766567: {
                "s": 812, "splash_s": 814.0, "assist_player": "#4 Adam Fecteau",
                "desc": "🏀 #9 Aaron finishes inside off #4 Adam Fecteau's pass! (14-10 Campbell United) [11:06 1st Half]"
            },
            766584: {
                "s": 861, "splash_s": 862.5,
                "desc": "⚡ #4 Adam Fecteau slashes to the left hoop and scores! (16-10 Campbell United) [10:19 1st Half]"
            },
            766608: {
                "s": 963, "splash_s": 965.0,
                "desc": "💪 #44 Christian Raslowsky scores in the paint to push the lead to 6! (18-12 Campbell United) [8:38 1st Half]"
            },
            766673: {
                "s": 1163, "splash_s": 1165.0,
                "desc": "🏀 #16 Chris drives the left lane and scores in traffic! (21-17 Campbell United) [5:12 1st Half]"
            },
            766724: {
                "s": 1400, "splash_s": 1402.0,
                "desc": "🎯 #22 Matt Mocherman buries a high-arcing 3-Pointer! (26-22 Campbell United) — Assist: #44 Christian Raslowsky [2:41 1st Half]"
            },
            766740: {
                "s": 1573, "splash_s": 1574.8,
                "desc": "⚡ #22 Matt Mocherman sprints coast-to-coast to beat the 1st-Half buzzer with a fast-break layup! (28-29) [0:00 1st Half]"
            },
            766828: {
                "s": 1891, "splash_s": 1893.0,
                "desc": "🏀 #9 Aaron finishes inside off #44 Christian Raslowsky's pass! (32-29 Campbell United) [18:56 2nd Half]"
            },
            766898: {
                "s": 2100, "splash_s": 2101.8, "hoop_side": "left",
                "desc": "🔒 #24 George jumps the passing lane for the defensive steal! (32-31 Campbell United) [15:30 2nd Half]"
            },
            766910: {
                "s": 2121, "splash_s": 2122.8,
                "desc": "💪 AND-ONE! #44 Christian Raslowsky powers through contact at the right rim! (34-31 Campbell United) [14:52 2nd Half]"
            },
            766937: {
                "s": 2224, "splash_s": 2225.8, "hoop_side": "left",
                "desc": "🔒 #24 George comes away with his 2nd steal of the half! (35-33 Campbell United) [13:18 2nd Half]"
            },
            767020: {
                "s": 2520, "splash_s": 2522.0,
                "desc": "🎯 #12 Corey Randolph rises over the contest and drills a 3-Pointer! (38-44 Campbell United) — Assist: #4 Adam Fecteau [9:44 2nd Half]"
            },
            767072: {
                "s": 2697, "splash_s": 2698.5,
                "desc": "🏀 #24 George finishes at the right rim off #16 Chris's dish! (40-46 Campbell United) [6:35 2nd Half]"
            },
            767075: {
                "s": 2703, "splash_s": 2704.5, "hoop_side": "left",
                "desc": "🔒 #44 Christian Raslowsky picks off the pass and ignites a coast-to-coast break! [6:25 2nd Half]"
            },
            767077: {
                "s": 2709, "splash_s": 2711.5,
                "desc": "⚡ #44 Christian Raslowsky goes coast-to-coast off the steal and finishes in the right lane! (42-46 Campbell United)"
            },
            767104: {
                "s": 2837, "splash_s": 2838.5,
                "desc": "🔥 #4 Adam Fecteau answers immediately with a clutch pull-up 3-Pointer! (45-49, 10 PTS / 4 AST / 2 STL) [5:46 2nd Half]"
            },
            767144: {
                "s": 3039, "splash_s": 3040.8, "hoop_side": "left",
                "desc": "🔒 #4 Adam Fecteau swipes a clutch late-game steal! (46-49) [2:17 2nd Half]"
            },
            767150: {
                "s": 3123, "splash_s": 3124.5,
                "desc": "🏀 #24 George finishes inside off #4 Adam Fecteau's drive-and-dish dime! (48-51 with 1:00 left)"
            },
            767223: {
                "s": 3635, "splash_s": 3636.5,
                "desc": "💪 #44 Christian Raslowsky powers through the paint to cut the deficit to 1! (53-54 Campbell United)"
            },
            767257: {
                "s": 3752, "splash_s": 3754.0,
                "desc": "🔥 #9 Aaron scores a huge crunch-time bucket off #4 Adam Fecteau's feed! (55-56 Campbell United)"
            },
            767281: {
                "s": 3891, "splash_s": 3892.5,
                "desc": "🌋 CLUTCH TRIPLE #1! Down 5 in the final seconds, #44 Christian Raslowsky drains a deep contested left-wing 3-Pointer over #11! (58-60)"
            },
            767320: {
                "s": 4053, "splash_s": 4055.0,
                "desc": "🚨 MIRACLE AT THE HORN!! #44 Christian Raslowsky (23 PTS, 14 REB) sprints coast-to-coast and splashes the BUZZER-BEATING 3-POINTER at 0:00 to tie it 61-61 & force Overtime!!"
            },
            767351: {
                "s": 4196, "splash_s": 4197.0, "hoop_side": "left",
                "desc": "🛡️ OVERTIME REJECTION! #16 Chris skies at the left rim to swat away Ricecookers' layup attempt (tied 61-61 in OT)!"
            },
            767369: {
                "s": 4247, "splash_s": 4248.8,
                "desc": "🔥 GO-AHEAD OT BUCKET! #16 Chris drives the right baseline and scores off the glass for the 63-61 Overtime lead!"
            },
            767392: {
                "s": 4372, "splash_s": 4373.8,
                "desc": "👑 OVERTIME GAME-WINNER!! Tied 63-63, #20 Shane Hoffman buries the rainbow 3-Pointer (Assist: #44 Christian Raslowsky) + CU seals the final buzzer stop for 66-63 (4-0 D2)!!"
            }
        }
    }
]

for cfg in CONFIGS:
    fused = fuse_majestic_game(cfg)
    bundle[cfg["slug"]] = fused
    print(f"Fused {cfg['slug']}: {fused['total_fused_events']} events, {len(fused['cu_highlight_events'])} highlights, top5={len(fused['top5_team_events'])}, score {fused['final_cu_score']}-{fused['final_opp_score']}")

with open(BUNDLE_PATH, "w", encoding="utf-8") as f:
    json.dump(bundle, f, indent=2)

print("Updated majestic_games_bundle.json successfully!")
