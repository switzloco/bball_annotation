import os
import sys
import json
import cv2
import numpy as np
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8")

out_dir = r"C:\Users\Nick\.gemini\antigravity\brain\92e691fb-4334-4d76-9835-87d6d959086f\scratch\oct2026_probe"
os.makedirs(out_dir, exist_ok=True)

games = [
    ("2026-10-04_CU_vs_Mustangs_Champ", r"c:\dev\bball_annotation\majestic_oct2026\2026-10-04_CU_vs_Mustangs_Champ.mp4", r"c:\dev\bball_annotation\majestic_oct2026\2026-10-04_CU_vs_Mustangs_Champ_full.json"),
    ("2026-10-18_CU_vs_HalalHoopers_G1", r"c:\dev\bball_annotation\majestic_oct2026\2026-10-18_CU_vs_HalalHoopers_G1.mp4", r"c:\dev\bball_annotation\majestic_oct2026\2026-10-18_CU_vs_HalalHoopers_G1_full.json"),
    ("2026-10-25_CU_vs_TMT_G2", r"c:\dev\bball_annotation\majestic_oct2026\2026-10-25_CU_vs_TMT_G2.mp4", r"c:\dev\bball_annotation\majestic_oct2026\2026-10-25_CU_vs_TMT_G2_full.json"),
]

for slug, vpath, jpath in games:
    cap = cv2.VideoCapture(vpath)
    fps = cap.get(cv2.CAP_PROP_FPS)
    nframes = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    dur = nframes / fps if fps else 0

    with open(jpath, "r", encoding="utf-8") as f:
        d = json.load(f)
    statlog = [s for s in d.get("statlog", []) if s.get("stat_type") != "dnp" and s.get("period") in (1, 2)]
    statlog.sort(key=lambda x: x["logged_at"])

    p1 = [s for s in statlog if s["period"] == 1]
    p2 = [s for s in statlog if s["period"] == 2]

    t1_start = datetime.fromisoformat(p1[0]["logged_at"].replace("Z", "+00:00"))
    t1_end = datetime.fromisoformat(p1[-1]["logged_at"].replace("Z", "+00:00"))
    t2_start = datetime.fromisoformat(p2[0]["logged_at"].replace("Z", "+00:00"))
    t2_end = datetime.fromisoformat(p2[-1]["logged_at"].replace("Z", "+00:00"))

    print(f"\n=== {slug} ===")
    print(f"Video: {w}x{h} @ {fps:.2f}fps, duration={dur:.1f}s ({dur/60:.1f}m)")
    print(f"P1 wall span: {(t1_end - t1_start).total_seconds():.1f}s ({p1[0]['logged_at']} [{p1[0]['clock']}] -> {p1[-1]['logged_at']} [{p1[-1]['clock']}])")
    print(f"Halftime wall gap: {(t2_start - t1_end).total_seconds():.1f}s")
    print(f"P2 wall span: {(t2_end - t2_start).total_seconds():.1f}s ({p2[0]['logged_at']} [{p2[0]['clock']}] -> {p2[-1]['logged_at']} [{p2[-1]['clock']}])")
    print(f"Total wall span (P1 first to P2 last): {(t2_end - t1_start).total_seconds():.1f}s")

    # Save overview contact sheet across the whole video (every 120s) + first 15 minutes (every 30s)
    tiles = []
    for sec in range(0, min(int(dur), 1200), 30):
        cap.set(cv2.CAP_PROP_POS_MSEC, sec * 1000)
        ok, frame = cap.read()
        if not ok:
            continue
        thumb = cv2.resize(frame, (320, 180))
        mm, ss = sec // 60, sec % 60
        cv2.rectangle(thumb, (0, 0), (190, 26), (0, 0, 0), -1)
        cv2.putText(thumb, f"{mm:02d}:{ss:02d} ({sec}s)", (6, 19), cv2.FONT_HERSHEY_SIMPLEX, 0.58, (0, 255, 255), 2)
        tiles.append(thumb)
    cols = 5
    while len(tiles) % cols != 0:
        tiles.append(np.zeros((180, 320, 3), dtype=np.uint8))
    grid = np.vstack([np.hstack(tiles[r*cols:(r+1)*cols]) for r in range(len(tiles)//cols)])
    cv2.imwrite(os.path.join(out_dir, f"{slug}_early_grid.jpg"), grid, [int(cv2.IMWRITE_JPEG_QUALITY), 88])
    cap.release()
