import cv2
import numpy as np
import os
import shutil
import subprocess
import json

_G2_1080 = r"c:\dev\bball_annotation\majestic_wtn\2026-10-25_WTN_vs_NewAvengers_G2_1080p.mp4"
_G3_1080 = r"c:\dev\bball_annotation\majestic_wtn\2026-11-01_WTN_vs_CrunchTime_G3_1080p.mp4"
G2_VID = _G2_1080 if os.path.exists(_G2_1080) else r"c:\dev\bball_annotation\majestic_wtn\2026-10-25_WTN_vs_NewAvengers_G2.mp4"
G3_VID = _G3_1080 if os.path.exists(_G3_1080) else r"c:\dev\bball_annotation\majestic_wtn\2026-11-01_WTN_vs_CrunchTime_G3.mp4"
G4_VID = r"c:\dev\bball_annotation\majestic_wtn\2026-11-08_WTN_vs_DomainExpansion_G4.mp4"

REELS_DIR = r"c:\dev\bball_annotation\majestic_games\reels"
os.makedirs(REELS_DIR, exist_ok=True)
OUT_REEL = os.path.join(REELS_DIR, "2026-11-01_WTN_Mo_Highlight_Reel.mp4")
ROOT_COPY = r"c:\dev\bball_annotation\majestic_games\2026-11-01_WTN_Mo_Highlight_Reel.mp4"

ARTIFACT_DIR = r"C:\Users\Nick\.gemini\antigravity\brain\92e691fb-4334-4d76-9835-87d6d959086f"
SCRATCH_DIR = os.path.join(ARTIFACT_DIR, "scratch", "mo_reel_1080p_v3_segs")
os.makedirs(SCRATCH_DIR, exist_ok=True)

# All 14 clips verified frame-by-frame across Games 2, 3, and Week 4 Victory (55-53) on 1920x1080 H.264 masters
CLIPS = [
    {
        "idx": 1,
        "video": G2_VID,
        "start_s": 1179.0,
        "end_s": 1188.0,
        "proof_s": 1184.8,
        "pip_side": "right",
        "zoom_box": (140, 260, 890, 720),
        "badge": "CLIP 1/14 | GAME 2 vs NEW AVENGERS (H1 12:11 LED)",
        "title": "#2 MO SLASHING LEFT-LANE RUNNER IN TRAFFIC (1/1 FG)",
        "sub": "Attacks down the left slot in red #2 & finishes off glass"
    },
    {
        "idx": 2,
        "video": G2_VID,
        "start_s": 1200.0,
        "end_s": 1212.0,
        "proof_s": 1207.8,
        "pip_side": "right",
        "zoom_box": (170, 250, 920, 710),
        "badge": "CLIP 2/14 | GAME 2 vs NEW AVENGERS (H1 11:50 LED)",
        "title": "#2 MO DREB + COAST-TO-COAST 3-POINTER! (5 PTS IN 21s)",
        "sub": "Cleans defensive glass & drills pull-up left-wing triple"
    },
    {
        "idx": 3,
        "video": G2_VID,
        "start_s": 1575.0,
        "end_s": 1585.0,
        "proof_s": 1581.5,
        "pip_side": "right",
        "zoom_box": (150, 260, 900, 720),
        "badge": "CLIP 3/14 | GAME 2 vs NEW AVENGERS (H1 6:44 LED)",
        "title": "#2 MO TRANSITION DRIVE & FINISH (7 PTS, 3/3 FG - 100% FG!)",
        "sub": "Perfect 3-for-3 shooting night with 7 rebounds"
    },
    {
        "idx": 4,
        "video": G2_VID,
        "start_s": 1615.0,
        "end_s": 1624.0,
        "proof_s": 1619.5,
        "pip_side": "left",
        "zoom_box": (1020, 300, 1770, 760),
        "badge": "CLIP 4/14 | GAME 2 vs NEW AVENGERS (H1 6:07 LED)",
        "title": "#2 MO DEFENSIVE STEAL & FAST BREAK IGNITION (STL)",
        "sub": "Active hands at top of the key to strip ball & ignite break"
    },
    {
        "idx": 5,
        "video": G2_VID,
        "start_s": 3268.0,
        "end_s": 3278.0,
        "proof_s": 3275.0,
        "pip_side": "left",
        "zoom_box": (1060, 290, 1810, 750),
        "badge": "CLIP 5/14 | GAME 2 vs NEW AVENGERS (H2 6:07 LED)",
        "title": "#2 MO 7TH REBOUND & COAST-TO-COAST PAINT DISH",
        "sub": "Pushes tempo down the middle & feeds teammate at right rim"
    },
    {
        "idx": 6,
        "video": G3_VID,
        "start_s": 1011.0,
        "end_s": 1020.0,
        "proof_s": 1016.0,
        "pip_side": "left",
        "zoom_box": (1150, 420, 1870, 860),
        "badge": "CLIP 6/14 | GAME 3 vs CRUNCH TIME (H1 15:00 LED)",
        "title": "#2 MO INTERIOR RIM PROTECTION - SWATS LAYUP ATTEMPT (BLK)",
        "sub": "Closes down the paint in white #2 to reject Crunch Time shot"
    },
    {
        "idx": 7,
        "video": G3_VID,
        "start_s": 2720.0,
        "end_s": 2730.0,
        "proof_s": 2725.2,
        "pip_side": "left",
        "zoom_box": (1140, 430, 1860, 870),
        "badge": "CLIP 7/14 | GAME 3 vs CRUNCH TIME (H2 12:54 LED)",
        "title": "#2 MO 3-POINTER #1 OF 5! (RIGHT-WING CATCH & SHOOT)",
        "sub": "Assisted by #33 Hamza | Pure high-arc splash at right hoop"
    },
    {
        "idx": 8,
        "video": G3_VID,
        "start_s": 3090.0,
        "end_s": 3102.0,
        "proof_s": 3097.5,
        "pip_side": "left",
        "zoom_box": (1140, 430, 1860, 870),
        "badge": "CLIP 8/14 | GAME 3 vs CRUNCH TIME (H2 6:54 -> 6:45 LED)",
        "title": "#2 MO DREB + COAST-TO-COAST 3-POINTER #2 OF 5!",
        "sub": "Pushes off defensive stop & buries right-wing transition 3"
    },
    {
        "idx": 9,
        "video": G3_VID,
        "start_s": 3120.0,
        "end_s": 3130.0,
        "proof_s": 3125.5,
        "pip_side": "left",
        "zoom_box": (1080, 410, 1830, 870),
        "badge": "CLIP 9/14 | GAME 3 vs CRUNCH TIME (H2 6:18 LED)",
        "title": "BACK-TO-BACK! #2 MO 3-POINTER #3 OF 5! (2 TRIPLES IN 27s)",
        "sub": "Assisted by #29 Deeno | Deep top-of-arc rainbow splash"
    },
    {
        "idx": 10,
        "video": G3_VID,
        "start_s": 3145.0,
        "end_s": 3156.0,
        "proof_s": 3151.2,
        "pip_side": "left",
        "zoom_box": (1080, 420, 1840, 885),
        "badge": "CLIP 10/14 | GAME 3 vs CRUNCH TIME (H2 5:53 LED)",
        "title": "HEAT CHECK! #2 MO PULL-UP 3-POINTER #4 OF 5! (3 IN 52s!)",
        "sub": "Crosses up on the dribble, drills pull-up 3 & high-fives!"
    },
    {
        "idx": 11,
        "video": G3_VID,
        "start_s": 3668.0,
        "end_s": 3679.0,
        "proof_s": 3672.2,
        "pip_side": "left",
        "zoom_box": (1140, 420, 1880, 875),
        "badge": "CLIP 11/14 | GAME 3 vs CRUNCH TIME (FINAL 0:09 LED)",
        "title": "CINCO DE MO! #2 MO DAGGER 3-POINTER #5 OF 5! (15 PTS, 5x 3PM)",
        "sub": "Assisted by #16 Naz | Drains contested wing 3 at the buzzer!"
    },
    {
        "idx": 12,
        "video": G4_VID,
        "start_s": 1577.0,
        "end_s": 1586.0,
        "proof_s": 1582.0,
        "pip_side": "left",
        "zoom_box": (1140, 430, 1890, 890),
        "badge": "CLIP 12/14 | GAME 4 WIN vs DOMAIN EXPANSION (13-0 RUN!)",
        "title": "#2 MO SLASHING PAINT RUNNER CAPS 13-0 OPENING BLITZ!",
        "sub": "Drives right slot in Red #2 & finishes in traffic (WTN 55, DOM 53)"
    },
    {
        "idx": 13,
        "video": G4_VID,
        "start_s": 2417.5,
        "end_s": 2426.5,
        "proof_s": 2423.0,
        "pip_side": "left",
        "zoom_box": (1080, 420, 1850, 880),
        "badge": "CLIP 13/14 | GAME 4 WIN vs DOMAIN EXPANSION (H1 2:11)",
        "title": "#2 MO PERIMETER DIME -> #33 HAMZA DEEP 3-POINTER! (28-17)",
        "sub": "Unselfish ball movement sets up Hamza's 3rd first-half triple"
    },
    {
        "idx": 14,
        "video": G4_VID,
        "start_s": 3209.5,
        "end_s": 3222.0,
        "proof_s": 3214.0,
        "pip_side": "left",
        "zoom_box": (1140, 430, 1890, 890),
        "badge": "CLIP 14/14 | GAME 4 WIN vs DOMAIN EXPANSION (55-53 VICTORY!)",
        "title": "#2 MO SHOT BLOCK + DEFENSIVE REBOUND TO PROTECT THE LEAD!",
        "sub": "Swats layup in the right paint & cleans glass in WTN's 55-53 W!"
    },
]

OUT_W, OUT_H = 1920, 1080
PIP_W, PIP_H = 520, 318


def decorate_1080p_frame(frame, c):
    if frame.shape[1] != OUT_W or frame.shape[0] != OUT_H:
        frame = cv2.resize(frame, (OUT_W, OUT_H), interpolation=cv2.INTER_LANCZOS4)
    out = frame.copy()

    zx1, zy1, zx2, zy2 = c["zoom_box"]
    crop = frame[zy1:zy2, zx1:zx2]
    pip = cv2.resize(crop, (PIP_W, PIP_H), interpolation=cv2.INTER_LANCZOS4)

    px = 38 if c["pip_side"] == "left" else (OUT_W - PIP_W - 38)
    py = 34

    cv2.rectangle(out, (px + 6, py + 6), (px + PIP_W + 6, py + PIP_H + 6), (8, 10, 16), -1)
    out[py:py + PIP_H, px:px + PIP_W] = pip
    cv2.rectangle(out, (px, py), (px + PIP_W, py + PIP_H), (40, 48, 230), 3)

    cv2.rectangle(out, (px, py), (px + 235, py + 32), (16, 18, 28), -1)
    cv2.rectangle(out, (px, py), (px + 6, py + 32), (40, 48, 230), -1)
    cv2.putText(out, "ISO CAM 2.0x | #2 MO", (px + 14, py + 22),
                cv2.FONT_HERSHEY_SIMPLEX, 0.56, (100, 225, 255), 2, cv2.LINE_AA)

    overlay = out.copy()
    bx1, by1, bx2, by2 = 48, OUT_H - 146, OUT_W - 48, OUT_H - 28
    cv2.rectangle(overlay, (bx1, by1), (bx2, by2), (14, 17, 27), -1)
    cv2.rectangle(overlay, (bx1, by1), (bx1 + 10, by2), (38, 44, 228), -1)
    out = cv2.addWeighted(overlay, 0.86, out, 0.14, 0)

    cv2.putText(out, f"WE THE NORTH (#2 MO)  |  {c['badge']}", (bx1 + 28, by1 + 34),
                cv2.FONT_HERSHEY_SIMPLEX, 0.76, (95, 220, 255), 2, cv2.LINE_AA)
    cv2.putText(out, c["title"], (bx1 + 28, by1 + 74),
                cv2.FONT_HERSHEY_SIMPLEX, 0.94, (255, 255, 255), 2, cv2.LINE_AA)
    cv2.putText(out, c["sub"], (bx1 + 28, by1 + 105),
                cv2.FONT_HERSHEY_SIMPLEX, 0.68, (205, 214, 228), 1, cv2.LINE_AA)

    cv2.rectangle(out, (bx2 - 175, by1 + 16), (bx2 - 22, by1 + 52), (38, 44, 228), -1)
    cv2.putText(out, "1080p FULL HD", (bx2 - 163, by1 + 41),
                cv2.FONT_HERSHEY_SIMPLEX, 0.58, (255, 255, 255), 2, cv2.LINE_AA)
    return out


segment_files = []
proof_tiles = []

for c in CLIPS:
    cap = cv2.VideoCapture(c["video"])
    fps = cap.get(cv2.CAP_PROP_FPS) or (30000.0 / 1001.0)
    dur = c["end_s"] - c["start_s"]
    n_frames = int(round(dur * fps))

    cap.set(cv2.CAP_PROP_POS_MSEC, c["proof_s"] * 1000.0)
    ok_p, pframe = cap.read()
    if ok_p:
        dec_p = decorate_1080p_frame(pframe, c)
        tile = cv2.resize(dec_p, (640, 360), interpolation=cv2.INTER_AREA)
        proof_tiles.append(tile)

    seg_path = os.path.join(SCRATCH_DIR, f"seg_1080p_{c['idx']:02d}.mp4")
    cmd = [
        "ffmpeg", "-y",
        "-loglevel", "error",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-pix_fmt", "bgr24",
        "-s", f"{OUT_W}x{OUT_H}",
        "-r", "30000/1001",
        "-i", "-",
        "-ss", f"{c['start_s']:.3f}",
        "-t", f"{dur:.3f}",
        "-i", c["video"],
        "-map", "0:v:0",
        "-map", "1:a:0?",
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "17",
        "-profile:v", "high",
        "-level", "4.1",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "160k",
        "-ar", "48000",
        "-ac", "2",
        "-shortest",
        seg_path
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    cap.set(cv2.CAP_PROP_POS_MSEC, c["start_s"] * 1000.0)
    written = 0
    for _ in range(n_frames):
        ok, frame = cap.read()
        if not ok:
            break
        dec = decorate_1080p_frame(frame, c)
        proc.stdin.write(dec.tobytes())
        written += 1

    proc.stdin.close()
    ret = proc.wait()
    cap.release()
    if ret != 0:
        raise RuntimeError(f"ffmpeg failed on clip {c['idx']} with exit code {ret}")

    pr = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=width,height,bit_rate", "-of", "json", seg_path],
        capture_output=True, text=True, check=True
    )
    st = json.loads(pr.stdout)["streams"][0]
    print(f"Encoded Clip #{c['idx']:02d} ({written} frames): {st['width']}x{st['height']} @ {int(st.get('bit_rate', 0)) // 1000} kbps")
    segment_files.append(seg_path)

concat_list = os.path.join(SCRATCH_DIR, "concat_1080p.txt")
with open(concat_list, "w", encoding="utf-8") as f:
    for sf in segment_files:
        f.write(f"file '{sf.replace(os.sep, '/')}'\n")

subprocess.run([
    "ffmpeg", "-y",
    "-f", "concat",
    "-safe", "0",
    "-i", concat_list,
    "-c", "copy",
    "-movflags", "+faststart",
    OUT_REEL
], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

shutil.copyfile(OUT_REEL, ROOT_COPY)

pr_final = subprocess.run(
    ["ffprobe", "-v", "error", "-select_streams", "v:0",
     "-show_entries", "stream=codec_name,profile,width,height,bit_rate,r_frame_rate:format=duration,size",
     "-of", "json", OUT_REEL],
    capture_output=True, text=True, check=True
)
fi = json.loads(pr_final.stdout)
vst = fi["streams"][0]
vfmt = fi["format"]
print(f"\nFINAL REEL: {vst['codec_name']} ({vst.get('profile')}) {vst['width']}x{vst['height']} @ {vst['r_frame_rate']} | "
      f"v_bitrate={int(vst.get('bit_rate',0))//1000} kbps | dur={float(vfmt['duration']):.2f}s | size={int(vfmt['size'])/1e6:.2f} MB")

cols = 3
while len(proof_tiles) % cols != 0:
    proof_tiles.append(np.zeros((360, 640, 3), dtype=np.uint8))
rows = [np.hstack(proof_tiles[i:i + cols]) for i in range(0, len(proof_tiles), cols)]
proof_img = np.vstack(rows)
proof_path = os.path.join(ARTIFACT_DIR, "wtn_mo_g4_reel_proof.jpg")
cv2.imwrite(proof_path, proof_img, [int(cv2.IMWRITE_JPEG_QUALITY), 92])
print("Saved 14-clip proof sheet:", proof_path)
