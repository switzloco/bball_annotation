# Majestic Stats Skepticism & Film-First Ground Truth Rule

## Why This Tool Exists ("Why You Have a Job")
Majestic Hoops (`majesticstats.com`) iPad table-scorer box scores and `statlog` timelines are **approximate at best** — never treat raw Majestic `FGA`, `FG%`, `3PT%`, `REB`, `AST`, `TOV`, or `clock` strings as ground truth without running `majestic_hygiene.py` and auditing game film!

## 5 Systemic Failure Modes Proven Across All 10 League JSONs + Film
1. **Unlogged Missed Shots (`OrphanOppDREB`) Even in Weeks 3–4**:
   - Weeks 1–2 logged **makes only** (`0` misses, `FGM == FGA`).
   - Even in Weeks 3–4 (`PARTIAL_FG`), fast rebounds, airballs, and quick putbacks cause iPad scorers to drop `15%–35%` of missed shots: e.g., `#7 Nick`'s true `~6/13` (`~46%`) 3PT night in `G3` was logged as `6/8` (`75%`), and Latto Talent's logged `21/48` (`43.8%`) vs. Sapa Boys hid **`26` Sapa Boys defensive rebounds with zero prior missed shot logged** (Possession-Imputed True Shooting = **`~21/74`, `28.4% FG`**; Weeks 3–4 combined drops from `38.7%` logged FG to **`~30.3% FG / ~36.8% eFG%`**).
2. **Unpaused-Timer `"0:00"` Clock Overrun Bug**:
   - Majestic's iPad clock (`20:00 -> 0:00`) is not wired to the gym scoreboard and frequently runs continuously through timeouts, fouls, free throws, and final-`2:00` stop-clock play — hitting `"0:00"` with `5–7` minutes of real basketball left and dumping `28–60` crunch-time events at `"0:00"` (`60` in `CU G4 OT`, `39` in `LT Wk2 OT`, `31` in `LT Wk4`). Always reconstruct **Dead-Ball-Stripped Active Clock** from UTC `logged_at` (`majestic_hygiene.sanitize_majestic_game`) or calibrate directly to the gym LED scoreboard on film.
3. **Fat-Finger Double-Taps & Cross-Jersey Miss Misattributions**:
   - Adjacent same-player `MISS -> MAKE` taps `<=3s` with zero rebound between (`2` removed in `CU G3`), plus 50-ft cross-jersey guesses (`#7`'s `3:01 2H` miss billed to `#20 Shane`).
4. **Inconsistent Turnover Tracking (`TOV` Gate Required)**:
   - Scorekeepers range from `1` CU turnover in `40m` (`CU G3`) to `17` (`CU G4`). Gate any cross-game `TOPG` or `AST/TOV` claim on **`combined_logged_tov >= 10`**.
5. **Null-Period DNP Rows & Missing Substitution Logs**:
   - Strip `period: null` (`dnp`) entries before sorting `statlog`, weight Tier-2 (`Made FG / FT / Foul`) `8.5x` above Tier-3 (`Miss / REB / AST / STL / TOV`) in stint solving, require `>=3.0m` bench/court exposure for Within-Game On/Off, and disclose `±2.5–4.0/10m` single-player solver uncertainty when subs are reconstructed.

## Mandatory 3-Tier Data Trust Hierarchy
1. **Tier 1 — Film-Verified / CV-Localized Ground Truth (Gold)**: Actual video frames, Collab Studio human-verified tags, `CHG` (Charges Drawn), and CV court-homography localizations (upgrade CV from statlog-triggered to **Rim-Impulse + Orphan-DREB triggered** so unlogged misses are captured).
2. **Tier 2 — Scoreboard-Coupled Counts (Silver)**: Final/halftime scores, `PTS`, `2PM`, `3PM`, `FTM`, and `PF`.
3. **Tier 3 — Discretionary Table-Scorer Taps (Noisy Approximation — NEVER Call "Verified")**: Always pair raw `FG%` with **Possession-Imputed True `FG%` / `eFG%`** from `majestic_hygiene.py`.

## Presentation Rule in Scouting Reports (Succinct, Never Preachy!)
- Keep data-hygiene math (`majestic_hygiene.py`, `0:00` clock reconstruction, orphan-rebound imputation, stint priors) **under the hood**.
- In scouting reports and UI cards, **never lecture the reader about scorer errors or methodology**. Simply present the clean basketball numbers directly and add a brief 3–6 word note **only where film/tracking differs meaningfully from the box score** (e.g., `~30% true FG on film vs. 39% box`, `~6/13 3PT on film vs. 6/8 box`, `3/11 3PT on film vs. 3/12 box`).
