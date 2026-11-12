# Majestic Stats Skepticism & Film-First Ground Truth Rule

## Why This Tool Exists ("Why You Have a Job")
Majestic Hoops (`majesticstats.com`) iPad table-scorer box scores are **approximate at best** — never treat raw Majestic `FGA`, `FG%`, `3PT%`, `REB`, `AST`, or `TOV` as ground truth without auditing the game film!

## Empirical Proof from Game Film (`G3 vs. Misfits 2`, Nov 1, 2026)
Even in Weeks 3–4 where Majestic enabled missed-shot buttons (unlike Weeks 1–2 which logged `0` misses, `FGM == FGA`), film inspection of `2026-11-01_CU_vs_Misfits2_G3.mp4` exposed massive table-scorer noise:
1. **Unlogged Missed Shots (`37` `MISS_PRIOR` Orphan Rebounds in One Game)**: Whenever play moved fast or a rebound/putback happened quickly (e.g. `#7 Nick`'s missed heat-check right-wing 3 at `5:44 2H` rebounded by `#9 Aaron`, or airballs/out-of-bounds misses), the scorer tapped only the rebound (or nothing), turning `#7 Nick`'s true **`~6/13` (`~46%`)** 3PT volume night into an inflated **`6/8` (`75%`)** box-score mirage.
2. **Cross-Jersey Miss Misattribution**: From 50 ft away at the scorer's table, iPad operators guess jerseys on misses — e.g., at `3:01 2H` (`s=3322s`), `#7 Nick` missed a right-wing 3PT on film that the scorer billed to `#20 Shane Hoffman` (simultaneously inflating `#7`'s FG% and depressing `#20`'s FG%), and at `13:14 2H` double-logged a miss and make on the same shot.
3. **Massive Turnover Undercounting**: In `G3` (`83–66`, 40 minutes of up-tempo play), the Majestic scorer logged **just `1` total turnover for all of Campbell United** (`3` for Misfits 2), creating fake `4:0` / `7:1` `AST/TOV` ratios and logging live-ball steals as "Rebounds" (`s=2453s`).

## Mandatory 3-Tier Data Trust Hierarchy
1. **Tier 1 — Film-Verified / CV-Localized Ground Truth (Gold)**:
   - Actual video frame inspection, Collab Studio human-verified tags, `CHG` (Charges Drawn), and CV court-homography shot/contest localizations. Always prioritize Tier 1 when film is available.
2. **Tier 2 — Scoreboard-Coupled Counts (Silver)**:
   - Final/halftime scores, `PTS`, `2PM`, `3PM`, `FTM` (coupled to the gym LED scoreboard), and `PF` (coupled to referee table foul/bonus calls, though individual jersey attribution can still drift by `±1`).
3. **Tier 3 — Discretionary Table-Scorer Taps (Noisy Approximation — NEVER Call "Verified")**:
   - Weeks 1–2 `FGA`/`FTA` (`0%` misses logged — completely unusable for `%`).
   - Weeks 3–4 `FGA`, `FG%`, `3PT%`, `AST`, `REB`, `STL`, `TOV` — directional only (`FGA` systematically undercounts true attempts by `15–35%` and `TOV` is wildly inconsistent across scorekeepers, e.g., `1 TOV` in `G3` vs. `17 TOV` in `G4`).
   - **Rule**: Never label raw Majestic Weeks 3–4 splits as `"Verified"` unless audited on video; explicitly caveat table-scorer miss/turnover undercounting and cross-check outliers on film!
