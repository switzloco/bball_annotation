Subject: 🏀 Campbell United Film Room & Nov 8 Scouting Report (vs. Ricecookers) — Live Links, Video Analysis Breakdown & Colab Roadmap

To: nicholas.switzer@gmail.com

Hey Nick,

Everything is finished, verified, and deployed live! Here is the complete summary of what we built, how the video analysis pipeline works, what we spent ($0.00 in API costs), and how we can use Google Colab with your Google AI Ultra plan going forward.

======================================================================
1. LIVE LINKS (READY TO SHARE WITH CAMPBELL UNITED ON WHATSAPP)
======================================================================
• Main Campbell United Film Room & Hub:
  https://bball-film-room-615717094211.us-central1.run.app

• 📋 Nov 8 Opponent Scouting Report: vs. Ricecookers (Sun Nov 8 @ 8:00 PM — The Grove CC):
  https://bball-film-room-615717094211.us-central1.run.app/?game=scouting_nov8

• 🏆 Fall '26 Championship (Oct 4, 2026 — Campbell United 76, Mustangs 66):
  https://bball-film-room-615717094211.us-central1.run.app/?game=2026-10-04_CU_vs_Mustangs_Champ

• 🏀 Holiday '26 Game 1 (Oct 18, 2026 — Campbell United 69, Halal Hoopers 47):
  https://bball-film-room-615717094211.us-central1.run.app/?game=2026-10-18_CU_vs_HalalHoopers_G1

• 🔥 Holiday '26 Game 2 (Oct 25, 2026 — Campbell United 52, TMT 50):
  https://bball-film-room-615717094211.us-central1.run.app/?game=2026-10-25_CU_vs_TMT_G2

• 🚀 Holiday '26 Game 3 (Nov 1, 2026 — Campbell United 83, Misfits 2 66):
  https://bball-film-room-615717094211.us-central1.run.app/?game=2026-11-01_CU_vs_Misfits2_G3

======================================================================
2. WHAT WE DID
======================================================================
1. Made the Site 100% Campbell United Team-Focused (Removed "Nick #7" Self-Focus):
   - Removed all "#7 Nick Switzer" buttons, dropdown callouts, filter presets, and box-score priority sorting.
   - Added a Campbell United Season Quick-Bar at the top so teammates on WhatsApp or desktop can jump in 1 tap between the Oct 4 Championship vs. Mustangs, Holiday '26 Games 1-3, and the Nov 8 Scouting Report vs. Ricecookers.
   - Box scores and Top 5 Plays now highlight the entire squad sorted naturally by points/rebounds/assists (#44 Christian Raslowsky, #31 Evan Kovarik, #16 Chris, #4 Adam Fecteau, #9 Aaron, #7 Nick Switzer, #22 Matt Mocherman, #24 George, #20 Shane Hoffman, #12 Corey Randolph).

2. Discovered Majestic Hoops' New Stats API & Synced All October-November 2026 Games:
   - Discovered that Majestic Hoops migrated from recleague.net to https://mh.majesticstats.com/ and posts full game broadcasts to https://www.youtube.com/@majestichoops/videos.
   - Pulled full JSON stat logs and box scores from mh.majesticstats.com/api/games/<id>/full for your Fall '26 Championship (Game 5211), Holiday '26 Game 1 vs. Halal Hoopers (Game 5505), Game 2 vs. TMT (Game 5893), Game 3 vs. Misfits 2 (Game 5858), and all 3 Ricecookers Holiday '26 games (Games 5508, 5804, 5801).
   - Downloaded the 3 October 2026 full-game MP4 broadcasts, synced every play to the exact video timestamp, and uploaded them to Google Cloud Storage (gs://basketball-highlights-store/majestic/).

3. Built the Nov 8 Opponent Scouting Report (vs. Ricecookers — Sun Nov 8 @ 8:00 PM at The Grove CC):
   - Tale of the Tape: Campbell United (3-0, 68.0 PPG, 54.3 OPP PPG, 39.7 RPG) vs. Ricecookers (0-3, 63.0 PPG, 68.7 OPP PPG, 29.0 RPG — deceptive 0-3 record with close losses by 9, 5, and 3 pts).
   - Common Opponents: vs. TMT (CU won 52-50; Ricecookers lost 55-58) and vs. Misfits 2 (CU won 83-66; Ricecookers lost 71-80).
   - Key Scouting Discovery: Ricecookers' #11 Dylan has played 58 minutes across all 3 games without taking a single shot (0 FGA, 0 FTA). Whoever guards #11 Dylan (#24 George / #22 Matt / #16 Chris / #44 Christian) can sag 10 feet into the paint as a free rim protector to wall off #3 Dustin's drives (17.7 PPG)! Meanwhile, never help off catch-and-shoot wings #4 Eugene (3/5 3PT vs TMT) or #12 AJ (3/5 3PT vs TMT), and attack #1 Aaron early (11 fouls in 3 games = 3.7 PF/G).

======================================================================
3. WHAT WE USED FOR VIDEO ANALYSIS & SYNCING
======================================================================
• yt-dlp + FFmpeg Contact-Sheet Probing:
  Downloaded the @majestichoops MP4s and generated multi-frame contact sheets to find the exact opening tip-off and halftime transitions:
  - In the Oct 4 Championship (Y1Dh7T0iqZA at Gunderson HS), the first 19m30s of the broadcast was the end of the previous game on that court; Campbell United's tip-off was at 19:30 (1170s), and the first logged play (19:47 P1) mapped to 1185s.
  - In Oct 18 vs. Halal Hoopers (GOoSXuhvvMM) and Oct 25 vs. TMT (G_ALwG-ok70) at The Grove CC, Majestic used a panning AI "BallerCam" at midcourt, with tip-offs at 04:00 (240s) and 13:00 (780s).

• Millisecond Wall-Clock Anchor Fusion + OpenCV Rim Motion (cv2):
  - Every event in mh.majesticstats.com/api/games/<id>/full includes a millisecond-precision ISO timestamp (logged_at). Because the camera records continuously through halftime without pausing, anchoring Period 1 tip-off and subtracting a 3.5-second human scorekeeper reaction lag synced every play across both halves to within ~1 second!
  - Paired assist logs with made baskets within a 5.5s window on the same team, and automatically reconstructed unlogged missed shots prior to rebounds.
  - For fixed-camera games (Gunderson HS), we also used OpenCV (cv2) pixel-difference rim-energy spikes inside the left/right hoop ROIs and LED scoreboard crops to verify splash frames.

======================================================================
4. HOW MUCH WE SPENT
======================================================================
• Paid AI / LLM / Vision API Spend: $0.00 (Zero dollars!)
  All video downloading, FFmpeg contact-sheet probing, OpenCV rim-energy analysis, and JSON statlog fusion ran locally at zero API cost.
• Google Cloud Storage & Cloud Run: ~$0.00 - $0.03
  Covered by GCP Free Tier (~1.3 GB of MP4 files in gs://basketball-highlights-store/majestic/ + scale-to-zero Cloud Run container).

======================================================================
5. HOW WE CAN LEVERAGE GOOGLE COLAB (WITH GOOGLE AI ULTRA) IN THE FUTURE
======================================================================
With your Google AI Ultra plan (which gives you high-memory GPU runtimes like NVIDIA A100 / L4 in Google Colab plus high-rate Gemini 2.5 Pro access), we can build a "1-Click Sunday Night Campbell United Colab Pipeline":

1. Panning BallerCam Court Homography & 2D Shot Charts (Colab GPU):
   - Because The Grove CC uses a panning BallerCam, hoop coordinates shift every second. On a Colab L4/A100 GPU, we can run a basketball court keypoint detector + YOLOv11 ball/rim tracker at 60+ FPS to map every make and miss onto a clean top-down 2D court shot chart for both Campbell United and your opponents.

2. Automatic Missed-Shot & Unlogged Assist Detection:
   - Scorekeepers sometimes miss assists or don't log missed field goals. A Colab GPU notebook can scan rim-activity windows across a 60-minute video in ~2 minutes, find every unlogged shot attempt on the rim, and pass just those 6-second video snippets to Gemini to classify the shooter, passer, and shot type (driving floater, corner 3, post hook, etc.).

3. Opponent Scouting Clip Reels:
   - Before each Sunday game, Colab can pull your next opponent's latest @majestichoops YouTube video, slice out every offensive possession by their top 2 scorers (e.g., #3 Dustin and #22 Sim on Ricecookers), and stitch an automatic 90-second "Opponent Tendencies" highlight reel MP4 for the Campbell United group chat.

4. 10x Faster Video Ingest on Google Fiber:
   - Instead of downloading and uploading 200 MB MP4s over home Wi-Fi, Colab runs directly inside Google's network—downloading from YouTube and pushing straight to gs://basketball-highlights-store/majestic/ in seconds!
