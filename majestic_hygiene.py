"""
majestic_hygiene.py — System-Level Majestic Statlog Sanitizer, Possession-Imputed
True Shooting Estimator, Scorer Reliability Gate, and Tier-Weighted Stint Solver (v2.3).

Addresses 5 Systemic Failure Modes discovered on film & raw JSON audits:
1. Null-Period DNP Timeline Traps (`period: null` mixed into `statlog`).
2. Fat-Finger Double-Tap Phantom Misses (same player `MISS -> MAKE` <=3s with no rebound between).
3. Unpaused-Timer `0:00` Clock Overruns (e.g., 46 events at `0:00` in CU G4 P2, 31 in LT Wk4, 39 in LT Wk2)
   repaired via `logged_at` Dead-Ball-Stripped Active Clock reconstruction.
4. Unlogged Missed Shots (`OrphanOppDREB`: opponent DREBs with >8.5s since any logged miss)
   repaired at the team level via Possession-Imputed True FGA / FG% / eFG% bounds.
5. Inconsistent Turnover & Sub Tracking (`TOV` reliability gate >=10 combined TOVs;
   Tier-2 vs Tier-3 soft-prior event weights + >=3.0m exposure gate in stint solving).
"""

import json
from collections import defaultdict
from datetime import datetime


def parse_clk(c):
    if not c or ":" not in str(c):
        return 0
    a, b = str(c).split(":")[:2]
    try:
        return int(a) * 60 + int(float(b))
    except Exception:
        return 0


def raw_elapsed(per, clk):
    p = int(per or 1)
    r = parse_clk(clk)
    if p == 1:
        return max(0, min(1200, 1200 - r))
    if p == 2:
        return 1200 + max(0, min(1200, 1200 - r))
    return 2400 + (p - 3) * 120 + max(0, min(120, 120 - r))


def parse_iso(ts):
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


def norm_name(jersey, name):
    j = str(jersey or "").strip()
    nm = (name or "").strip()
    first = nm.split()[0] if nm else ""
    return f"#{j} {first}"


def sanitize_majestic_game(gdata, team_id, game_label=""):
    """
    Runs the 5-stage ingestion hygiene pass on a raw Majestic `*_full.json` object.
    Returns `(clean_logs, hygiene_summary)`.
    """
    raw_statlog = gdata.get("statlog", [])
    null_dnp_dropped = sum(1 for r in raw_statlog if r.get("period") is None)
    logs = sorted(
        [r for r in raw_statlog if r.get("period") is not None],
        key=lambda r: (int(r.get("period") or 1), int(r.get("id") or 0)),
    )

    # Stage 1: Deduplicate adjacent same-player MISS -> MAKE fat-finger taps (<=3s, no rebound between)
    drop_ids = set()
    shot_indices = [i for i, r in enumerate(logs) if r.get("stat_type") == "shot"]
    for idx_pos in range(len(shot_indices) - 1):
        i0, i1 = shot_indices[idx_pos], shot_indices[idx_pos + 1]
        r0, r1 = logs[i0], logs[i1]
        if (
            r0.get("player_id") == r1.get("player_id")
            and r0.get("made") is False
            and r1.get("made") is True
            and r0.get("value") == r1.get("value")
            and abs(
                raw_elapsed(r1.get("period"), r1.get("clock"))
                - raw_elapsed(r0.get("period"), r0.get("clock"))
            )
            <= 3
        ):
            between_types = [logs[k].get("stat_type") for k in range(i0 + 1, i1)]
            if "rebound" not in between_types:
                drop_ids.add(r0["id"])

    clean_logs = [dict(r) for r in logs if r["id"] not in drop_ids]

    # Stage 2: Repair Majestic's Unpaused-Clock `0:00` Overrun via `logged_at` Active Clock
    by_period = defaultdict(list)
    for r in clean_logs:
        by_period[int(r.get("period") or 1)].append(r)

    frozen_fixed = 0
    overrun_periods = 0
    for per, plogs in by_period.items():
        p_start = 0.0 if per == 1 else (1200.0 if per == 2 else 2400.0 + (per - 3) * 120.0)
        p_dur = 1200.0 if per in (1, 2) else 120.0
        p_end = p_start + p_dur
        zero_cnt = sum(1 for r in plogs if parse_clk(r.get("clock")) == 0)
        ts_vals = [parse_iso(r.get("logged_at")) for r in plogs]

        if (
            ((per in (1, 2) and zero_cnt >= 10) or (per >= 3 and zero_cnt >= 6))
            and all(x is not None for x in ts_vals)
            and len(plogs) >= 5
        ):
            overrun_periods += 1
            frozen_fixed += zero_cnt
            act = [0.0]
            for i in range(1, len(plogs)):
                dt = max(0.0, ts_vals[i] - ts_vals[i - 1])
                st_prev = plogs[i - 1].get("stat_type") or ""
                dt_play = (
                    min(dt, 4.0)
                    if (st_prev.startswith("timeout") or st_prev in ("foul", "freethrow"))
                    else min(dt, 24.0)
                )
                act.append(act[-1] + dt_play)
            tot_act = act[-1] or 1.0
            first_el = raw_elapsed(per, plogs[0].get("clock")) - p_start
            usable_start = p_start + min(30.0, max(0.0, first_el))
            usable_span = (p_end - 1.0) - usable_start
            for r, ac in zip(plogs, act):
                r["_clean_el"] = usable_start + (ac / tot_act) * usable_span
        else:
            zero_run = []
            last_nonzero_el = p_start
            for r in plogs:
                el = raw_elapsed(per, r.get("clock"))
                if parse_clk(r.get("clock")) > 0:
                    last_nonzero_el = max(last_nonzero_el, float(el))
                    r["_clean_el"] = last_nonzero_el
                    zero_run = []
                else:
                    zero_run.append(r)
            if zero_run:
                n = len(zero_run)
                for k, r in enumerate(zero_run):
                    r["_clean_el"] = last_nonzero_el + ((k + 1) / (n + 1)) * max(
                        0.0, (p_end - 0.1) - last_nonzero_el
                    )
                if n >= 2:
                    frozen_fixed += n

    # Stage 3: Possession-Imputed Orphan Misses & TOV Tracking Reliability Gate
    bx_t = [b for b in gdata.get("boxscore", []) if b.get("team_id") == team_id and not b.get("dnp")]
    bx_o = [b for b in gdata.get("boxscore", []) if b.get("team_id") != team_id and not b.get("dnp")]

    fgm_t = sum(int(b.get("fgm") or 0) for b in bx_t)
    raw_fga_t = sum(int(b.get("fga") or 0) for b in bx_t)
    tpm_t = sum(int(b.get("three_pm") or 0) for b in bx_t)
    fgm_o = sum(int(b.get("fgm") or 0) for b in bx_o)
    raw_fga_o = sum(int(b.get("fga") or 0) for b in bx_o)
    miss_logged = (raw_fga_t - fgm_t) + (raw_fga_o - fgm_o)

    tov_t = sum(int(b.get("turnovers") or 0) for b in bx_t)
    tov_o = sum(int(b.get("turnovers") or 0) for b in bx_o)

    orphan_opp_dreb = 0
    orphan_team_dreb = 0
    last_miss_el = -999.0
    for r in clean_logs:
        el = r["_clean_el"]
        st = r.get("stat_type")
        if st in ("shot", "freethrow") and r.get("made") is False:
            last_miss_el = el
        elif st == "rebound":
            if el - last_miss_el > 8.5:
                if r.get("team_id") != team_id:
                    orphan_opp_dreb += 1
                else:
                    orphan_team_dreb += 1
            last_miss_el = -999.0

    regime = "PARTIAL_FG" if miss_logged > 0 else "MAKES_ONLY"
    team_drop = sum(1 for r in logs if r["id"] in drop_ids and r.get("team_id") == team_id)
    clean_fga_t = raw_fga_t - team_drop
    imputed_fga_t = (clean_fga_t + orphan_opp_dreb) if regime == "PARTIAL_FG" else None
    tov_reliable = (tov_t + tov_o) >= 10

    gi = gdata.get("game", {})
    hygiene = {
        "game_label": game_label,
        "date": (gi.get("scheduled_at") or "")[:10],
        "matchup": f"{gi.get('home_team', '')} {gi.get('home_score', '')}-{gi.get('away_score', '')} {gi.get('away_team', '')}".strip(),
        "regime": regime,
        "null_dnp_dropped": null_dnp_dropped,
        "fat_finger_misses_removed": len(drop_ids),
        "overrun_periods_reconstructed": overrun_periods,
        "frozen_zero_clock_events_repaired": frozen_fixed,
        "orphan_unlogged_team_misses": orphan_opp_dreb if regime == "PARTIAL_FG" else None,
        "orphan_unlogged_opp_misses": orphan_team_dreb if regime == "PARTIAL_FG" else None,
        "logged_fg": f"{fgm_t}/{raw_fga_t}",
        "logged_fg_pct": round(100.0 * fgm_t / max(1, raw_fga_t), 1) if regime == "PARTIAL_FG" else None,
        "logged_efg_pct": round(100.0 * (fgm_t + 0.5 * tpm_t) / max(1, raw_fga_t), 1) if regime == "PARTIAL_FG" else None,
        "imputed_true_fg": f"~{fgm_t}/{imputed_fga_t}" if imputed_fga_t else None,
        "imputed_true_fg_pct": round(100.0 * fgm_t / imputed_fga_t, 1) if imputed_fga_t else None,
        "imputed_true_efg_pct": round(100.0 * (fgm_t + 0.5 * tpm_t) / imputed_fga_t, 1) if imputed_fga_t else None,
        "logged_tov_team_opp": f"{tov_t}/{tov_o}",
        "tov_tracking_reliable": tov_reliable,
    }
    return clean_logs, hygiene


def solve_tier_weighted_stints(gdata, clean_logs, team_id, step=20):
    """
    Tier-Weighted Soft-Prior Stint Solver (v2.3):
    - Tier 2 (Scoreboard/Ref: Made FG, FT, Foul) -> +120.0 hard anchor
    - Tier 3 (Discretionary Table Tap: Missed FG, REB, AST, STL, BLK, TOV) -> +14.0 soft prior
      (cannot force two 9.0*2=18.0 live-play teleportation subs if a single jersey was mis-tapped!)
    - Zero transition penalty at halftime & OT period boundaries.
    """
    max_p = max([int(r.get("period") or 1) for r in clean_logs] + [2])
    total_sec = 2400 + max(0, max_p - 2) * 120
    T = total_sec // step
    halftime_bin = 1200 // step
    ot_bins = {2400 // step + k * (120 // step) for k in range(max(0, max_p - 2))}

    raw_secs = {}
    pmap = {}
    for b in gdata.get("boxscore", []):
        if b.get("team_id") == team_id and not b.get("dnp") and (b.get("seconds_played") or 0) > 0:
            p = norm_name(b.get("jersey_number"), b.get("name"))
            raw_secs[p] = int(b.get("seconds_played") or 0)
            pmap[b["player_id"]] = p

    players = sorted(raw_secs.keys())
    tot_raw = sum(raw_secs.values())
    scale = (5 * T) / (tot_raw / step) if tot_raw > 0 else 1.0
    floats = {p: min(float(T), (raw_secs[p] / step) * scale) for p in players}
    target_bins = {p: min(T, int(round(floats[p]))) for p in players}
    while sum(target_bins.values()) < 5 * T:
        best_p = max(players, key=lambda p: (floats[p] - target_bins[p]) if target_bins[p] < T else -999)
        target_bins[best_p] += 1
    while sum(target_bins.values()) > 5 * T:
        best_p = min(players, key=lambda p: (floats[p] - target_bins[p]) if target_bins[p] > 0 else 999)
        target_bins[best_p] -= 1

    tier2_bins = [set() for _ in range(T)]
    tier3_bins = [set() for _ in range(T)]
    team_pts_bin = [0] * T
    opp_pts_bin = [0] * T
    timeouts_bin = set()

    for r in clean_logs:
        bidx = min(T - 1, max(0, int(r["_clean_el"]) // step))
        st = r.get("stat_type")
        if st and st.startswith("timeout"):
            timeouts_bin.add(bidx)
        pts = int(r.get("points") or 0)
        if pts > 0 and r.get("made") is True:
            if r.get("team_id") == team_id:
                team_pts_bin[bidx] += pts
            else:
                opp_pts_bin[bidx] += pts
        if r.get("team_id") == team_id and r.get("player_id") in pmap:
            p = pmap[r["player_id"]]
            if (st == "shot" and r.get("made") is True) or st in ("freethrow", "foul"):
                if len(tier2_bins[bidx]) < 5:
                    tier2_bins[bidx].add(p)
            elif st in ("shot", "rebound", "assist", "steal", "block", "turnover"):
                tier3_bins[bidx].add(p)

    prox_score = {}
    for p in players:
        ebs = [t for t in range(T) if (p in tier2_bins[t] or p in tier3_bins[t])]
        arr = []
        for t in range(T):
            if not ebs:
                arr.append(-50.0)
            else:
                half_t = 0 if t < halftime_bin else (1 if t < 120 else 2)
                same_h = [e for e in ebs if (0 if e < halftime_bin else (1 if e < 120 else 2)) == half_t]
                d = min(abs(t - e) for e in same_h) if same_h else (min(abs(t - e) for e in ebs) + 35.0)
                arr.append(-float(d))
        prox_score[p] = arr

    on_court = [set() for _ in range(T)]
    rem_cap = dict(target_bins)
    for t in range(T):
        rem_bins = T - t
        chosen = {p for p in players if rem_cap[p] >= rem_bins}
        for p in sorted(tier2_bins[t]):
            if len(chosen) < 5 and rem_cap[p] > 0:
                chosen.add(p)
        for p in sorted(tier3_bins[t]):
            if len(chosen) < 5 and rem_cap[p] > 0:
                chosen.add(p)
        while len(chosen) < 5:
            cands = [p for p in players if p not in chosen and rem_cap[p] > 0]
            best_p = max(cands, key=lambda p: (1 if rem_cap[p] == rem_bins else 0, prox_score[p][t] + 0.5 * rem_cap[p]))
            chosen.add(best_p)
        on_court[t] = chosen
        for p in chosen:
            rem_cap[p] -= 1

    tr_weight = 9.0
    prox_weight = 0.45

    def bin_ev_bonus(p, t):
        if p in tier2_bins[t]:
            return 120.0
        if p in tier3_bins[t]:
            return 14.0
        return 0.0

    for _ in range(35):
        improved = False
        for lo in range(T):
            for hi in range(lo + 1, T):
                as_ = [p for p in (on_court[lo] - on_court[hi]) if p not in tier2_bins[lo]]
                bs_ = [p for p in (on_court[hi] - on_court[lo]) if p not in tier2_bins[hi]]
                if not as_ or not bs_:
                    continue
                for pa in as_:
                    for pb in bs_:
                        ev_gain = (bin_ev_bonus(pb, lo) + bin_ev_bonus(pa, hi)) - (
                            bin_ev_bonus(pa, lo) + bin_ev_bonus(pb, hi)
                        )
                        prox_gain = (prox_score[pb][lo] + prox_score[pa][hi]) - (
                            prox_score[pa][lo] + prox_score[pb][hi]
                        )
                        s1_new = (on_court[lo] - {pa}) | {pb}
                        s2_new = (on_court[hi] - {pb}) | {pa}

                        def get_s(idx, o=False):
                            if o:
                                return on_court[idx]
                            if idx == lo:
                                return s1_new
                            if idx == hi:
                                return s2_new
                            return on_court[idx]

                        edges = {idx for idx in (lo, lo + 1, hi, hi + 1) if 0 < idx < T}

                        def edge_w(idx):
                            if idx == halftime_bin or idx in ot_bins:
                                return 0.0
                            if idx in timeouts_bin:
                                return 1.5
                            return tr_weight

                        old_tr = sum(edge_w(idx) * len(get_s(idx, True) ^ get_s(idx - 1, True)) for idx in edges)
                        new_tr = sum(edge_w(idx) * len(get_s(idx, False) ^ get_s(idx - 1, False)) for idx in edges)
                        if (ev_gain + prox_gain * prox_weight - (new_tr - old_tr)) > 1e-6:
                            on_court[lo] = s1_new
                            on_court[hi] = s2_new
                            improved = True
                            break
                    if improved:
                        break
        if not improved:
            break

    cum_cu, cum_op = 0, 0
    marg = []
    for t in range(T):
        marg.append(cum_cu - cum_op)
        cum_cu += team_pts_bin[t]
        cum_op += opp_pts_bin[t]

    subs = sum(len(on_court[t] - on_court[t - 1]) for t in range(1, T) if t != halftime_bin and t not in ot_bins)
    return on_court, team_pts_bin, opp_pts_bin, marg, subs
