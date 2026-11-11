import cv2
import numpy as np
import os
import shutil
import subprocess

G4_VID = r"c:\dev\bball_annotation\majestic_oct2026\2026-11-08_CU_vs_Ricecookers_G4.mp4"

REELS_DIR = r"c:\dev\bball_annotation\majestic_games\reels"
os.makedirs(REELS_DIR, exist_ok=True)
OUT_REEL = os.path.join(REELS_DIR, "2026-11-08_CU_vs_Ricecookers_G4_OT_Win_Reel.mp4")
ROOT_COPY = r"c:\dev\bball_annotation\majestic_games\2026-11-08_CU_vs_Ricecookers_G4_OT_Win_Reel.mp4"

ARTIFACT_DIR = r"C:\Users\Nick\.gemini\antigravity\brain\92e691fb-4334-4d76-9835-87d6d959086f"
SCRATCH_DIR = os.path.join(ARTIFACT_DIR, "scratch", "cu_ric_g4_reel_segs")
os.makedirs(SCRATCH_DIR, exist_ok=True)

# 14 Frame-Verified 1080p Clips telling Campbell United's 66-63 OT Comeback Win (4-0 D2)
CLIPS = [
    {
        "idx": 1,
        "video": G4_VID,
        "start_s": 294.0,
        "end_s": 303.5,
        "proof_s": 299.0,
        "pip_side": "right",
        "zoom_box": (140, 120, 940, 608),
        "badge": "CLIP 1/14 | H1 19:42 (3-0 CU)",
        "title": "#4 ADAM FECTEAU SPLASHES THE OPENING 3-POINTER! (AST: #20 SHANE)",
        "sub": "Campbell United strikes first off the opening tip from the left wing"
    },
    {
        "idx": 2,
        "video": G4_VID,
        "start_s": 626.5,
        "end_s": 634.5,
        "proof_s": 631.0,
        "pip_side": "left",
        "zoom_box": (960, 130, 1760, 618),
        "badge": "CLIP 2/14 | H1 14:14 (12-8 CU)",
        "title": "NO EASY BUCKETS! #20 SHANE HOFFMAN RIM-PROTECTING BLOCK!",
        "sub": "Rotates in the paint and elevates high to erase the Ricecookers layup"
    },
    {
        "idx": 3,
        "video": G4_VID,
        "start_s": 1396.5,
        "end_s": 1405.5,
        "proof_s": 1401.0,
        "pip_side": "right",
        "zoom_box": (220, 130, 1020, 618),
        "badge": "CLIP 3/14 | H1 2:41 (26-22 CU)",
        "title": "#22 MATT MOCHERMAN DRAINS DEEP 3-POINTER! (AST: #44 CHRISTIAN)",
        "sub": "Steps into a high-arcing triple off Christian Raslowsky's kickout"
    },
    {
        "idx": 4,
        "video": G4_VID,
        "start_s": 2516.0,
        "end_s": 2525.5,
        "proof_s": 2520.5,
        "pip_side": "left",
        "zoom_box": (660, 120, 1460, 608),
        "badge": "CLIP 4/14 | H2 9:44 (38-44)",
        "title": "#12 COREY RANDOLPH CATCH-AND-SHOOT 3-POINTER! (AST: #4 ADAM)",
        "sub": "Rises smoothly over the contest off Adam Fecteau's perimeter dime"
    },
    {
        "idx": 5,
        "video": G4_VID,
        "start_s": 2703.0,
        "end_s": 2713.5,
        "proof_s": 2710.5,
        "pip_side": "left",
        "zoom_box": (920, 130, 1720, 618),
        "badge": "CLIP 5/14 | H2 6:17 (42-46)",
        "title": "#44 CHRISTIAN RASLOWSKY STEAL & COAST-TO-COAST FINISH!",
        "sub": "Picks off the pass and attacks the right lane (23 PTS, 14 REB double-double)"
    },
    {
        "idx": 6,
        "video": G4_VID,
        "start_s": 2833.5,
        "end_s": 2842.0,
        "proof_s": 2837.2,
        "pip_side": "left",
        "zoom_box": (580, 130, 1380, 618),
        "badge": "CLIP 6/14 | H2 5:46 (45-49)",
        "title": "ANSWERED IMMEDIATELY! #4 ADAM FECTEAU PULL-UP 3-POINTER!",
        "sub": "10 PTS, 4 AST & 2 STL - drills big second-half triple to keep CU within 4"
    },
    {
        "idx": 7,
        "video": G4_VID,
        "start_s": 3119.5,
        "end_s": 3128.0,
        "proof_s": 3123.8,
        "pip_side": "left",
        "zoom_box": (920, 130, 1720, 618),
        "badge": "CLIP 7/14 | H2 1:00 (48-51)",
        "title": "CRUNCH-TIME DIME! #4 ADAM DISHES TO #24 GEORGE AT THE RIM!",
        "sub": "Adam collapses the defense and finds George inside with 1:00 left"
    },
    {
        "idx": 8,
        "video": G4_VID,
        "start_s": 3632.5,
        "end_s": 3641.0,
        "proof_s": 3635.8,
        "pip_side": "left",
        "zoom_box": (920, 130, 1720, 618),
        "badge": "CLIP 8/14 | LATE H2 (53-54)",
        "title": "ONE-POINT GAME! #44 CHRISTIAN RASLOWSKY POWERS IT HOME!",
        "sub": "Relentless paint attack cuts the Ricecookers lead to 53-54 in crunch time"
    },
    {
        "idx": 9,
        "video": G4_VID,
        "start_s": 3749.5,
        "end_s": 3758.5,
        "proof_s": 3753.2,
        "pip_side": "left",
        "zoom_box": (860, 130, 1660, 618),
        "badge": "CLIP 9/14 | LATE H2 (55-56)",
        "title": "CLUTCH CONNECTION! #4 ADAM FEEDS #9 AARON IN THE PAINT!",
        "sub": "Aaron finishes strong inside (8 PTS) to pull Campbell United within 1 again"
    },
    {
        "idx": 10,
        "video": G4_VID,
        "start_s": 3887.5,
        "end_s": 3897.5,
        "proof_s": 3891.5,
        "pip_side": "left",
        "zoom_box": (520, 130, 1480, 715),
        "badge": "CLIP 10/14 | FINAL SECONDS H2 (58-60)",
        "title": "CLUTCH TRIPLE #1! #44 CHRISTIAN BURIES DEEP 3PT OVER #11!",
        "sub": "Down 5 in the final seconds, Christian splashes contested 3 to make it 58-60!"
    },
    {
        "idx": 11,
        "video": G4_VID,
        "start_s": 4049.0,
        "end_s": 4064.0,
        "proof_s": 4054.5,
        "pip_side": "left",
        "zoom_box": (540, 140, 1500, 725),
        "badge": "CLIP 11/14 | H2 0:00 BUZZER! (61-61 TIE!!)",
        "title": "MIRACLE AT THE HORN!! #44 CHRISTIAN TIES IT 61-61 TO FORCE OT!!",
        "sub": "Coast-to-coast buzzer-beating 3-pointer at 0:00 - Campbell United mobs midcourt!"
    },
    {
        "idx": 12,
        "video": G4_VID,
        "start_s": 4193.5,
        "end_s": 4203.5,
        "proof_s": 4197.0,
        "pip_side": "right",
        "zoom_box": (520, 120, 1320, 608),
        "badge": "CLIP 12/14 | OVERTIME 0:48 (61-61)",
        "title": "OVERTIME REJECTION! #16 CHRIS SWATS AWAY THE GO-AHEAD LAYUP!",
        "sub": "Huge defensive stop at the rim keeps it deadlocked 61-61 in Overtime"
    },
    {
        "idx": 13,
        "video": G4_VID,
        "start_s": 4243.5,
        "end_s": 4252.5,
        "proof_s": 4247.8,
        "pip_side": "left",
        "zoom_box": (980, 130, 1780, 618),
        "badge": "CLIP 13/14 | OVERTIME (63-61 CU LEAD!)",
        "title": "TWO-WAY HEROICS! #16 CHRIS SCORES FOR THE 63-61 OT LEAD!",
        "sub": "Follows his OT block with a strong baseline drive & finish off glass"
    },
    {
        "idx": 14,
        "video": G4_VID,
        "start_s": 4368.0,
        "end_s": 4385.0,
        "proof_s": 4372.5,
        "pip_side": "left",
        "zoom_box": (720, 100, 1680, 685),
        "badge": "CLIP 14/14 | OT FINALE! (66-63 FINAL - 4-0 D2!)",
        "title": "GAME-WINNER!! #20 SHANE HOFFMAN OT DAGGER 3PT! (AST: #44 CHRISTIAN)",
        "sub": "Tied 63-63, Shane drains the winning 3PT + CU seals final stop at horn for 4-0!"
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
    # Campbell United Championship Gold + Crimson accent border
    cv2.rectangle(out, (px, py), (px + PIP_W, py + PIP_H), (45, 210, 255), 3)

    cv2.rectangle(out, (px, py), (px + 290, py + 32), (14, 16, 26), -1)
    cv2.rectangle(out, (px, py), (px + 6, py + 32), (35, 55, 230), -1)
    cv2.putText(out, "ISO CAM 2.0x | CU 66-63 OT", (px + 14, py + 22),
                cv2.FONT_HERSHEY_SIMPLEX, 0.52, (95, 230, 255), 2, cv2.LINE_AA)

    overlay = out.copy()
    bx1, by1, bx2, by2 = 48, OUT_H - 146, OUT_W - 48, OUT_H - 28
    cv2.rectangle(overlay, (bx1, by1), (bx2, by2), (14, 17, 27), -1)
    cv2.rectangle(overlay, (bx1, by1), (bx1 + 10, by2), (45, 210, 255), -1)
    out = cv2.addWeighted(overlay, 0.86, out, 0.14, 0)

    cv2.putText(out, f"CAMPBELL UNITED 66, RICECOOKERS 63 (OT - 4-0 D2)  |  {c['badge']}", (bx1 + 28, by1 + 34),
                cv2.FONT_HERSHEY_SIMPLEX, 0.72, (95, 230, 255), 2, cv2.LINE_AA)
    cv2.putText(out, c["title"], (bx1 + 28, by1 + 74),
                cv2.FONT_HERSHEY_SIMPLEX, 0.88, (255, 255, 255), 2, cv2.LINE_AA)
    cv2.putText(out, c["sub"], (bx1 + 28, by1 + 105),
                cv2.FONT_HERSHEY_SIMPLEX, 0.65, (205, 214, 228), 1, cv2.LINE_AA)

    cv2.rectangle(out, (bx2 - 175, by1 + 16), (bx2 - 22, by1 + 52), (28, 42, 215), -1)
    cv2.putText(out, "1080p FULL HD", (bx2 - 163, by1 + 41),
                cv2.FONT_HERSHEY_SIMPLEX, 0.58, (255, 255, 255), 2, cv2.LINE_AA)
    return out


segment_files = []
proof_tiles = []

cap = cv2.VideoCapture(G4_VID)
fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
fps_str = "30" if abs(fps - 30.0) < 0.02 else "30000/1001"

for c in CLIPS:
    dur = c["end_s"] - c["start_s"]
    n_frames = int(round(dur * fps))

    cap.set(cv2.CAP_PROP_POS_MSEC, c["proof_s"] * 1000.0)
    ok_p, pframe = cap.read()
    if ok_p:
        dec_p = decorate_1080p_frame(pframe, c)
        tile = cv2.resize(dec_p, (640, 360), interpolation=cv2.INTER_AREA)
        proof_tiles.append(tile)

    seg_path = os.path.join(SCRATCH_DIR, f"cu_ric_seg_1080p_{c['idx']:02d}.mp4")
    cmd = [
        "ffmpeg", "-y",
        "-loglevel", "error",
        "-f", "rawvideo",
        "-vcodec", "rawvideo",
        "-pix_fmt", "bgr24",
        "-s", f"{OUT_W}x{OUT_H}",
        "-r", fps_str,
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
    if ret != 0:
        raise RuntimeError(f"ffmpeg failed on clip {c['idx']} with exit code {ret}")

    pr = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=bit_rate,width,height", "-of", "default=noprint_wrappers=1", seg_path],
        capture_output=True, text=True
    )
    info = " | ".join(pr.stdout.strip().splitlines())
    print(f"Encoded Clip {c['idx']:02d}/14 ({written} frames, {dur:.1f}s) -> {info}")
    segment_files.append(seg_path)

cap.release()

concat_list = os.path.join(SCRATCH_DIR, "concat_list.txt")
with open(concat_list, "w", encoding="utf-8") as f:
    for sf in segment_files:
        safe_p = sf.replace("\\", "/")
        f.write(f"file '{safe_p}'\n")

subprocess.run([
    "ffmpeg", "-y", "-loglevel", "error",
    "-f", "concat", "-safe", "0",
    "-i", concat_list,
    "-c", "copy",
    "-movflags", "+faststart",
    OUT_REEL
], check=True)

shutil.copyfile(OUT_REEL, ROOT_COPY)

# Save 2-column 1080p proof sheet in Artifact dir
while len(proof_tiles) % 2 != 0:
    proof_tiles.append(np.zeros((360, 640, 3), dtype=np.uint8))
rows = [np.hstack([proof_tiles[i], proof_tiles[i + 1]]) for i in range(0, len(proof_tiles), 2)]
proof_grid = np.vstack(rows)
proof_path = os.path.join(ARTIFACT_DIR, "cu_ricecookers_g4_ot_reel_proof.jpg")
cv2.imwrite(proof_path, proof_grid, [cv2.IMWRITE_JPEG_QUALITY, 92])

pr_final = subprocess.run(
    ["ffprobe", "-v", "error", "-select_streams", "v:0",
     "-show_entries", "stream=codec_name,width,height,r_frame_rate,bit_rate:format=duration,size",
     "-of", "default=noprint_wrappers=1", OUT_REEL],
    capture_output=True, text=True
)
print("=== FINAL 1080p CU VS RICECOOKERS OT REEL FFPROBE ===")
print(pr_final.stdout)
print(f"Saved proof grid -> {proof_path}")
