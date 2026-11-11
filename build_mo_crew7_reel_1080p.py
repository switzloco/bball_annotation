import cv2
import numpy as np
import os
import shutil
import subprocess
import json

W2_VID = r"c:\dev\bball_annotation\majestic_crew7\2026-01-18_C7_vs_Breadwinners_W2.mp4"
W3_VID = r"c:\dev\bball_annotation\majestic_crew7\2026-01-25_C7_vs_BTA_W3.mp4"
W4_VID = r"c:\dev\bball_annotation\majestic_crew7\2026-02-01_C7_vs_OutOfShape_W4.mp4"

REELS_DIR = r"c:\dev\bball_annotation\majestic_games\reels"
os.makedirs(REELS_DIR, exist_ok=True)
OUT_REEL = os.path.join(REELS_DIR, "2026-02-01_C7_Mo_Winter26_Reel.mp4")
ROOT_COPY = r"c:\dev\bball_annotation\majestic_games\2026-02-01_C7_Mo_Winter26_Reel.mp4"

ARTIFACT_DIR = r"C:\Users\Nick\.gemini\antigravity\brain\92e691fb-4334-4d76-9835-87d6d959086f"
SCRATCH_DIR = os.path.join(ARTIFACT_DIR, "scratch", "mo_c7_reel_1080p_segs")
os.makedirs(SCRATCH_DIR, exist_ok=True)

# All 14 clips verified on 1920x1080 H.264 masters via Physical LED Scoreboard Binary Search + Biometric/Jersey QA
CLIPS = [
    {
        "idx": 1,
        "video": W2_VID,
        "start_s": 638.5,
        "end_s": 648.0,
        "proof_s": 642.8,
        "pip_side": "left",
        "zoom_box": (1080, 430, 1840, 885),
        "badge": "CLIP 1/14 | W2 vs BREADWINNERS (H1 15:25 LED)",
        "title": "#2 MO FOREGROUND RIGHT-WING 3-POINTER #1 OF 4!",
        "sub": "Pulls up in red #2 & cyan kicks - holds pure gooseneck follow-through"
    },
    {
        "idx": 2,
        "video": W2_VID,
        "start_s": 1923.0,
        "end_s": 1933.0,
        "proof_s": 1927.6,
        "pip_side": "right",
        "zoom_box": (60, 410, 810, 860),
        "badge": "CLIP 2/14 | W2 vs BREADWINNERS (H2 19:20 LED)",
        "title": "#2 MO DEEP CORNER 3-POINTER #2 OF 4!",
        "sub": "Opens the second half burying baseline corner triple at left hoop"
    },
    {
        "idx": 3,
        "video": W2_VID,
        "start_s": 2328.5,
        "end_s": 2338.5,
        "proof_s": 2333.2,
        "pip_side": "right",
        "zoom_box": (110, 420, 860, 870),
        "badge": "CLIP 3/14 | W2 vs BREADWINNERS (H2 13:52 LED)",
        "title": "#2 MO TOP-OF-THE-ARC 3-POINTER #3 OF 4!",
        "sub": "Rises smoothly from straightaway 3PT range & splashes net"
    },
    {
        "idx": 4,
        "video": W2_VID,
        "start_s": 2619.5,
        "end_s": 2630.0,
        "proof_s": 2624.5,
        "pip_side": "right",
        "zoom_box": (120, 430, 870, 885),
        "badge": "CLIP 4/14 | W2 vs BREADWINNERS (H2 8:53 LED)",
        "title": "FLAMETHROWER! #2 MO LEFT-WING 3-POINTER #4 OF 4! (4/4 3PT!)",
        "sub": "Foreground left-wing catch-and-shoot dagger - 100% from beyond the arc!"
    },
    {
        "idx": 5,
        "video": W2_VID,
        "start_s": 3290.0,
        "end_s": 3299.5,
        "proof_s": 3295.8,
        "pip_side": "right",
        "zoom_box": (80, 420, 830, 870),
        "badge": "CLIP 5/14 | W2 vs BREADWINNERS (H2 0:22 LED)",
        "title": "#2 MO SKYING PAINT FLOATER OVER 3 DEFENDERS (14 PTS, 3 STL, BLK)",
        "sub": "Elevates above three defenders in the lane to cap a 5-for-5 shooting night"
    },
    {
        "idx": 6,
        "video": W3_VID,
        "start_s": 827.0,
        "end_s": 836.5,
        "proof_s": 832.5,
        "pip_side": "right",
        "zoom_box": (80, 420, 830, 870),
        "badge": "CLIP 6/14 | W3 vs BTA UNIVERSITY (H1 11:40 LED)",
        "title": "#2 MO EXPLOSIVE MIDDLE-LANE SLASH & FINISH IN TRAFFIC",
        "sub": "Splits BTA defense down the heart of the paint & scores high at the cup"
    },
    {
        "idx": 7,
        "video": W3_VID,
        "start_s": 1554.5,
        "end_s": 1564.5,
        "proof_s": 1558.8,
        "pip_side": "right",
        "zoom_box": (110, 420, 860, 870),
        "badge": "CLIP 7/14 | W3 vs BTA UNIVERSITY (H1 0:26 LED)",
        "title": "END-OF-HALF DAGGER! #2 MO TRANSITION PULL-UP 3-POINTER!",
        "sub": "Walks into a deep right-slot pull-up triple in final 26s of first half"
    },
    {
        "idx": 8,
        "video": W3_VID,
        "start_s": 1958.5,
        "end_s": 1967.5,
        "proof_s": 1963.7,
        "pip_side": "left",
        "zoom_box": (1100, 420, 1850, 870),
        "badge": "CLIP 8/14 | W3 vs BTA UNIVERSITY (H2 16:33 LED)",
        "title": "#2 MO DOUBLE-DOUBLE! FAST-BREAK RIM ATTACK (13 PTS, 11 REB, 5 AST)",
        "sub": "All-around monster night: 13 points, 11 rebounds, 5 dimes, 1 steal & 1 block"
    },
    {
        "idx": 9,
        "video": W4_VID,
        "start_s": 958.5,
        "end_s": 967.5,
        "proof_s": 963.0,
        "pip_side": "right",
        "zoom_box": (90, 340, 850, 790),
        "badge": "CLIP 9/14 | W4 vs OUT OF SHAPE (H1 13:18 LED)",
        "title": "25-POINT EXPLOSION BEGINS! #2 MO TRANSITION LEFT-RIM FINISH",
        "sub": "Outruns the pack in full red #2 Crew 7 kit & lays it high off glass"
    },
    {
        "idx": 10,
        "video": W4_VID,
        "start_s": 1861.5,
        "end_s": 1871.0,
        "proof_s": 1866.4,
        "pip_side": "right",
        "zoom_box": (90, 340, 850, 790),
        "badge": "CLIP 10/14 | W4 vs OUT OF SHAPE (H1 0:08 LED)",
        "title": "HALFTIME BUZZER RUN! #2 MO SOLO OPEN-FLOOR BREAKAWAY",
        "sub": "Attacks full speed down left lane & finishes smoothly before the horn"
    },
    {
        "idx": 11,
        "video": W4_VID,
        "start_s": 2408.5,
        "end_s": 2417.5,
        "proof_s": 2412.0,
        "pip_side": "left",
        "zoom_box": (1040, 320, 1820, 770),
        "badge": "CLIP 11/14 | W4 vs OUT OF SHAPE (H2 14:10 LED)",
        "title": "PLAYMAKER MO! #2 MO BASELINE BLOW-BY & KICKOUT 3PT DIME (AST)",
        "sub": "Beats defender along right baseline, collapses paint & whips pass for 3PT"
    },
    {
        "idx": 12,
        "video": W4_VID,
        "start_s": 2790.5,
        "end_s": 2799.5,
        "proof_s": 2795.8,
        "pip_side": "left",
        "zoom_box": (1040, 320, 1820, 770),
        "badge": "CLIP 12/14 | W4 vs OUT OF SHAPE (H2 7:48 LED)",
        "title": "#2 MO EURO-STEP SLASH & CONTESTED RIGHT-RIM BUCKET",
        "sub": "Knifes through traffic & finishes softly off the backboard"
    },
    {
        "idx": 13,
        "video": W4_VID,
        "start_s": 3100.5,
        "end_s": 3109.5,
        "proof_s": 3103.5,
        "pip_side": "left",
        "zoom_box": (1040, 320, 1820, 770),
        "badge": "CLIP 13/14 | W4 vs OUT OF SHAPE (H2 2:28 LED)",
        "title": "UNSTOPPABLE! #2 MO RIGHT-SIDELINE RIP-THROUGH TO THE RIM!",
        "sub": "Explodes past perimeter defender in foreground & takes it all the way"
    },
    {
        "idx": 14,
        "video": W4_VID,
        "start_s": 3158.0,
        "end_s": 3166.5,
        "proof_s": 3161.2,
        "pip_side": "left",
        "zoom_box": (1040, 320, 1820, 770),
        "badge": "CLIP 14/14 | W4 vs OUT OF SHAPE (H2 1:35 LED)",
        "title": "SEASON-HIGH 25 PTS! #2 MO SOLO BREAKAWAY FINALE (58 PTS WINTER '26)",
        "sub": "11 Made FGs + 9 REB in W4 | Winter '26 Totals: 58 PTS, 10x 3PM, 30 REB, 10 AST!"
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
    # Crew 7 Crimson + Gold accent border
    cv2.rectangle(out, (px, py), (px + PIP_W, py + PIP_H), (35, 195, 255), 3)

    cv2.rectangle(out, (px, py), (px + 255, py + 32), (14, 16, 26), -1)
    cv2.rectangle(out, (px, py), (px + 6, py + 32), (35, 195, 255), -1)
    cv2.putText(out, "ISO CAM 2.0x | C7 #2 MO", (px + 14, py + 22),
                cv2.FONT_HERSHEY_SIMPLEX, 0.54, (85, 225, 255), 2, cv2.LINE_AA)

    overlay = out.copy()
    bx1, by1, bx2, by2 = 48, OUT_H - 146, OUT_W - 48, OUT_H - 28
    cv2.rectangle(overlay, (bx1, by1), (bx2, by2), (14, 17, 27), -1)
    cv2.rectangle(overlay, (bx1, by1), (bx1 + 10, by2), (35, 195, 255), -1)
    out = cv2.addWeighted(overlay, 0.86, out, 0.14, 0)

    cv2.putText(out, f"CREW 7 (#2 MOHAMED - WINTER '26)  |  {c['badge']}", (bx1 + 28, by1 + 34),
                cv2.FONT_HERSHEY_SIMPLEX, 0.74, (85, 225, 255), 2, cv2.LINE_AA)
    cv2.putText(out, c["title"], (bx1 + 28, by1 + 74),
                cv2.FONT_HERSHEY_SIMPLEX, 0.90, (255, 255, 255), 2, cv2.LINE_AA)
    cv2.putText(out, c["sub"], (bx1 + 28, by1 + 105),
                cv2.FONT_HERSHEY_SIMPLEX, 0.66, (205, 214, 228), 1, cv2.LINE_AA)

    cv2.rectangle(out, (bx2 - 175, by1 + 16), (bx2 - 22, by1 + 52), (28, 42, 215), -1)
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

    seg_path = os.path.join(SCRATCH_DIR, f"c7_seg_1080p_{c['idx']:02d}.mp4")
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

concat_list = os.path.join(SCRATCH_DIR, "concat_c7_1080p.txt")
with open(concat_list, "w", encoding="utf-8") as f:
    for sf in segment_files:
        f.write(f"file '{sf.replace(os.sep, '/')}'\n")

subprocess.run([
    "ffmpeg", "-y",
    "-loglevel", "error",
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
print(f"\nFINAL CREW 7 REEL: {vst['codec_name']} ({vst.get('profile')}) {vst['width']}x{vst['height']} @ {vst['r_frame_rate']} | "
      f"v_bitrate={int(vst.get('bit_rate',0))//1000} kbps | dur={float(vfmt['duration']):.2f}s | size={int(vfmt['size'])/1e6:.2f} MB")

cols = 3
while len(proof_tiles) % cols != 0:
    proof_tiles.append(np.zeros((360, 640, 3), dtype=np.uint8))
rows = [np.hstack(proof_tiles[i:i + cols]) for i in range(0, len(proof_tiles), cols)]
proof_img = np.vstack(rows)
proof_path = os.path.join(ARTIFACT_DIR, "c7_mo_winter26_reel_proof.jpg")
cv2.imwrite(proof_path, proof_img, [int(cv2.IMWRITE_JPEG_QUALITY), 92])
print("Saved 14-clip 1080p proof sheet:", proof_path)
