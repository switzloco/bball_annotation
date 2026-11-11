import cv2
import json
import numpy as np
import os
import subprocess

VID = r"c:\dev\bball_annotation\majestic_oct2026\latto_talent_wk4_SdT-2krO6uY.mp4"
OUT_DIR = r"c:\dev\bball_annotation\majestic_oct2026\scouting_assets"
os.makedirs(OUT_DIR, exist_ok=True)

ARTIFACT_DIR = r"C:\Users\Nick\.gemini\antigravity\brain\92e691fb-4334-4d76-9835-87d6d959086f"
SCRATCH_DIR = os.path.join(ARTIFACT_DIR, "scratch", "lt_scouting_segs")
os.makedirs(SCRATCH_DIR, exist_ok=True)


def build_logo():
    sz = 256
    img = np.zeros((sz, sz, 3), dtype=np.uint8)
    # Deep obsidian gradient background
    for y in range(sz):
        t = y / float(sz - 1)
        b = int(38 * (1 - t) + 18 * t)
        g = int(20 * (1 - t) + 10 * t)
        r = int(42 * (1 - t) + 22 * t)
        img[y, :] = (b, g, r)

    # Outer hot-pink & championship-gold shield frame
    cv2.rectangle(img, (8, 8), (sz - 9, sz - 9), (145, 65, 244), 6, cv2.LINE_AA)
    cv2.rectangle(img, (18, 18), (sz - 19, sz - 19), (90, 210, 255), 2, cv2.LINE_AA)

    # Top pill "HOLIDAY '26 D2"
    cv2.rectangle(img, (40, 30), (sz - 40, 60), (130, 45, 230), -1)
    cv2.putText(img, "HOLIDAY '26 D2", (52, 51), cv2.FONT_HERSHEY_SIMPLEX, 0.56, (255, 255, 255), 2, cv2.LINE_AA)

    # Bold "LT" monogram
    cv2.putText(img, "LT", (58, 156), cv2.FONT_HERSHEY_DUPLEX, 3.4, (12, 12, 18), 12, cv2.LINE_AA)
    cv2.putText(img, "LT", (54, 152), cv2.FONT_HERSHEY_DUPLEX, 3.4, (165, 85, 255), 8, cv2.LINE_AA)
    cv2.putText(img, "LT", (54, 152), cv2.FONT_HERSHEY_DUPLEX, 3.4, (255, 255, 255), 3, cv2.LINE_AA)

    # Bottom text
    cv2.putText(img, "LATTO TALENT", (37, 198), cv2.FONT_HERSHEY_SIMPLEX, 0.78, (95, 220, 255), 2, cv2.LINE_AA)
    cv2.putText(img, "3-1  |  PINK JERSEYS", (44, 224), cv2.FONT_HERSHEY_SIMPLEX, 0.50, (215, 225, 240), 1, cv2.LINE_AA)

    out_p = os.path.join(OUT_DIR, "latto_talent_logo.png")
    cv2.imwrite(out_p, img)
    print(f"Saved logo -> {out_p}")


def safe_crop_resize(frame, box, target_w, target_h):
    H, W = frame.shape[:2]
    x1, y1, x2, y2 = box
    x1 = max(0, min(W - 20, int(x1)))
    y1 = max(0, min(H - 20, int(y1)))
    x2 = max(x1 + 20, min(W, int(x2)))
    y2 = max(y1 + 20, min(H, int(y2)))
    crop = frame[y1:y2, x1:x2]
    return cv2.resize(crop, (target_w, target_h), interpolation=cv2.INTER_LANCZOS4)


# 8 1080p-Sourced Split-View Player Scouting Cards (960x540 = 16:9)
PLAYER_CARDS = [
    {
        "file": "lt_p_9_diallo.jpg",
        "num_tag": "#9 CLOSE-UP",
        "close_t": 717.5,
        "close_box": (950, 220, 1410, 720),   # 460x500 close-up of #9 Diallo Holmes (headband + braids + #9)
        "act_t": 1629.5,
        "act_box": (480, 170, 1220, 760),     # Coast-to-coast grab-and-go push after block
        "header": "#9 DIALLO HOLMES (20.3 PPG, 10.0 RPG, 88% FT)",
        "sub": "Point-Forward | Pull-Up 3PT (10x 3PM) & FT Magnet (21/24 FT)"
    },
    {
        "file": "lt_p_1_sean.jpg",
        "num_tag": "#1 CLOSE-UP",
        "close_t": 1943.8,
        "close_box": (980, 310, 1520, 900),   # Huge foreground #1 Sean Steven
        "act_t": 3329.4,
        "act_box": (980, 170, 1700, 750),     # Crunch-time right-hand paint drive (6/6 2PT)
        "header": "#1 SEAN STEVEN (11.5 PPG, 6/6 2PT, 7 AST->#9)",
        "sub": "Primary Ball-Handler | 100% Paint Finisher & #1 Feeder to Diallo"
    },
    {
        "file": "lt_p_5_brandon.jpg",
        "num_tag": "#5 CLOSE-UP",
        "close_t": 525.0,
        "close_box": (720, 310, 1180, 810),   # Clear #5 Brandon Nguyen at center court
        "act_t": 1946.8,
        "act_box": (80, 140, 740, 670),       # H1 buzzer-beating left-corner 3PT release
        "header": "#5 BRANDON NGUYEN (14 PTS, 4x 3PM in Wk 4)",
        "sub": "Pure Catch-and-Shoot Corner & Wing Sniper (0 TOV in 4 GP)"
    },
    {
        "file": "lt_p_3_mahaan.jpg",
        "num_tag": "#3 CLOSE-UP",
        "close_t": 588.0,
        "close_box": (1520, 220, 1920, 660),  # Front-facing #3 Mahaan (goggles + #3 pink jersey)
        "act_t": 3258.2,
        "act_box": (1180, 180, 1860, 730),    # Crunch-time go-ahead 3PT (62-59 @ 2:15)
        "header": "#3 MAHAAN (8.5 PPG, 80% FT, Wk 4 Go-Ahead 3PT)",
        "sub": "Physical Wing Slasher & Late-Game Spacer (10 PTS, 5 REB vs MIS2)"
    },
    {
        "file": "lt_p_8_radhir.jpg",
        "num_tag": "#8 CLOSE-UP",
        "close_t": 623.1,
        "close_box": (520, 250, 980, 750),    # Huge #8 Radhir in foreground
        "act_t": 1369.5,
        "act_box": (680, 170, 1340, 700),     # Top-of-key catch-and-shoot 3PT
        "header": "#8 RADHIR (7.3 PPG, 4.3 RPG, 2.7 Fouls/G)",
        "sub": "High-Motor 3-and-D Wing Connector | Gambles on Passing Lanes"
    },
    {
        "file": "lt_p_4_lazar.jpg",
        "num_tag": "#4 CLOSE-UP",
        "close_t": 2583.5,
        "close_box": (560, 290, 1080, 860),   # Huge #4 Lazar in foreground
        "act_t": 1207.3,
        "act_box": (240, 160, 960, 730),      # Steal & coast-to-coast breakaway layup right at left rim!
        "header": "#4 LAZAR & #23 DILBAR (83% 2PT | 8.0 PPG)",
        "sub": "Opportunistic Baseline/45 Cutters & Transition Leak-Out Threats"
    },
    {
        "file": "lt_p_2_troy.jpg",
        "num_tag": "#2 CLOSE-UP",
        "close_t": 1945.5,
        "close_box": (1320, 300, 1840, 870),  # Huge #2 Troy (black headband) in foreground
        "act_t": 2569.0,
        "act_box": (980, 170, 1680, 730),     # Rim-running transition finish at right hoop
        "header": "#2 TROY (23 PTS & 11 REB vs CU in Mar 1 Champ!)",
        "sub": "Paint Finisher, Shot-Blocker & Glass Cleaner (0 3PA - Sag & Box Out!)"
    },
    {
        "file": "lt_p_10_ty.jpg",
        "num_tag": "#10 CLOSE-UP",
        "close_t": 250.0,
        "close_box": (650, 330, 1110, 830),   # Clear #10 Ty in foreground
        "act_t": 972.8,
        "act_box": (20, 180, 680, 710),       # Left-corner catch-and-shoot 3PT release
        "header": "#10 TY (2/2 3PT) & #6 RAJ (5/5 2PT Reserve Big)",
        "sub": "Bench Corner 3PT Spacer (#10) + Non-Shooting Foul-Prone Big (#6)"
    },
]


def build_player_cards(cap):
    card_w, card_h = 960, 540
    banner_h = 96
    top_h = card_h - banner_h   # 444px
    left_w = 408                # Close-up portrait
    right_w = card_w - left_w - 4  # 548px action frame

    rendered_cards = []
    for pc in PLAYER_CARDS:
        cap.set(cv2.CAP_PROP_POS_MSEC, pc["close_t"] * 1000.0)
        ok1, fr1 = cap.read()
        cap.set(cv2.CAP_PROP_POS_MSEC, pc["act_t"] * 1000.0)
        ok2, fr2 = cap.read()
        if not ok1 or not ok2:
            raise RuntimeError(f"Failed reading frames for {pc['file']}")

        left_img = safe_crop_resize(fr1, pc["close_box"], left_w, top_h)
        right_img = safe_crop_resize(fr2, pc["act_box"], right_w, top_h)

        canvas = np.zeros((card_h, card_w, 3), dtype=np.uint8)
        canvas[:top_h, :left_w] = left_img
        canvas[:top_h, left_w:left_w + 4] = (65, 200, 255)  # Gold divider
        canvas[:top_h, left_w + 4:] = right_img

        # Top-left pill on close-up
        cv2.rectangle(canvas, (12, 12), (188, 44), (16, 18, 28), -1)
        cv2.rectangle(canvas, (12, 12), (188, 44), (65, 200, 255), 2)
        cv2.putText(canvas, pc["num_tag"], (22, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.58, (95, 225, 255), 2, cv2.LINE_AA)

        # Top-left pill on action panel
        ax = left_w + 16
        cv2.rectangle(canvas, (ax, 12), (ax + 225, 44), (16, 18, 28), -1)
        cv2.rectangle(canvas, (ax, 12), (ax + 225, 44), (245, 190, 56), 2)
        cv2.putText(canvas, "SIGNATURE TENDENCY", (ax + 12, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.56, (255, 225, 115), 2, cv2.LINE_AA)

        # Bottom banner
        canvas[top_h:top_h + 3, :] = (155, 65, 245)  # Hot-pink accent rule
        canvas[top_h + 3:, :] = (18, 16, 26)
        cv2.putText(canvas, pc["header"], (18, top_h + 42), cv2.FONT_HERSHEY_SIMPLEX, 0.76, (255, 255, 255), 2, cv2.LINE_AA)
        cv2.putText(canvas, pc["sub"], (18, top_h + 76), cv2.FONT_HERSHEY_SIMPLEX, 0.60, (105, 225, 255), 2, cv2.LINE_AA)

        out_p = os.path.join(OUT_DIR, pc["file"])
        cv2.imwrite(out_p, canvas, [cv2.IMWRITE_JPEG_QUALITY, 93])
        rendered_cards.append(cv2.resize(canvas, (480, 270), interpolation=cv2.INTER_AREA))
        print(f"Saved card -> {out_p}")

    proof = np.vstack([
        np.hstack(rendered_cards[:4]),
        np.hstack(rendered_cards[4:])
    ])
    proof_p = os.path.join(ARTIFACT_DIR, "lt_scouting_cards_proof.jpg")
    cv2.imwrite(proof_p, proof, [cv2.IMWRITE_JPEG_QUALITY, 92])
    print(f"Saved 8-card proof grid -> {proof_p}")


# 11-Clip 1080p Full HD Scouting Tape Reel (~93.5s) covering every scouted threat
CLIPS = [
    {
        "idx": 1,
        "player": "#9 Diallo Holmes",
        "chap_title": "Pull-Up Right-Wing 3PT (20.3 PPG, 10x 3PM, 88% FT)",
        "start_s": 620.5,
        "end_s": 629.5,
        "proof_s": 625.2,
        "pip_side": "right",
        "zoom_box": (440, 130, 1240, 618),
        "badge": "CLIP 1/11 | #1 THREAT: #9 DIALLO HOLMES (20.3 PPG, 10.0 RPG)",
        "title": "#9 DIALLO HOLMES ELEVATES FOR PULL-UP WING 3-POINTER!",
        "sub": "32.4% of LT scoring - run him off 3PT arc & wall up WITHOUT fouling (88% FT!)"
    },
    {
        "idx": 2,
        "player": "#9 Diallo Holmes",
        "chap_title": "Rim Block -> Coast-to-Coast Dime to #1 Sean (3.3 APG, 1.3 BPG)",
        "start_s": 1625.0,
        "end_s": 1634.5,
        "proof_s": 1629.5,
        "pip_side": "right",
        "zoom_box": (520, 140, 1320, 628),
        "badge": "CLIP 2/11 | POINT-FORWARD TRANSITION ENGINE (6 AST IN WK 4)",
        "title": "#9 DIALLO BLOCKS IT & PUSHES COAST-TO-COAST TO #1 SEAN!",
        "sub": "Grabs boards & ignites fast breaks - sprint back & stop ball at halfcourt!"
    },
    {
        "idx": 3,
        "player": "#9 Diallo Holmes",
        "chap_title": "Clutch 2nd-Half Kickout 3PT off #1 Sean Penetration (7x AST!)",
        "start_s": 3024.5,
        "end_s": 3033.0,
        "proof_s": 3028.8,
        "pip_side": "left",
        "zoom_box": (820, 140, 1620, 628),
        "badge": "CLIP 3/11 | PRIMARY TWO-MAN ACTION: #1 SEAN -> #9 DIALLO",
        "title": "#1 SEAN COLLAPSES PAINT & KICKS TO #9 DIALLO FOR CLUTCH 3PT!",
        "sub": "#1 Sean has 7 direct assists to #9 Diallo - stay attached on drive-and-kick!"
    },
    {
        "idx": 4,
        "player": "#1 Sean Steven",
        "chap_title": "Early Pull-Up 3PT (11.5 PPG - Streaky 3/16 3PT in Wks 3-4)",
        "start_s": 654.5,
        "end_s": 663.0,
        "proof_s": 658.2,
        "pip_side": "right",
        "zoom_box": (260, 130, 1060, 618),
        "badge": "CLIP 4/11 | #2 SCORER: #1 SEAN STEVEN (11.5 PPG, 2.5 APG)",
        "title": "#1 SEAN STEVEN PULLS UP FROM THREE (7x 3PM, 19% IN WKS 3-4)",
        "sub": "High-volume 3PT shooter (1/9 vs MIS2) - contest without flying past his right hand!"
    },
    {
        "idx": 5,
        "player": "#1 Sean Steven",
        "chap_title": "Crunch-Time Right-Hand Lane Drive (6/6 2PT = 100% Inside!)",
        "start_s": 3324.5,
        "end_s": 3333.0,
        "proof_s": 3329.0,
        "pip_side": "left",
        "zoom_box": (840, 140, 1640, 628),
        "badge": "CLIP 5/11 | DEADLY INSIDE: #1 SEAN STEVEN (6/6 2PT IN WKS 3-4)",
        "title": "1:05 LEFT: #1 SEAN STEVEN SPLITS THE LANE FOR DAGGER 2PT!",
        "sub": "100% on 2PT attempts over last 2 weeks - cut off middle/right-hand drives!"
    },
    {
        "idx": 6,
        "player": "#5 Brandon Nguyen",
        "chap_title": "H1 Buzzer-Beating Corner 3PT off #9 Diallo Kickout (4x 3PM)",
        "start_s": 1942.5,
        "end_s": 1951.0,
        "proof_s": 1947.0,
        "pip_side": "right",
        "zoom_box": (80, 120, 880, 608),
        "badge": "CLIP 6/11 | CORNER SNIPER: #5 BRANDON NGUYEN (4/10 3PT IN WK 4)",
        "title": "H1 BUZZER! #5 BRANDON NGUYEN DRAINS LEFT-CORNER 3PT!",
        "sub": "14 PTS on 4 triples vs MIS2 (0 TOV) - ZERO stunting/helping off #5 Brandon!"
    },
    {
        "idx": 7,
        "player": "#3 Mahaan",
        "chap_title": "Crunch-Time Go-Ahead Right-Corner 3PT (8.5 PPG, 80% FT)",
        "start_s": 3254.0,
        "end_s": 3262.5,
        "proof_s": 3258.4,
        "pip_side": "left",
        "zoom_box": (1060, 140, 1860, 628),
        "badge": "CLIP 7/11 | CLUTCH WING: #3 MAHAAN (8.5 PPG, 5/8 2PT, 4/5 FT)",
        "title": "2:15 LEFT (TIED 59-59): #3 MAHAAN HITS GO-AHEAD CORNER 3PT!",
        "sub": "Physical mid-season wing addition - close out balanced & wall up on slashes"
    },
    {
        "idx": 8,
        "player": "#8 Radhir",
        "chap_title": "Wing Catch-and-Shoot 3PT off #9 Diallo Pass (7.3 PPG, 2.7 PF/G)",
        "start_s": 1366.0,
        "end_s": 1374.5,
        "proof_s": 1369.8,
        "pip_side": "right",
        "zoom_box": (60, 140, 860, 628),
        "badge": "CLIP 8/11 | 3-AND-D CONNECTOR: #8 RADHIR (7.3 PPG, 4.3 RPG)",
        "title": "#8 RADHIR STEPS INTO WING 3PT OFF #9 DIALLO PASS!",
        "sub": "Active ball-hawk (2.7 fouls/G) - attack him off the dribble to draw early fouls!"
    },
    {
        "idx": 9,
        "player": "#4 Lazar",
        "chap_title": "Passing-Lane Steal & Breakaway Finish (5/6 2PT = 83.3%)",
        "start_s": 1203.0,
        "end_s": 1211.5,
        "proof_s": 1207.3,
        "pip_side": "right",
        "zoom_box": (200, 130, 1000, 618),
        "badge": "CLIP 9/11 | CUTTER & THIEF: #4 LAZAR (8 PTS, 4/5 2PT IN WK 4)",
        "title": "#4 LAZAR JUMPS THE PASSING LANE FOR BREAKAWAY FINISH!",
        "sub": "83% 2PT finisher on cuts & steals (0/2 3PT) - crisp passes & track back-cuts!"
    },
    {
        "idx": 10,
        "player": "#2 Troy",
        "chap_title": "Transition Rim Run & Paint Finish (23p/11r vs CU in Mar 1 Champ!)",
        "start_s": 2564.5,
        "end_s": 2572.5,
        "proof_s": 2569.0,
        "pip_side": "left",
        "zoom_box": (940, 140, 1740, 628),
        "badge": "CLIP 10/11 | REVENGE ALERT: #2 TROY (23 PTS, 11 REB VS CU MAR 1!)",
        "title": "#2 TROY RUNS THE FLOOR & FINISHES INSIDE (6 REB, 2 STL, 1 BLK)",
        "sub": "Just returned in Wk 4! Non-shooter (0 3PA) - SAG INTO PAINT & BOX HIM OUT!"
    },
    {
        "idx": 11,
        "player": "#10 Ty",
        "chap_title": "Bench Left-Corner 3PT off #9 Diallo Skip Pass (2/2 3PT = 100%)",
        "start_s": 969.0,
        "end_s": 976.5,
        "proof_s": 972.8,
        "pip_side": "right",
        "zoom_box": (40, 140, 840, 628),
        "badge": "CLIP 11/11 | BENCH SPACER: #10 TY (2/2 3PT IN WKS 3-4)",
        "title": "#9 DIALLO SKIPS TO #10 TY FOR LEFT-CORNER 3-POINTER!",
        "sub": "Respect #10 Ty in corners (2/2 3PT), but sag off non-shooting big #6 Raj!"
    },
]

OUT_W, OUT_H = 1920, 1080
PIP_W, PIP_H = 520, 318


def decorate_scouting_frame(frame, c):
    if frame.shape[1] != OUT_W or frame.shape[0] != OUT_H:
        frame = cv2.resize(frame, (OUT_W, OUT_H), interpolation=cv2.INTER_LANCZOS4)
    out = frame.copy()

    zx1, zy1, zx2, zy2 = c["zoom_box"]
    pip = safe_crop_resize(frame, (zx1, zy1, zx2, zy2), PIP_W, PIP_H)

    px = 38 if c["pip_side"] == "left" else (OUT_W - PIP_W - 38)
    py = 34

    cv2.rectangle(out, (px + 6, py + 6), (px + PIP_W + 6, py + PIP_H + 6), (8, 10, 16), -1)
    out[py:py + PIP_H, px:px + PIP_W] = pip
    # Hot-pink + cyan scouting border
    cv2.rectangle(out, (px, py), (px + PIP_W, py + PIP_H), (165, 75, 250), 3)

    cv2.rectangle(out, (px, py), (px + 330, py + 32), (14, 16, 26), -1)
    cv2.rectangle(out, (px, py), (px + 6, py + 32), (165, 75, 250), -1)
    cv2.putText(out, "SCOUTING ISO 2.0x | PINK JERSEYS", (px + 14, py + 22),
                cv2.FONT_HERSHEY_SIMPLEX, 0.50, (255, 215, 110), 2, cv2.LINE_AA)

    overlay = out.copy()
    bx1, by1, bx2, by2 = 48, OUT_H - 146, OUT_W - 48, OUT_H - 28
    cv2.rectangle(overlay, (bx1, by1), (bx2, by2), (14, 16, 26), -1)
    cv2.rectangle(overlay, (bx1, by1), (bx1 + 10, by2), (165, 75, 250), -1)
    out = cv2.addWeighted(overlay, 0.86, out, 0.14, 0)

    cv2.putText(out, f"NOV 15 SCOUTING: LATTO TALENT (3-1)  |  {c['badge']}", (bx1 + 28, by1 + 34),
                cv2.FONT_HERSHEY_SIMPLEX, 0.68, (110, 225, 255), 2, cv2.LINE_AA)
    cv2.putText(out, c["title"], (bx1 + 28, by1 + 74),
                cv2.FONT_HERSHEY_SIMPLEX, 0.86, (255, 255, 255), 2, cv2.LINE_AA)
    cv2.putText(out, c["sub"], (bx1 + 28, by1 + 105),
                cv2.FONT_HERSHEY_SIMPLEX, 0.63, (210, 220, 235), 1, cv2.LINE_AA)

    cv2.rectangle(out, (bx2 - 175, by1 + 16), (bx2 - 22, by1 + 52), (145, 55, 235), -1)
    cv2.putText(out, "1080p SCOUT", (bx2 - 160, by1 + 41),
                cv2.FONT_HERSHEY_SIMPLEX, 0.58, (255, 255, 255), 2, cv2.LINE_AA)
    return out


def build_scouting_reel(cap):
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    fps_str = "30" if abs(fps - 30.0) < 0.02 else "30000/1001"

    segment_files = []
    proof_tiles = []
    chapters = []
    cum_sec = 0.0

    for c in CLIPS:
        dur = c["end_s"] - c["start_s"]
        n_frames = int(round(dur * fps))
        mm = int(cum_sec) // 60
        ss = int(cum_sec) % 60
        chapters.append({
            "sec": round(cum_sec, 1),
            "time": f"{mm}:{ss:02d}",
            "player": c["player"],
            "title": c["chap_title"]
        })

        cap.set(cv2.CAP_PROP_POS_MSEC, c["proof_s"] * 1000.0)
        ok_p, pframe = cap.read()
        if ok_p:
            dec_p = decorate_scouting_frame(pframe, c)
            proof_tiles.append(cv2.resize(dec_p, (640, 360), interpolation=cv2.INTER_AREA))

        seg_path = os.path.join(SCRATCH_DIR, f"lt_scout_seg_1080p_{c['idx']:02d}.mp4")
        cmd = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "rawvideo", "-vcodec", "rawvideo",
            "-pix_fmt", "bgr24", "-s", f"{OUT_W}x{OUT_H}", "-r", fps_str,
            "-i", "-",
            "-ss", f"{c['start_s']:.3f}", "-t", f"{dur:.3f}", "-i", VID,
            "-map", "0:v:0", "-map", "1:a:0?",
            "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-profile:v", "high", "-level", "4.1", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2",
            "-shortest", seg_path
        ]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        cap.set(cv2.CAP_PROP_POS_MSEC, c["start_s"] * 1000.0)
        written = 0
        for _ in range(n_frames):
            ok, frame = cap.read()
            if not ok:
                break
            proc.stdin.write(decorate_scouting_frame(frame, c).tobytes())
            written += 1
        proc.stdin.close()
        ret = proc.wait()
        if ret != 0:
            raise RuntimeError(f"ffmpeg failed on clip {c['idx']} ({ret})")

        actual_dur = written / fps
        print(f"Encoded Scouting Clip {c['idx']:02d}/11 ({written}f = {actual_dur:.2f}s, start={cum_sec:.1f}s) -> {c['player']}")
        cum_sec += actual_dur
        segment_files.append(seg_path)

    concat_txt = os.path.join(SCRATCH_DIR, "concat_lt.txt")
    with open(concat_txt, "w", encoding="utf-8") as f:
        for sf in segment_files:
            f.write(f"file '{sf.replace(chr(92), '/')}'\n")

    out_reel = os.path.join(OUT_DIR, "latto_talent_scouting_tape_1080p.mp4")
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "concat", "-safe", "0", "-i", concat_txt,
        "-c", "copy", "-movflags", "+faststart", out_reel
    ], check=True)

    while len(proof_tiles) % 2 != 0:
        proof_tiles.append(np.zeros((360, 640, 3), dtype=np.uint8))
    rows = [np.hstack([proof_tiles[i], proof_tiles[i + 1]]) for i in range(0, len(proof_tiles), 2)]
    proof_p = os.path.join(ARTIFACT_DIR, "lt_scouting_reel_proof.jpg")
    cv2.imwrite(proof_p, np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 92])

    meta_p = os.path.join(SCRATCH_DIR, "lt_chapters.json")
    with open(meta_p, "w", encoding="utf-8") as f:
        json.dump({"duration_s": round(cum_sec, 1), "chapters": chapters}, f, indent=2)

    pr = subprocess.run([
        "ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=codec_name,width,height,r_frame_rate,bit_rate:format=duration,size",
        "-of", "default=noprint_wrappers=1", out_reel
    ], capture_output=True, text=True)
    print("=== LATTO TALENT 1080p SCOUTING REEL FFPROBE ===")
    print(pr.stdout)
    print(f"Saved chapters -> {meta_p}")
    print(f"Saved reel proof -> {proof_p}")


if __name__ == "__main__":
    build_logo()
    cap = cv2.VideoCapture(VID)
    build_player_cards(cap)
    build_scouting_reel(cap)
    cap.release()
