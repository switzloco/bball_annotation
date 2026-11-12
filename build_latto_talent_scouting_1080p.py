import cv2
import json
import numpy as np
import os
import subprocess
import wave

VID = r"c:\dev\bball_annotation\majestic_oct2026\latto_talent_wk4_SdT-2krO6uY.mp4"
OUT_DIR = r"c:\dev\bball_annotation\majestic_oct2026\scouting_assets"
os.makedirs(OUT_DIR, exist_ok=True)

ARTIFACT_DIR = r"C:\Users\Nick\.gemini\antigravity\brain\92e691fb-4334-4d76-9835-87d6d959086f"
SCRATCH_DIR = os.path.join(ARTIFACT_DIR, "scratch", "lt_scouting_segs")
os.makedirs(SCRATCH_DIR, exist_ok=True)


def build_logo():
    sz = 256
    img = np.zeros((sz, sz, 3), dtype=np.uint8)
    for y in range(sz):
        t = y / float(sz - 1)
        b = int(38 * (1 - t) + 18 * t)
        g = int(20 * (1 - t) + 10 * t)
        r = int(42 * (1 - t) + 22 * t)
        img[y, :] = (b, g, r)

    cv2.rectangle(img, (8, 8), (sz - 9, sz - 9), (145, 65, 244), 6, cv2.LINE_AA)
    cv2.rectangle(img, (18, 18), (sz - 19, sz - 19), (90, 210, 255), 2, cv2.LINE_AA)

    cv2.rectangle(img, (40, 30), (sz - 40, 60), (130, 45, 230), -1)
    cv2.putText(img, "HOLIDAY '26 D2", (52, 51), cv2.FONT_HERSHEY_SIMPLEX, 0.56, (255, 255, 255), 2, cv2.LINE_AA)

    cv2.putText(img, "LT", (58, 156), cv2.FONT_HERSHEY_DUPLEX, 3.4, (12, 12, 18), 12, cv2.LINE_AA)
    cv2.putText(img, "LT", (54, 152), cv2.FONT_HERSHEY_DUPLEX, 3.4, (165, 85, 255), 8, cv2.LINE_AA)
    cv2.putText(img, "LT", (54, 152), cv2.FONT_HERSHEY_DUPLEX, 3.4, (255, 255, 255), 3, cv2.LINE_AA)

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


PLAYER_CARDS = [
    {
        "file": "lt_p_9_diallo.jpg",
        "num_tag": "#9 CLOSE-UP",
        "close_t": 717.5,
        "close_box": (950, 220, 1410, 720),
        "act_t": 1629.5,
        "act_box": (480, 170, 1220, 760),
        "header": "#9 DIALLO HOLMES (20.3 PPG, 10.0 RPG, 88% FT)",
        "sub": "Point-Forward | Pull-Up 3PT (10x 3PM) & FT Magnet (21/24 FT)"
    },
    {
        "file": "lt_p_1_sean.jpg",
        "num_tag": "#1 CLOSE-UP",
        "close_t": 1943.8,
        "close_box": (980, 310, 1520, 900),
        "act_t": 3329.4,
        "act_box": (980, 170, 1700, 750),
        "header": "#1 SEAN STEVEN (11.5 PPG, 6/6 2PT, 7 AST->#9)",
        "sub": "Primary Ball-Handler | 100% Paint Finisher & #1 Feeder to Diallo"
    },
    {
        "file": "lt_p_5_brandon.jpg",
        "num_tag": "#5 CLOSE-UP",
        "close_t": 525.0,
        "close_box": (720, 310, 1180, 810),
        "act_t": 1946.8,
        "act_box": (80, 140, 740, 670),
        "header": "#5 BRANDON NGUYEN (14 PTS, 4x 3PM in Wk 4)",
        "sub": "Pure Catch-and-Shoot Corner & Wing Sniper (0 TOV in 4 GP)"
    },
    {
        "file": "lt_p_3_mahaan.jpg",
        "num_tag": "#3 CLOSE-UP",
        "close_t": 588.0,
        "close_box": (1520, 220, 1920, 660),
        "act_t": 3258.2,
        "act_box": (1180, 180, 1860, 730),
        "header": "#3 MAHAAN (8.5 PPG, 80% FT, Wk 4 Go-Ahead 3PT)",
        "sub": "Physical Wing Slasher & Late-Game Spacer (10 PTS, 5 REB vs MIS2)"
    },
    {
        "file": "lt_p_8_radhir.jpg",
        "num_tag": "#8 CLOSE-UP",
        "close_t": 623.1,
        "close_box": (520, 250, 980, 750),
        "act_t": 2587.0,
        "act_box": (580, 150, 1280, 700),
        "header": "#8 RADHIR (7.3 PPG, 4.3 RPG, 2.7 Fouls/G)",
        "sub": "High-Motor 3-and-D Wing Connector | Gambles on Passing Lanes"
    },
    {
        "file": "lt_p_4_lazar.jpg",
        "num_tag": "#4 CLOSE-UP",
        "close_t": 2583.5,
        "close_box": (560, 290, 1080, 860),
        "act_t": 1205.5,
        "act_box": (240, 150, 960, 720),
        "header": "#4 LAZAR & #23 DILBAR (83% 2PT | 8.0 PPG)",
        "sub": "Opportunistic Baseline/45 Cutters & Transition Leak-Out Threats"
    },
    {
        "file": "lt_p_2_troy.jpg",
        "num_tag": "#2 CLOSE-UP",
        "close_t": 1945.5,
        "close_box": (1320, 300, 1840, 870),
        "act_t": 2569.0,
        "act_box": (980, 170, 1680, 730),
        "header": "#2 TROY (23 PTS & 11 REB vs CU in Mar 1 Champ!)",
        "sub": "Paint Finisher, Shot-Blocker & Glass Cleaner (0 3PA - Sag & Box Out!)"
    },
    {
        "file": "lt_p_10_ty.jpg",
        "num_tag": "#10 CLOSE-UP",
        "close_t": 250.0,
        "close_box": (650, 330, 1110, 830),
        "act_t": 973.4,
        "act_box": (20, 180, 680, 710),
        "header": "#10 TY (2/2 3PT) & #6 RAJ (5/5 2PT Reserve Big)",
        "sub": "Bench Corner 3PT Spacer (#10) + Non-Shooting Foul-Prone Big (#6)"
    },
]


def build_player_cards(cap):
    card_w, card_h = 960, 540
    banner_h = 96
    top_h = card_h - banner_h
    left_w = 408
    right_w = card_w - left_w - 4

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
        canvas[:top_h, left_w:left_w + 4] = (65, 200, 255)
        canvas[:top_h, left_w + 4:] = right_img

        cv2.rectangle(canvas, (12, 12), (188, 44), (16, 18, 28), -1)
        cv2.rectangle(canvas, (12, 12), (188, 44), (65, 200, 255), 2)
        cv2.putText(canvas, pc["num_tag"], (22, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.58, (95, 225, 255), 2, cv2.LINE_AA)

        ax = left_w + 16
        cv2.rectangle(canvas, (ax, 12), (ax + 225, 44), (16, 18, 28), -1)
        cv2.rectangle(canvas, (ax, 12), (ax + 225, 44), (245, 190, 56), 2)
        cv2.putText(canvas, "SIGNATURE TENDENCY", (ax + 12, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.56, (255, 225, 115), 2, cv2.LINE_AA)

        canvas[top_h:top_h + 3, :] = (155, 65, 245)
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


# 11 Tight, Visually Distinct, Zero-Dead-Time 1080p Scouting Clips (~77.5s = 1:17)
CLIPS = [
    {
        "idx": 1,
        "player": "#9 Diallo Holmes",
        "chap_title": "Pull-Up Right-Wing 3PT (20.3 PPG, 10x 3PM, 88% FT)",
        "start_s": 621.0,
        "end_s": 628.0,
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
        "end_s": 1634.0,
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
        "start_s": 3025.0,
        "end_s": 3032.0,
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
        "start_s": 655.0,
        "end_s": 662.0,
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
        "start_s": 3325.5,
        "end_s": 3332.5,
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
        "start_s": 1943.0,
        "end_s": 1950.5,
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
        "start_s": 3255.0,
        "end_s": 3262.0,
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
        "chap_title": "2nd-Half Left-Wing Catch-and-Shoot 3PT (7.3 PPG, 2.7 PF/G)",
        "start_s": 2583.5,
        "end_s": 2590.5,
        "proof_s": 2587.0,
        "pip_side": "left",
        "zoom_box": (520, 120, 1320, 608),
        "badge": "CLIP 8/11 | 3-AND-D CONNECTOR: #8 RADHIR (7.3 PPG, 4.3 RPG)",
        "title": "#4 LAZAR SWINGS TO #8 RADHIR FOR 2ND-HALF WING 3PT!",
        "sub": "Active ball-hawk (2.7 fouls/G) - attack him off the dribble to draw early fouls!"
    },
    {
        "idx": 9,
        "player": "#4 Lazar",
        "chap_title": "Midcourt Passing-Lane Steal & Breakaway Layup (83% 2PT)",
        "start_s": 1201.5,
        "end_s": 1207.5,
        "proof_s": 1205.5,
        "pip_side": "right",
        "zoom_box": (240, 120, 1040, 608),
        "badge": "CLIP 9/11 | CUTTER & THIEF: #4 LAZAR (8 PTS, 4/5 2PT IN WK 4)",
        "title": "#4 LAZAR JUMPS MIDCOURT PASS FOR OPEN-FLOOR BREAKAWAY!",
        "sub": "83% 2PT finisher on cuts & steals (0/2 3PT) - crisp passes & track back-cuts!"
    },
    {
        "idx": 10,
        "player": "#2 Troy",
        "chap_title": "Fast-Break Rim Run & Paint Finish (23p/11r vs CU in Mar 1 Champ!)",
        "start_s": 2565.5,
        "end_s": 2571.5,
        "proof_s": 2569.1,
        "pip_side": "left",
        "zoom_box": (940, 130, 1740, 618),
        "badge": "CLIP 10/11 | REVENGE ALERT: #2 TROY (23 PTS, 11 REB VS CU MAR 1!)",
        "title": "#2 TROY SPRINTS THE LANE & SCORES INSIDE (6 REB, 2 STL, 1 BLK)",
        "sub": "Just returned in Wk 4! Non-shooter (0 3PA) - SAG INTO PAINT & BOX HIM OUT!"
    },
    {
        "idx": 11,
        "player": "#10 Ty",
        "chap_title": "Bench Left-Corner 3PT off #9 Diallo Skip Pass (2/2 3PT = 100%)",
        "start_s": 970.5,
        "end_s": 977.0,
        "proof_s": 973.5,
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


def build_scouting_reel_single_stream(cap):
    """
    Encodes ALL 11 clips in a SINGLE continuous libx264 + AAC pass (zero -c copy concat splices!):
    - Sample-exact 48kHz PCM WAV master assembled across all 11 clips
    - -bf 0 so video start_time == 0.000000 exact (no +0.021354s B-frame PTS shift!)
    - -g 30 (keyframe every 1.0s) + explicit -force_key_frames on every chapter start!
    """
    fps = 30.0
    sr_hz = 48000

    # Step 1: Build sample-exact master WAV + chapter list
    master_wav = os.path.join(SCRATCH_DIR, "master_scouting_audio.wav")
    chapters = []
    force_kf_times = []
    cum_frames = 0

    with wave.open(master_wav, "wb") as wout:
        wout.setnchannels(2)
        wout.setsampwidth(2)
        wout.setframerate(sr_hz)

        for c in CLIPS:
            dur = round(c["end_s"] - c["start_s"], 3)
            n_frames = int(round(dur * fps))
            c["_n_frames"] = n_frames
            exact_dur = n_frames / fps
            target_pcm_bytes = int(round(exact_dur * sr_hz)) * 4  # 2ch * 2bytes

            cum_sec = cum_frames / fps
            mm = int(cum_sec) // 60
            ss = int(cum_sec) % 60
            chapters.append({
                "sec": round(cum_sec, 2),
                "time": f"{mm}:{ss:02d}",
                "player": c["player"],
                "title": c["chap_title"]
            })
            force_kf_times.append(f"{cum_sec:.3f}")
            cum_frames += n_frames

            raw_pcm = subprocess.check_output([
                "ffmpeg", "-v", "error",
                "-ss", f"{c['start_s']:.3f}",
                "-t", f"{exact_dur + 0.1:.3f}",
                "-i", VID,
                "-vn", "-ac", "2", "-ar", str(sr_hz),
                "-f", "s16le", "-"
            ])
            if len(raw_pcm) >= target_pcm_bytes:
                raw_pcm = raw_pcm[:target_pcm_bytes]
            else:
                raw_pcm = raw_pcm + b"\x00" * (target_pcm_bytes - len(raw_pcm))
            wout.writeframes(raw_pcm)

    # Step 2: Pipe ALL 11 decorated clips continuously into ONE ffmpeg encode
    out_reel = os.path.join(OUT_DIR, "latto_talent_scouting_tape_1080p.mp4")
    fkf_arg = ",".join(force_kf_times)
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "rawvideo", "-vcodec", "rawvideo",
        "-pix_fmt", "bgr24", "-s", f"{OUT_W}x{OUT_H}", "-r", "30",
        "-i", "-",
        "-i", master_wav,
        "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-bf", "0",
        "-g", "30", "-keyint_min", "15",
        "-force_key_frames", fkf_arg,
        "-profile:v", "high", "-level", "4.1", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2",
        "-shortest", "-movflags", "+faststart",
        out_reel
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    proof_tiles = []
    for c in CLIPS:
        cap.set(cv2.CAP_PROP_POS_MSEC, c["proof_s"] * 1000.0)
        ok_p, pframe = cap.read()
        if ok_p:
            dec_p = decorate_scouting_frame(pframe, c)
            proof_tiles.append(cv2.resize(dec_p, (640, 360), interpolation=cv2.INTER_AREA))

        cap.set(cv2.CAP_PROP_POS_MSEC, c["start_s"] * 1000.0)
        n_frames = c["_n_frames"]
        last_good = None
        for _ in range(n_frames):
            ok, frame = cap.read()
            if not ok:
                frame = last_good if last_good is not None else np.zeros((OUT_H, OUT_W, 3), dtype=np.uint8)
            else:
                last_good = frame
            proc.stdin.write(decorate_scouting_frame(frame, c).tobytes())
        print(f"Streamed Clip {c['idx']:02d}/11 ({n_frames}f = {n_frames/fps:.2f}s) -> {c['player']}: {c['chap_title'][:42]}")

    proc.stdin.close()
    ret = proc.wait()
    if ret != 0:
        raise RuntimeError(f"Single-stream ffmpeg failed with exit code {ret}")

    while len(proof_tiles) % 2 != 0:
        proof_tiles.append(np.zeros((360, 640, 3), dtype=np.uint8))
    rows = [np.hstack([proof_tiles[i], proof_tiles[i + 1]]) for i in range(0, len(proof_tiles), 2)]
    proof_p = os.path.join(ARTIFACT_DIR, "lt_scouting_reel_proof.jpg")
    cv2.imwrite(proof_p, np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 92])

    total_sec = round(cum_frames / fps, 2)
    meta_p = os.path.join(SCRATCH_DIR, "lt_chapters.json")
    with open(meta_p, "w", encoding="utf-8") as f:
        json.dump({"duration_s": total_sec, "chapters": chapters}, f, indent=2)

    pr = subprocess.run([
        "ffprobe", "-v", "error",
        "-show_entries", "stream=codec_type,codec_name,width,height,r_frame_rate,start_time,duration,nb_frames:format=duration,size",
        "-of", "default=noprint_wrappers=1", out_reel
    ], capture_output=True, text=True)
    print("=== SINGLE-STREAM 1080p SCOUTING REEL FFPROBE ===")
    print(pr.stdout)
    print("Chapters:", json.dumps(chapters, indent=2))


if __name__ == "__main__":
    build_logo()
    cap = cv2.VideoCapture(VID)
    build_player_cards(cap)
    build_scouting_reel_single_stream(cap)
    cap.release()
