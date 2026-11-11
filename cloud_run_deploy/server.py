import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from urllib.parse import parse_qs, urlparse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

GCS_ROOT_DIR = "/mnt/gcs"
GCS_MOUNT_DIR = "/mnt/gcs/runs/2026-10-31"
IS_CLOUD_RUN = os.path.exists(GCS_ROOT_DIR)

DEFAULT_CREW_MASTER_ROSTER = {
    "Josh": {
        "name": "Josh",
        "permanent_traits": "Curly brown hair, stocky build, high-volume 3PT shooter & primary ball-handler",
        "default_team_role": "Far Hoop Squad Captain",
        "outfit_history": {"2026-10-31": "White \"Luigi's\" Tee"},
        "updated_at": "2026-10-31T23:55:00Z",
    },
    "Damien": {
        "name": "Damien",
        "permanent_traits": "Stocky/tall build, bald head, beard, dominant rebounder & interior shot-blocker",
        "default_team_role": "Near Hoop Anchor",
        "outfit_history": {"2026-10-31": "Maroon Tee"},
        "updated_at": "2026-10-31T23:55:00Z",
    },
    "Kenny": {
        "name": "Kenny",
        "permanent_traits": "Tall, lean wing, wears black track pants & bright teal shoes, clutch wing 3PT shooter",
        "default_team_role": "Wing Sharpshooter",
        "outfit_history": {"2026-10-31": "Black Tee / Black Pants (Teal Shoes)"},
        "updated_at": "2026-10-31T23:55:00Z",
    },
    "Brian": {
        "name": "Brian",
        "permanent_traits": "Blonde hair, athletic wing, left-wing slasher & high-arc runner finisher",
        "default_team_role": "Slasher / Wing",
        "outfit_history": {"2026-10-31": "Black Tee (Blonde Hair)"},
        "updated_at": "2026-10-31T23:55:00Z",
    },
    "Donnie": {
        "name": "Donnie",
        "permanent_traits": "Wears glasses, crafty baseline driver & reverse layup finisher",
        "default_team_role": "Guard / Wing",
        "outfit_history": {"2026-10-31": "Dark Blue \"Warriors\" Tee"},
        "updated_at": "2026-10-31T23:55:00Z",
    },
    "Timor": {
        "name": "Timor",
        "permanent_traits": "Quick two-way guard, smooth mid-range pull-up jumper & active on-ball steals",
        "default_team_role": "Two-Way Guard",
        "outfit_history": {"2026-10-31": "Black Tee / Mint Green Shorts"},
        "updated_at": "2026-10-31T23:55:00Z",
    },
    "Rock": {
        "name": "Rock",
        "permanent_traits": "Bald, stocky build, strong interior defender, active hands & clutch passer",
        "default_team_role": "Point Forward / Defender",
        "outfit_history": {"2026-10-31": "Black Tee (Bald, Stocky) / Neon Yellow"},
        "updated_at": "2026-10-31T23:55:00Z",
    },
    "Spider": {
        "name": "Spider",
        "permanent_traits": "Lean, high-motor rebounder, white shoes, relentless offensive glass putback specialist",
        "default_team_role": "Glass Cleaner / Forward",
        "outfit_history": {"2026-10-31": "Grey Sleeveless Tank"},
        "updated_at": "2026-10-31T23:55:00Z",
    },
}

if IS_CLOUD_RUN:
    os.makedirs(GCS_MOUNT_DIR, exist_ok=True)
    FEEDBACK_FILE = os.path.join(GCS_MOUNT_DIR, "training_feedback.json")
    JSONL_LOG_FILE = os.path.join(GCS_MOUNT_DIR, "training_corrections.jsonl")
    CREW_MASTER_FILE = os.path.join(GCS_ROOT_DIR, "crew_master_roster.json")
    VIDEO_FILE = os.path.join(GCS_MOUNT_DIR, "20261031_full_game.mp4")
    if not os.path.exists(FEEDBACK_FILE) and os.path.exists("training_feedback.json"):
        shutil.copyfile("training_feedback.json", FEEDBACK_FILE)
    if not os.path.exists(JSONL_LOG_FILE) and os.path.exists("training_corrections.jsonl"):
        shutil.copyfile("training_corrections.jsonl", JSONL_LOG_FILE)
else:
    FEEDBACK_FILE = "training_feedback.json"
    JSONL_LOG_FILE = "training_corrections.jsonl"
    CREW_MASTER_FILE = "crew_master_roster.json"
    VIDEO_FILE = (
        "20261031_full_game_web.mp4"
        if os.path.exists("20261031_full_game_web.mp4")
        else "20261031_full_game.mp4"
    )

PUBLIC_GCS_VIDEO_URL = "https://storage.googleapis.com/basketball-highlights-store/runs/2026-10-31/20261031_full_game.mp4"
MAX_RANGE_CHUNK = 8 * 1024 * 1024
TEAM_PASSCODE = os.environ.get("FILM_ROOM_PASSCODE", "cu2026").strip().lower()
AUTH_COOKIE_HEADER = f"cpsn_auth={TEAM_PASSCODE}; Max-Age=7776000; Path=/; SameSite=Lax"


def load_crew_master_roster():
    roster = dict(DEFAULT_CREW_MASTER_ROSTER)
    # First merge bundled local crew_master_roster.json if present
    if os.path.exists("crew_master_roster.json"):
        try:
            with open("crew_master_roster.json", "r", encoding="utf-8") as f:
                bundled = json.load(f)
                if isinstance(bundled, dict):
                    roster.update(bundled)
        except Exception:
            pass
    # Then merge persistent GCS / local CREW_MASTER_FILE
    if os.path.exists(CREW_MASTER_FILE):
        try:
            with open(CREW_MASTER_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                if isinstance(saved, dict):
                    for k, v in saved.items():
                        if k in roster and isinstance(roster[k], dict) and isinstance(v, dict):
                            merged = dict(roster[k])
                            merged.update(v)
                            if "biometric_anchors" in roster[k] and "biometric_anchors" not in v:
                                merged["biometric_anchors"] = roster[k]["biometric_anchors"]
                            roster[k] = merged
                        else:
                            roster[k] = v
        except Exception:
            pass
    return roster


def save_crew_master_roster(roster):
    try:
        with open(CREW_MASTER_FILE, "w", encoding="utf-8") as f:
            json.dump(roster, f, indent=2)
    except Exception:
        pass


def load_feedback():
    default_data = {
        "plays": {},
        "crew_roster_map": {},
        "crew_master_roster": load_crew_master_roster(),
        "custom_plays": [],
        "segment_corrections": [],
        "collab_calibrations": {},
        "collab_live_tags": {},
    }
    target = FEEDBACK_FILE if os.path.exists(FEEDBACK_FILE) else "training_feedback.json"
    if not os.path.exists(target):
        return default_data
    try:
        with open(target, "r", encoding="utf-8") as f:
            loaded = json.load(f)
            for k, v in default_data.items():
                if k not in loaded:
                    loaded[k] = v
            # Merge global persistent crew_master_roster so all regular ballers are always present
            master = load_crew_master_roster()
            if isinstance(loaded.get("crew_master_roster"), dict):
                master.update(loaded["crew_master_roster"])
            loaded["crew_master_roster"] = master
            return loaded
    except Exception:
        return default_data


def save_feedback(data, log_entry=None):
    if "crew_master_roster" in data and isinstance(data["crew_master_roster"], dict):
        save_crew_master_roster(data["crew_master_roster"])
    with open(FEEDBACK_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    if log_entry:
        with open(JSONL_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry) + "\n")


PLAY_OG_METADATA = {
    1385: (
        "🔥 CPSN #1 Play (23:05) — Josh Outlet Pass → Kenny Walk-Off Layup (15–14 Final)",
        "Watch Josh sky for the DREB at 23:00 and fire a full-court outlet pass to Kenny for the walk-off game-winner! Starts with 5s setup pre-roll.",
    ),
    1355: (
        "🏀 CPSN #2 Play (22:35) — Rock Dish → Timor Clutch Right-Wing Jumper (14–14)",
        "Watch Rock find Timor on the right wing at 22:33 to tie the game 14–14! Starts with 5s setup pre-roll.",
    ),
    1297: (
        "🔒 CPSN #3 Play (21:37) — Timor Midcourt Steal → Damien Fast-Break Finish",
        "Two-way transition bucket: Timor strips the ball at midcourt and leads Damien for the fast-break layup!",
    ),
    539: (
        "⚡ CPSN #4 Play (08:54) — Damien Coast-to-Coast Steal & Fast-Break Layup",
        "Damien intercepts the pass at the Far Hoop and goes coast-to-coast on a 2-on-0 break with Timor!",
    ),
    2238: (
        "🎯 CPSN #5 Play (37:18) — Brian Shooter's Touch High-Bounce Runner",
        "Brian slashes down the left lane and floats a high-arc runner that bounces high off the iron and drops in!",
    ),
    378: (
        "🏀 Game 1 Winner (06:18) — Donnie Dish → Game-Winning Cut & Layup (9–12 Final)",
        "Watch the Game 1 walk-off bucket at Campbell Park Sports Network Film Room!",
    ),
    186: (
        "🏀 Highlight (03:06) — Donnie Crafty Baseline Reverse Layup (9–9)",
        "Watch Donnie drive the right baseline and finish a reverse layup off a dish from Timor!",
    ),
}


class RangeAndFeedbackHandler(SimpleHTTPRequestHandler):
    """HTTP handler supporting:
    1. Byte-Range (206 Partial Content) for local playback & direct CDN redirect on Cloud Run.
    2. GET /api/clip?s=<sec>&dur=<sec> for instant lossless 9-second MP4 highlight downloads.
    3. GET/POST /api/feedback for storing RLHF training corrections, day-to-day crew identity mappings, and Cap/Facts votes.
    4. Dynamic OpenGraph meta tags for ?play= and ?reel= deep-links shared in WhatsApp / iMessage / Discord.
    """

    def is_authorized(self, qs=None):
        return True

    def do_GET(self):
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        k_val = ((qs.get("k") or qs.get("key") or [""])[0]).strip().lower()
        has_valid_k = (k_val == TEAM_PASSCODE)

        if parsed.path == "/robots.txt":
            body = b"User-agent: *\nDisallow: /\n"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if parsed.path in ("/", "/index.html"):
            game_val = (qs.get("game") or [None])[0]
            play_val = (qs.get("play") or qs.get("t") or [None])[0]
            reel_val = (qs.get("reel") or [None])[0]
            if (game_val or play_val or reel_val or has_valid_k) and os.path.exists("index.html"):
                try:
                    with open("index.html", "r", encoding="utf-8") as f:
                        html = f.read()
                    custom_title = None
                    custom_desc = None
                    game_og_map = {
                        "scouting_nov15": (
                            "📋 Campbell United Scouting Report: vs. Latto Talent (Sun Nov 15 @ 5:00 PM — Battle for #1!)",
                            "1080p Scouting Tape & Matchup Plan for CU (4-0) vs. Latto Talent (3-1): #9 Diallo Holmes (20.3 PPG), #1 Sean Steven, #5 Brandon Nguyen & #2 Troy!",
                        ),
                        "scouting_nov8": (
                            "📋 Campbell United Scouting Report: vs. Ricecookers (Sun Nov 8 @ 8:00 PM)",
                            "Complete personnel breakdown (#3 Dustin, #22 Sim, #7 Nate, #1 Aaron, #4 Eugene, #12 AJ, #11 Dylan), tactical keys to victory & game film!",
                        ),
                        "2026-10-04_CU_vs_Mustangs_Champ": (
                            "🏆 Fall '26 Championship: Campbell United 76, Mustangs 66 — Interactive Film Room",
                            "Watch every play & highlight from Campbell United's 76–66 Fall '26 Championship win over Mustangs!",
                        ),
                        "2026-10-18_CU_vs_HalalHoopers_G1": (
                            "🏀 Holiday '26 Game 1: Campbell United 69, Halal Hoopers 47 — Interactive Film Room",
                            "Watch synced game film, box score & highlights from Campbell United's 69–47 Season Opener victory!",
                        ),
                        "2026-10-25_CU_vs_TMT_G2": (
                            "🔥 Holiday '26 Game 2: Campbell United 52, TMT 50 — Interactive Film Room",
                            "Watch every play from Campbell United's 52–50 nail-biter win over TMT at The Grove CC!",
                        ),
                        "2026-11-01_CU_vs_Misfits2_G3": (
                            "🚀 Holiday '26 Game 3: Campbell United 83, Misfits 2 66 (3-0 D2) — Film & Stats Hub",
                            "Full play-by-play & box score from Campbell United's 83–66 win over Misfits 2 (11x 3PM, 3-0 in D2)!",
                        ),
                        "2026-02-15_CU_vs_PimpsDown": (
                            "⚡ Winter '26 Wk 6: Campbell United 59, Pimps Down 51 (#30 Wes Spotlight) — Film Room",
                            "Watch #30 Wes's 10 PTS, 3 AST, coast-to-coast steal & clutch late bucket in Campbell United's 59–51 win!",
                        ),
                        "2026-09-20_SB_vs_Mustangs_Eugene41": (
                            "👑 #99 Eugene Kim 41 PTS (11× 3PM): Sapa Boys 78, Mustangs 76 OT — Film Room",
                            "Watch all 11 3-pointers, buzzer-beating block & walk-off OT FTs in Eugene Kim's 41-point explosion!",
                        ),
                        "2026-10-18_SB_vs_Tandoori_Eugene29": (
                            "🔥 #99 Eugene Kim 29 PTS (5× 3PM, 6 AST): Sapa Boys 83, Tandoori Chicken 73 — Film Room",
                            "Watch every bucket & dime from #99 Eugene Kim (29 PTS, 5 REB, 6 AST) & #32 Tianen Chen (30 PTS)!",
                        ),
                        "2026-10-15_Pickup_G1": (
                            "🏀 Pickup Run: Oct 15, 2026 Game 1 — Campbell United × Pickup Crew (9–4) | CPSN Film Room",
                            "Cross-run biometric player ID connecting Campbell United (#44 Christian, #4 Adam, #31 Evan, #16 Chris, #7 Nick, #9 Aaron, #24 George) to the Oct 15 pickup run!",
                        ),
                        "2026-11-08_CU_vs_Ricecookers_G4": (
                            "🏆 Holiday '26 Game 4: Campbell United 66, Ricecookers 63 (OT) — 4-0 D2 1080p Film Room",
                            "#44 Christian Raslowsky's 61–61 buzzer 3PT (23 PTS, 14 REB) + #20 Shane Hoffman's OT game-winning 3PT lift Campbell United to 66–63 (4-0 D2)!",
                        ),
                        "2026-10-18_WTN_vs_OTFSelect_G1": (
                            "🍁 WeTheNorth (#2 Mo) vs. OTF Select — Holiday '26 Game 1 Film Room",
                            "Watch synced game film, box score & #2 Mo's highlights from WeTheNorth vs. OTF Select!",
                        ),
                        "2026-10-25_WTN_vs_NewAvengers_G2": (
                            "🍁 WeTheNorth (#2 Mo: 7 PTS on 3/3 FG, 7 REB, AST, STL) vs. New Avengers — Game 2 Film Room",
                            "Watch #2 Mo's 100% FG shooting night (7 PTS, 7 REB, 1 AST, 1 STL) in WeTheNorth vs. New Avengers!",
                        ),
                        "2026-11-01_WTN_vs_CrunchTime_G3": (
                            "🔥 #2 Mo 15 PTS (5× 3PM, 5 REB, 1 BLK): WeTheNorth vs. Crunch Time — Game 3 Film Room",
                            "Watch all 5 3-pointers (including 3 straight triples in 52 seconds!) & 1st-half block from #2 Mo!",
                        ),
                        "2026-11-08_WTN_vs_DomainExpansion_G4": (
                            "🏆 WeTheNorth 55, Domain Expansion 53 [WIN!] (#2 Mo Two-Way Showcase) — Game 4 Film Room",
                            "Full box score, play-by-play & #2 Mo Season Highlight Reel from WeTheNorth's 55–53 victory over Domain Expansion!",
                        ),
                        "2026-02-01_C7_vs_OutOfShape_W4": (
                            "🔥 #2 Mohamed 25 PTS (11 FG, 3× 3PM, 9 REB, 1 BLK): Crew 7 vs. Out Of Shape — Winter '26 Film Room",
                            "Watch #2 Mohamed's 25-point eruption on Crew 7 + live Collab Training verification in 1080p HD!",
                        ),
                        "2026-01-25_C7_vs_BTA_W3": (
                            "⚡ #2 Mohamed Double-Double (13 PTS, 11 REB, 5 AST, STL, BLK): Crew 7 vs. BTA — Winter '26 Film Room",
                            "Full 1080p game film & #2 Mohamed's all-around double-double showcase on Crew 7!",
                        ),
                        "2026-01-18_C7_vs_Breadwinners_W2": (
                            "🎯 #2 Mohamed 14 PTS (4× 3PM, 7 REB, 3 STL, 1 BLK): Crew 7 vs. Breadwinners — Winter '26 Film Room",
                            "Watch #2 Mohamed's 4-three sharpshooting & 3-steal defensive clinic for Crew 7!",
                        ),
                        "season_analytics": (
                            "🧠 Campbell United Season Analytics & #4 Adam 3× Dunk Lab — CPSN Film Room",
                            "Watch #4 Adam Fecteau's 3-Dunk 1st Half vs. Misfits 2 + Colab GPU Analytics across Campbell United's 4-0 streak!",
                        ),
                    }
                    if game_val in game_og_map and not play_val:
                        custom_title, custom_desc = game_og_map[game_val]
                    elif reel_val == "cu_g4":
                        custom_title = "🎬 Campbell United 66, Ricecookers 63 (OT) — 1080p Comeback & Game-Winner Reel (4-0 D2)"
                        custom_desc = "Watch #44 Christian's 61-61 buzzer 3PT, #16 Chris's OT block & lead bucket, and #20 Shane's OT game-winning 3PT in 1080p Full HD!"
                    elif reel_val == "mo":
                        custom_title = "🎬 #2 Mo 1080p Highlight Reel — WeTheNorth & Crew 7 Showcase"
                        custom_desc = "Watch #2 Mohamed's 1080p Full HD highlights across WeTheNorth & Crew 7 with 2.0x ISO CAM zoom!"
                    elif reel_val == "mo_c7":
                        custom_title = "🔥 #2 Mohamed (Crew 7 • Winter '26) 1080p Highlight Reel — 58 PTS, 10× 3PM, 30 REB"
                        custom_desc = "Watch #2 Mohamed's Winter '26 Crew 7 eruption (25 PTS vs OOS, 13/11/5 vs BTA, 4× 3PM vs Breadwinners) in 1080p HD!"
                    elif reel_val == "top5":
                        custom_title = "🎬 CPSN Top 5 Plays Auto-Reel — Campbell United Film Room"
                        custom_desc = "Auto-plays all 5 Top Plays back-to-back with 5s setup pre-roll!"
                    elif play_val and play_val.isdigit():
                        sec = int(play_val)
                        if sec in PLAY_OG_METADATA and not game_val:
                            custom_title, custom_desc = PLAY_OG_METADATA[sec]
                        else:
                            mm, ss = sec // 60, sec % 60
                            custom_title = f"🏀 Campbell United Highlight @ {mm:02d}:{ss:02d} — CPSN Film Room"
                            custom_desc = f"Watch this play at {mm:02d}:{ss:02d} (with 5s pre-roll to catch the pass) or download the 11s MP4 clip!"
                    if custom_title and custom_desc:
                        html = re.sub(
                            r'(<meta\s+property="og:title"\s+content=")[^"]*(")',
                            lambda m: f"{m.group(1)}{custom_title}{m.group(2)}",
                            html,
                        )
                        html = re.sub(
                            r'(<meta\s+name="twitter:title"\s+content=")[^"]*(")',
                            lambda m: f"{m.group(1)}{custom_title}{m.group(2)}",
                            html,
                        )
                        html = re.sub(
                            r'(<meta\s+property="og:description"\s+content=")[^"]*(")',
                            lambda m: f"{m.group(1)}{custom_desc}{m.group(2)}",
                            html,
                        )
                        html = re.sub(
                            r'(<meta\s+name="twitter:description"\s+content=")[^"]*(")',
                            lambda m: f"{m.group(1)}{custom_desc}{m.group(2)}",
                            html,
                        )
                    payload = html.encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Cache-Control", "no-cache")
                    if has_valid_k:
                        self.send_header("Set-Cookie", AUTH_COOKIE_HEADER)
                    self.send_header("Content-Length", str(len(payload)))
                    self.end_headers()
                    self.wfile.write(payload)
                    return
                except Exception:
                    pass

        if parsed.path == "/api/majestic":
            bundle_path = "majestic_games_bundle.json"
            if os.path.exists(bundle_path):
                with open(bundle_path, "rb") as f:
                    payload = f.read()
            else:
                payload = b"{}"
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return

        if parsed.path == "/api/feedback":
            data = load_feedback()
            payload = json.dumps(data).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return

        if parsed.path == "/api/clip":
            if not self.is_authorized(qs):
                self.send_error(401, "Team Passcode Required to Download Clips")
                return
            center_sec = float(qs.get("s", ["0"])[0])
            duration = float(qs.get("dur", ["11"])[0])
            raw_name = qs.get("name", [""])[0]
            game_slug = qs.get("game", ["pickup"])[0]
            start_sec = max(0.0, center_sec - 6.0)
            mm = int(center_sec) // 60
            ss = int(center_sec) % 60
            known_slugs = {
                1385: "Josh_outlet_Kenny_walkoff_layup_10-31-26",
                1355: "Rock_to_Timor_clutch_jumper_10-31-26",
                1297: "Timor_steal_Damien_layup_10-31-26",
                2141: "Josh_missed_deep_3pt_10-31-26",
                2238: "Brian_bounce_runner_10-31-26",
                539: "Damien_steal_fastbreak_layup_10-31-26",
                378: "Game1_winner_layup_10-31-26",
                186: "Donnie_reverse_layup_10-31-26",
            }
            clean_name = re.sub(r"[^A-Za-z0-9_\-]+", "_", raw_name).strip("_")
            if not clean_name:
                clean_name = known_slugs.get(
                    int(round(center_sec)),
                    f"bball_clip_{mm:02d}m{ss:02d}s",
                )
            if clean_name.lower().endswith(".mp4"):
                clean_name = clean_name[:-4]
            out_name = f"{clean_name}.mp4"

            tmp_fd, tmp_path = tempfile.mkstemp(suffix=".mp4")
            os.close(tmp_fd)
            try:
                majestic_allowed = {
                    "2026-10-04_CU_vs_Mustangs_Champ",
                    "2026-10-18_CU_vs_HalalHoopers_G1",
                    "2026-10-25_CU_vs_TMT_G2",
                    "2026-11-01_CU_vs_Misfits2_G3",
                    "2026-11-08_CU_vs_Ricecookers_G4",
                    "2026-10-18_WTN_vs_OTFSelect_G1",
                    "2026-10-25_WTN_vs_NewAvengers_G2",
                    "2026-11-01_WTN_vs_CrunchTime_G3",
                    "2026-11-08_WTN_vs_DomainExpansion_G4",
                    "2026-01-11_C7_vs_OutOfShape_W1",
                    "2026-01-18_C7_vs_Breadwinners_W2",
                    "2026-01-25_C7_vs_BTA_W3",
                    "2026-02-01_C7_vs_OutOfShape_W4",
                    "2026-09-20_SB_vs_Mustangs_Eugene41",
                    "2026-10-18_SB_vs_Tandoori_Eugene29",
                    "2026-10-15_Pickup_G1",
                    "2026-02-15_CU_vs_PimpsDown",
                    "2026-02-08_CU_vs_Eagles",
                    "2025-11-09_CU_vs_Crew7",
                    "2026-03-01_CU_vs_LattoTalent_Champ",
                }
                if game_slug in majestic_allowed:
                    local_oct = os.path.join("majestic_oct2026", f"{game_slug}.mp4")
                    local_wtn = os.path.join("majestic_wtn", f"{game_slug}.mp4")
                    local_c7 = os.path.join("majestic_crew7", f"{game_slug}.mp4")
                    local_maj = os.path.join("majestic_games", f"{game_slug}.mp4")
                    if not IS_CLOUD_RUN and os.path.exists(local_oct):
                        src_video = local_oct
                    elif not IS_CLOUD_RUN and os.path.exists(local_wtn):
                        src_video = local_wtn
                    elif not IS_CLOUD_RUN and os.path.exists(local_c7):
                        src_video = local_c7
                    elif not IS_CLOUD_RUN and os.path.exists(local_maj):
                        src_video = local_maj
                    else:
                        src_video = f"https://storage.googleapis.com/basketball-highlights-store/majestic/{game_slug}.mp4"
                else:
                    src_video = VIDEO_FILE if (not IS_CLOUD_RUN and os.path.exists(VIDEO_FILE)) else PUBLIC_GCS_VIDEO_URL
                cmd = [
                    "ffmpeg", "-y",
                    "-ss", f"{start_sec:.2f}",
                    "-i", src_video,
                    "-t", f"{duration:.2f}",
                    "-c", "copy",
                    "-movflags", "+faststart",
                    tmp_path,
                ]
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                with open(tmp_path, "rb") as f:
                    clip_bytes = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "video/mp4")
                self.send_header("Content-Disposition", f'attachment; filename="{out_name}"')
                self.send_header("Content-Length", str(len(clip_bytes)))
                self.end_headers()
                self.wfile.write(clip_bytes)
            except Exception as e:
                self.send_error(500, f"Clip extraction failed: {e}")
            finally:
                if os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except OSError:
                        pass
            return

        return super().do_GET()

    def do_POST(self):
        if self.path.startswith("/api/auth"):
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
            try:
                body = json.loads(raw)
            except Exception:
                body = {}
            pw = str(body.get("passcode") or "").strip().lower()
            if pw == TEAM_PASSCODE:
                resp = json.dumps({"ok": True}).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Set-Cookie", AUTH_COOKIE_HEADER)
                self.send_header("Content-Length", str(len(resp)))
                self.end_headers()
                self.wfile.write(resp)
            else:
                resp = json.dumps({"ok": False, "error": "Invalid team passcode"}).encode("utf-8")
                self.send_response(401)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(resp)))
                self.end_headers()
                self.wfile.write(resp)
            return

        if self.path.startswith("/api/feedback"):
            if not self.is_authorized():
                resp = json.dumps({"error": "Team passcode required"}).encode("utf-8")
                self.send_response(401)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(resp)))
                self.end_headers()
                self.wfile.write(resp)
                return
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length).decode("utf-8")
            body = json.loads(raw) if raw else {}
            data = load_feedback()

            action = body.get("action")
            play_key = str(body.get("play_key", ""))
            now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

            if play_key and play_key not in data["plays"]:
                data["plays"][play_key] = {
                    "accurate_votes": 0,
                    "wrong_votes": 0,
                    "fire_votes": 0,
                    "notes": [],
                }

            log_entry = None

            if action == "vote_play" and play_key:
                vote_type = body.get("vote")
                if vote_type == "accurate":
                    data["plays"][play_key]["accurate_votes"] += 1
                elif vote_type == "wrong":
                    data["plays"][play_key]["wrong_votes"] += 1
                elif vote_type == "fire":
                    data["plays"][play_key]["fire_votes"] = data["plays"][play_key].get("fire_votes", 0) + 1
                log_entry = {
                    "timestamp": now_iso,
                    "session_id": body.get("session_id", "2026-10-31"),
                    "dataset_split": "eval_benchmark" if vote_type == "wrong" else "verified_train",
                    "event": "vote_play",
                    "play_key": play_key,
                    "vote": vote_type,
                    "ai_original": body.get("ai_original"),
                }

            elif action == "add_note" and play_key:
                note_id = f"note_{int(time.time() * 1000)}"
                note = {
                    "id": note_id,
                    "author": body.get("author", "Anonymous Baller").strip() or "Anonymous Baller",
                    "issue_type": body.get("issue_type", "Wrong Player / Stat"),
                    "claimed_player": body.get("claimed_player", ""),
                    "comment": body.get("comment", "").strip(),
                    "facts_votes": 0,
                    "cap_votes": 0,
                    "created_at": now_iso,
                }
                data["plays"][play_key]["notes"].append(note)
                data["plays"][play_key]["wrong_votes"] += 1
                log_entry = {
                    "timestamp": now_iso,
                    "session_id": body.get("session_id", "2026-10-31"),
                    "dataset_split": "hard_negative_eval_and_train",
                    "event": "play_correction",
                    "play_key": play_key,
                    "video_seconds": body.get("video_seconds"),
                    "ai_original": body.get("ai_original"),
                    "user_correction": note,
                }

            elif action == "vote_note" and play_key:
                note_id = body.get("note_id")
                vote_type = body.get("vote")
                for n in data["plays"][play_key]["notes"]:
                    if n["id"] == note_id:
                        if vote_type == "facts":
                            n["facts_votes"] = n.get("facts_votes", 0) + 1
                        elif vote_type == "cap":
                            n["cap_votes"] = n.get("cap_votes", 0) + 1
                        log_entry = {
                            "timestamp": now_iso,
                            "session_id": body.get("session_id", "2026-10-31"),
                            "event": "peer_verification_vote",
                            "play_key": play_key,
                            "note_id": note_id,
                            "vote": vote_type,
                            "facts_votes": n["facts_votes"],
                            "cap_votes": n["cap_votes"],
                        }
                        break

            elif action == "add_missing_play":
                sec = int(float(body.get("video_seconds", 0)))
                mm = sec // 60
                ss = sec % 60
                custom_play = {
                    "id": f"custom_{int(time.time() * 1000)}",
                    "s": sec,
                    "t": f"{mm:02d}:{ss:02d}",
                    "g": body.get("segment", "G2"),
                    "hoop": body.get("hoop", "Near"),
                    "player": body.get("player", "Unknown Player"),
                    "event_type": body.get("event_type", "MADE"),
                    "desc": body.get("desc", "").strip(),
                    "author": body.get("author", "Anonymous Baller").strip() or "Anonymous Baller",
                    "created_at": now_iso,
                }
                data["custom_plays"].append(custom_play)
                log_entry = {
                    "timestamp": now_iso,
                    "session_id": body.get("session_id", "2026-10-31"),
                    "dataset_split": "recall_failure_eval",
                    "event": "missing_play_added",
                    "custom_play": custom_play,
                }

            elif action == "map_crew_player":
                visual_id = body.get("visual_id", "").strip()
                real_name = body.get("real_name", "").strip()
                traits = body.get("traits", "").strip()
                footwear_gear = body.get("footwear_gear", "").strip()
                session_id = body.get("session_id", "2026-10-31")
                if visual_id and real_name:
                    data["crew_roster_map"][visual_id] = {
                        "real_name": real_name,
                        "traits": traits,
                        "footwear_gear": footwear_gear,
                        "updated_at": now_iso,
                    }
                    if "crew_master_roster" not in data or not isinstance(data["crew_master_roster"], dict):
                        data["crew_master_roster"] = load_crew_master_roster()
                    existing_master = data["crew_master_roster"].get(real_name, {})
                    outfit_hist = dict(existing_master.get("outfit_history") or {})
                    prev_session_outfits = outfit_hist.get(session_id, [])
                    if isinstance(prev_session_outfits, str):
                        prev_session_outfits = [prev_session_outfits] if prev_session_outfits else []
                    elif not isinstance(prev_session_outfits, list):
                        prev_session_outfits = []
                    if visual_id not in prev_session_outfits:
                        prev_session_outfits.append(visual_id)
                    outfit_hist[session_id] = prev_session_outfits

                    bio = dict(existing_master.get("biometric_anchors") or {})
                    if footwear_gear:
                        bio["footwear_and_gear"] = footwear_gear

                    data["crew_master_roster"][real_name] = {
                        "player_id": existing_master.get("player_id", f"crew_{real_name.lower().replace(' ', '_')}"),
                        "name": real_name,
                        "permanent_traits": traits or existing_master.get("permanent_traits", ""),
                        "biometric_anchors": bio,
                        "default_team_role": existing_master.get("default_team_role", "Crew Regular"),
                        "outfit_history": outfit_hist,
                        "updated_at": now_iso,
                    }
                    log_entry = {
                        "timestamp": now_iso,
                        "session_id": session_id,
                        "dataset_split": "reid_gallery_train",
                        "event": "crew_identity_mapping",
                        "visual_id": visual_id,
                        "real_name": real_name,
                        "traits": traits,
                        "footwear_gear": footwear_gear,
                    }

            elif action == "update_session_metadata":
                if "session_metadata" not in data:
                    data["session_metadata"] = {}
                data["session_metadata"]["game_format"] = body.get("game_format", "5v5_full_court")
                data["session_metadata"]["camera_angle"] = body.get("camera_angle", "corner_elevated")
                if "hoop_rois_4k" in body:
                    data["session_metadata"]["hoop_rois_4k"] = body["hoop_rois_4k"]
                data["session_metadata"]["updated_at"] = now_iso
                log_entry = {
                    "timestamp": now_iso,
                    "session_id": body.get("session_id", "2026-10-31"),
                    "event": "session_metadata_updated",
                    "game_format": data["session_metadata"]["game_format"],
                    "camera_angle": data["session_metadata"]["camera_angle"],
                    "hoop_rois_4k": data["session_metadata"].get("hoop_rois_4k"),
                }

            elif action == "collab_calibrate":
                session_id = str(body.get("session_id", "2026-10-31"))
                pkey = str(body.get("play_key", ""))
                if session_id and pkey:
                    if "collab_calibrations" not in data or not isinstance(data["collab_calibrations"], dict):
                        data["collab_calibrations"] = {}
                    if session_id not in data["collab_calibrations"]:
                        data["collab_calibrations"][session_id] = {}
                    prev_cal = dict(data["collab_calibrations"][session_id].get(pkey) or {})
                    new_cal = {
                        "play_key": pkey,
                        "status": body.get("status", prev_cal.get("status", "verified")),
                        "verified_player": body.get("verified_player", prev_cal.get("verified_player", "")),
                        "verified_assist": body.get("verified_assist", prev_cal.get("verified_assist", "")),
                        "start_s": body.get("start_s", prev_cal.get("start_s")),
                        "splash_s": body.get("splash_s", prev_cal.get("splash_s")),
                        "orig_s": body.get("orig_s", prev_cal.get("orig_s")),
                        "led_clock": body.get("led_clock", prev_cal.get("led_clock", "")),
                        "contributor": (body.get("contributor") or prev_cal.get("contributor") or "Crew Collab").strip(),
                        "updated_at": now_iso,
                    }
                    data["collab_calibrations"][session_id][pkey] = new_cal
                    drift_s = None
                    if new_cal.get("splash_s") is not None and new_cal.get("orig_s") is not None:
                        try:
                            drift_s = round(float(new_cal["splash_s"]) - float(new_cal["orig_s"]), 2)
                        except Exception:
                            drift_s = None
                    log_entry = {
                        "timestamp": now_iso,
                        "session_id": session_id,
                        "dataset_split": "collab_gold_verified",
                        "event": "collab_calibrate",
                        "play_key": pkey,
                        "drift_delta_s": drift_s,
                        "calibration": new_cal,
                    }

            elif action == "collab_tag_live":
                session_id = str(body.get("session_id", "2026-10-31"))
                sec = round(float(body.get("video_seconds", 0)), 1)
                mm = int(sec) // 60
                ss = int(sec) % 60
                if "collab_live_tags" not in data or not isinstance(data["collab_live_tags"], dict):
                    data["collab_live_tags"] = {}
                if session_id not in data["collab_live_tags"]:
                    data["collab_live_tags"][session_id] = []
                tag_obj = {
                    "id": f"ctag_{int(time.time() * 1000)}",
                    "s": max(0, int(round(sec - 3.5))),
                    "splash_s": sec,
                    "t": f"{mm:02d}:{ss:02d}",
                    "player": body.get("player", "#2 Mohamed"),
                    "action_type": body.get("action_type", "3-pt FG Made"),
                    "pts_added": int(body.get("pts_added", 3 if "3-pt" in str(body.get("action_type", "")) else (2 if "2-pt" in str(body.get("action_type", "")) else 0))),
                    "contributor": (body.get("contributor") or "Crew Collab").strip(),
                    "note": (body.get("note") or "").strip(),
                    "created_at": now_iso,
                }
                data["collab_live_tags"][session_id].append(tag_obj)
                log_entry = {
                    "timestamp": now_iso,
                    "session_id": session_id,
                    "dataset_split": "collab_live_crowd_tags",
                    "event": "collab_tag_live",
                    "tag": tag_obj,
                }

            save_feedback(data, log_entry)
            payload = json.dumps(data).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return

        self.send_error(404, "Endpoint not found")

    def send_head(self):
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        force_download = qs.get("download", ["0"])[0] == "1"

        if parsed.path.startswith("/majestic_games/") and parsed.path.endswith(".mp4"):
            fname = os.path.basename(parsed.path)
            sub_dir = "reels/" if "/reels/" in parsed.path else ""
            if IS_CLOUD_RUN:
                self.send_response(302)
                self.send_header("Location", f"https://storage.googleapis.com/basketball-highlights-store/majestic/{sub_dir}{fname}")
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                return None
            oct_path = os.path.join("majestic_oct2026", fname)
            wtn_path = os.path.join("majestic_wtn", fname)
            c7_path = os.path.join("majestic_crew7", fname)
            reel_path = os.path.join("majestic_games", "reels", fname)
            if os.path.exists(oct_path):
                path = oct_path
            elif os.path.exists(wtn_path):
                path = wtn_path
            elif os.path.exists(c7_path):
                path = c7_path
            elif os.path.exists(reel_path):
                path = reel_path
            else:
                path = os.path.join("majestic_games", fname)
        elif parsed.path.endswith("20261031_full_game.mp4"):
            if IS_CLOUD_RUN:
                # Redirect video streaming & download requests on Cloud Run directly to Google Cloud Storage Edge CDN
                # so browser HTTP 206 byte-ranges never hit Cloud Run's 32 MB limit or GCS FUSE stale file handles.
                self.send_response(302)
                self.send_header("Location", PUBLIC_GCS_VIDEO_URL)
                self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                return None
            path = VIDEO_FILE if os.path.exists(VIDEO_FILE) else self.translate_path(parsed.path)
        else:
            path = self.translate_path(parsed.path)

        if os.path.isdir(path):
            return super().send_head()
        ctype = self.guess_type(path)
        try:
            f = open(path, "rb")
        except OSError:
            self.send_error(404, "File not found")
            return None

        fs = os.fstat(f.fileno())
        file_len = fs.st_size
        range_header = self.headers.get("Range")

        if range_header and not force_download:
            m = re.match(r"bytes=(\d+)-(\d*)", range_header)
            if m:
                start = int(m.group(1))
                if m.group(2):
                    end = int(m.group(2))
                else:
                    end = min(start + MAX_RANGE_CHUNK - 1, file_len - 1) if IS_CLOUD_RUN else (file_len - 1)
                if start >= file_len:
                    f.close()
                    self.send_error(416, "Requested Range Not Satisfiable")
                    return None
                end = min(end, file_len - 1)
                length = end - start + 1

                self.send_response(206)
                self.send_header("Content-type", ctype)
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("Content-Range", f"bytes {start}-{end}/{file_len}")
                self.send_header("Content-Length", str(length))
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Last-Modified", self.date_time_string(fs.st_mtime))
                self.end_headers()
                f.seek(start)
                self._range_remaining = length
                return f

        self.send_response(200)
        self.send_header("Content-type", ctype)
        if force_download:
            self.send_header("Content-Disposition", f'attachment; filename="{os.path.basename(path)}"')
        self.send_header("Content-Length", str(file_len))
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Last-Modified", self.date_time_string(fs.st_mtime))
        self.end_headers()
        self._range_remaining = file_len
        return f

    def copyfile(self, source, outputfile):
        remaining = getattr(self, "_range_remaining", None)
        if remaining is None:
            return super().copyfile(source, outputfile)
        bufsize = 64 * 1024
        try:
            while remaining > 0:
                chunk = source.read(min(bufsize, remaining))
                if not chunk:
                    break
                outputfile.write(chunk)
                remaining -= len(chunk)
        except (ConnectionResetError, BrokenPipeError, ConnectionAbortedError):
            pass


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    port = int(os.environ.get("PORT", "8080"))
    host = "0.0.0.0" if IS_CLOUD_RUN or "PORT" in os.environ else "127.0.0.1"
    server = ThreadingHTTPServer((host, port), RangeAndFeedbackHandler)
    print(f"Serving ESPN Film Room + Highlight Clip Downloader + Training API on http://{host}:{port}")
    server.serve_forever()
