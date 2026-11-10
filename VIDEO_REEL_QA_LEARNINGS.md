# Video Reel Quality & Sync QA Learnings (`#2 Mo` WeTheNorth Reel Post-Mortem)

**Date**: November 10, 2026  
**Scope**: Root-cause investigation and permanent pipeline fix for degraded visual quality and late-game timestamp drift at the end of `2026-11-01_WTN_Mo_Highlight_Reel.mp4` (`Clips #6–#11`, Game 3 vs. Crunch Time).

---

## 1. Executive Summary: Why the End of Mo's Reel Looked Bad

Investigation with `ffprobe` stream diagnostics and physical gym LED scoreboard contact sheets uncovered **three compounding root causes** that hit `Clips #6–#11` (the entire second half of the reel):

| Failure Layer | Before (Broken v1 Reel) | After (Fixed 1080p v2 Reel) |
| :--- | :--- | :--- |
| **1. YouTube Ingest Stream (`yt-dlp`)** | Missing `--js-runtimes node` caused YouTube's JS challenge solver to fail silently and fall back to **Format `398` (`1280x720` AV1 @ `547 kbps`)** — starving wide-angle gym footage of detail and breaking hardware decode on Safari/iOS. | Explicit `--js-runtimes node -f "137+140"` pulls **Format `137` (`1920x1080` Full HD H.264 @ `1,733 kbps`)** — **2.25× pixel count** and **3.2× higher source video bitrate**. |
| **2. Multi-Generation Re-Encoding** | Decoded `547 kbps` AV1 -> wrote intermediate OpenCV `mp4v` (`mpeg4` Part 2) -> re-encoded a **3rd time** with `ffmpeg -c:v libx264 -preset fast -crf 23`, crushing `Clip #10` down to **`860 kbps`** with heavy macroblocking. | **Zero intermediate file**: Python pipes uncompressed `bgr24` frames directly (`-f rawvideo`) into a **single-pass** `ffmpeg -c:v libx264 -preset slow -crf 17 -profile:v high` (~`5,000+ kbps` 1080p) plus a **2.0× `ISO CAM` Lanczos PiP zoom**. |
| **3. Stopped-Clock Drift & Flipped Hoop Direction** | `logged_at` wall-clock deltas drifted by **35–53 seconds** during late-game free throws/timeouts in Game 3 (`Clips #8–#11`). Worse, a +45s shift landed on the *next* possession at the opposite basket, masking that `WeTheNorth` (White `#2 Mo`) actually attacked the **near/right hoop** in H2 (`Clip #10` cut free-throw congestion at `4:57` instead of `#2 Mo`'s pull-up 3 at `5:53`; `Clip #11` cut midcourt jogging at `0:34` instead of his buzzer 3 at `0:09`). | Anchored directly to the **physical gym wall LED game clock** (`y=340..455, x=1630..1755` on 1080p). All 5 of `#2 Mo`'s 3-pointers (`2725s`, `3098s`, `3126s`, `3151s`, `3673s`) and his H1 block (`1016s`) now show `#2` in white right in the foreground splashing every shot. |

---

## 2. Technical Deep-Dive & Mandatory Pipeline Rules

### Rule 1: Always Pass `--js-runtimes node` and Force 1080p H.264 (`avc1`) in `yt-dlp`
Recent YouTube player updates gate `1080p` (`itag 137` / `itag 270`) behind a JavaScript `n`-challenge. When `yt-dlp` runs without `--js-runtimes node` on Windows:
1. It emits a non-fatal warning (`No supported JavaScript runtime could be found`) and hides `1080p` MP4 formats.
2. `-f "bestvideo[ext=mp4]+bestaudio[ext=m4a]"` selects **`av01` (AV1) 720p (`itag 398`) at ~`540 kbps`** because YouTube packs AV1 inside `.mp4` containers.
3. At `540 kbps` on a wide-angle gym camera, distant players (~35×70 px) lose jersey numbers and limb edges, and AV1 `.mp4` files fail to play on older iOS/Safari clients.

**Mandatory Download Command**:
```powershell
& "C:\Users\Nick\AppData\Local\Python\bin\python.exe" -X utf8 -m yt_dlp `
  --js-runtimes node `
  -f "137+140-7/137+140/bestvideo[ext=mp4][vcodec^=avc1]+bestaudio[ext=m4a]" `
  --merge-output-format mp4 `
  -o "<output>.mp4" "<youtube_url>"
```

### Rule 2: Never Use `cv2.VideoWriter("mp4v")` as an Intermediate Before `ffmpeg`
OpenCV's built-in `mp4v` FourCC invokes legacy **MPEG-4 Part 2** (`mpeg4`) without modern rate-control, introducing severe mosquito noise and 8×8 DCT ringing around high-contrast text overlays and small moving players. Re-encoding that `mp4v` output with `libx264 -crf 23` compounds two lossy quantization stages on top of YouTube's compression.

**Mandatory Single-Pass Raw Pipe Pattern** (see `build_mo_highlight_reel_1080p.py`):
- Keep frames as uncompressed `1920x1080` `uint8` BGR arrays in memory.
- Render crisp `cv2.INTER_LANCZOS4` 2.0× `ISO CAM` Picture-in-Picture (PiP) insets (placed on the opposite side of the live hoop & scoreboard) + ASCII broadcast lower-thirds (`cv2.LINE_AA`).
- Stream `frame.tobytes()` directly into `ffmpeg -loglevel error -f rawvideo -pix_fmt bgr24 -s 1920x1080 -r 30000/1001 -i -` with `-c:v libx264 -preset medium -crf 17 -profile:v high -level 4.1 -pix_fmt yuv420p -movflags +faststart`.
- **Windows Pipe Deadlock Trap**: Never pair `stdin=subprocess.PIPE` with an unread `stderr=subprocess.PIPE` when streaming 6 MB uncompressed 1080p frames into `ffmpeg`. Without `-loglevel error` and `stderr=subprocess.DEVNULL` (or an async reader thread), `ffmpeg`'s per-frame `stderr` progress fills the OS pipe buffer and deadlocks both processes on Segment 1.

### Rule 3: Calibrate Timestamps Against the Physical Gym LED Scoreboard, Never Raw Wall-Clock Alone
Statlog `logged_at` timestamps measure **real-world wall time** when the scorekeeper taps the tablet, whereas game play-by-play clocks (`12:54`, `6:45`, `6:18`, `5:53`, `0:00`) measure **running/stopped gym LED clock time**:
- Even in running-clock rec leagues, the clock stops for timeouts, injuries, and final-2-minute dead balls, and scorekeepers frequently batch-log rebounds/assists/fouls several seconds late.
- By late 2nd Half, linear `p2_first_sec + (logged_at - t2_0)` drifted by **+38s to +53s** in Game 3 (`s=3203` instead of `s=3151` for 3PT #4) and **-174s** in Game 2 (`s=3276` where LED read `5:59` instead of `s=3450` where LED read `3:05`).
- A ~40-second error equals **one full basketball possession**, meaning the ball is at the *opposite* hoop — which can trick visual QA into thinking the teams switched baskets!

**Mandatory QA Gate Before Publishing Any Reel**:
1. Crop the physical gym wall LED scoreboard (`~120x100 px`) as an inset onto every candidate highlight contact sheet.
2. Verify **both** that the LED game clock matches the statlog `clock` (`±3s`) **and** that the target player's jersey number (`#2` for Mo) is visibly making the shot/block/steal in the frame.
3. Append a cache-busting version query parameter (e.g. `?v=1080p2`) whenever overwriting an existing `.mp4` object on Google Cloud Storage (`gs://basketball-highlights-store/...`) so browser caches and GCS CDN edges immediately serve the newly encoded file.
