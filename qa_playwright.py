import os
import subprocess
import sys
import time
from playwright.sync_api import sync_playwright

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

PORT = 8092
BASE_URL = os.environ.get("TARGET_URL", f"http://127.0.0.1:{PORT}")


def run_qa():
    server_proc = None
    if "127.0.0.1" in BASE_URL or "localhost" in BASE_URL:
        env = os.environ.copy()
        env["PORT"] = str(PORT)
        server_proc = subprocess.Popen(
            [sys.executable, "server.py"],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        time.sleep(1.5)

    console_errors = []
    page_errors = []

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1600, "height": 960})
            page = context.new_page()

            page.on(
                "console",
                lambda msg: console_errors.append(msg.text)
                if msg.type == "error"
                else None,
            )
            page.on("pageerror", lambda err: page_errors.append(str(err)))

            print(f"[1/7] Navigating to {BASE_URL} ...")
            page.goto(BASE_URL, wait_until="networkidle")
            time.sleep(1.0)

            # Check ESPN Broadcast UI elements
            print("[2/7] Verifying ESPN Broadcast UI, Scorebug, BottomLine & SC Top 5...")
            assert page.locator(".espn-logo-badge").is_visible(), "Missing ESPN logo badge"
            assert page.locator("#espnScorebug").is_visible(), "Missing ESPN scorebug"
            assert page.locator("#espnBottomline").is_visible(), "Missing ESPN BottomLine ticker"
            assert page.locator(".sc-badge").inner_text().strip() == "SC TOP 5", "Missing SC TOP 5 badge"
            assert page.locator(".top5-card").count() == 5, "Expected 5 Top Plays cards"

            # Ensure no banned words exist anywhere on page
            body_html = page.content().lower()
            assert "durag" not in body_html and "headwrap" not in body_html, "Found banned words in HTML!"

            # Wait for video metadata
            print("[3/7] Verifying <video> metadata & readyState...")
            page.wait_for_function(
                "() => document.getElementById('bballVideo').readyState >= 1",
                timeout=10000,
            )
            v_init = page.evaluate(
                """() => {
                const v = document.getElementById('bballVideo');
                return { src: v.currentSrc, readyState: v.readyState, duration: v.duration, error: v.error ? v.error.message : null };
            }"""
            )
            print("      Initial <video> state:", v_init)
            assert v_init["error"] is None, f"Video error on load: {v_init['error']}"
            assert v_init["duration"] > 2200, f"Unexpected duration: {v_init['duration']}"

            # Test A: Click very first play in Play-by-Play (00:01, s=1)
            print("[4/7] Clicking First Play in Play-by-Play (00:01, #play-s-1)...")
            page.locator("#play-s-1 .play-main-row").click()
            time.sleep(1.2)
            v_play1 = page.evaluate(
                """() => {
                const v = document.getElementById('bballVideo');
                const active = document.querySelector('.play-card.active-play');
                const score = document.getElementById('currentScore1s2s').textContent.trim();
                return {
                    readyState: v.readyState,
                    currentTime: v.currentTime,
                    paused: v.paused,
                    activeId: active ? active.id : null,
                    score: score,
                    error: v.error ? v.error.message : null
                };
            }"""
            )
            print("      After clicking 00:01 (#play-s-1):", v_play1)
            assert v_play1["error"] is None, f"Video error on 00:01: {v_play1['error']}"
            assert v_play1["readyState"] >= 2, f"Video stalled on 00:01: {v_play1}"
            assert v_play1["currentTime"] >= 0.4, f"Video currentTime did not advance from 0: {v_play1}"
            assert v_play1["activeId"] == "play-s-1", f"Expected activeId='play-s-1', got {v_play1['activeId']}"
            assert v_play1["score"] == "2 – 3", f"Expected score '2 – 3', got {v_play1['score']}"

            # Test B: Click #1 Play in SC Top 5 (23:05, s=1385) and verify pre-roll lock keeps play-s-1385 active!
            print("[5/7] Clicking #1 Play in SC Top 5 (23:05, #top5-s-1385)...")
            page.locator("#top5-s-1385").click()
            time.sleep(1.2)
            v_top1 = page.evaluate(
                """() => {
                const v = document.getElementById('bballVideo');
                const active = document.querySelector('.play-card.active-play');
                const score = document.getElementById('currentScore1s2s').textContent.trim();
                return {
                    readyState: v.readyState,
                    currentTime: v.currentTime,
                    paused: v.paused,
                    activeId: active ? active.id : null,
                    score: score,
                    error: v.error ? v.error.message : null
                };
            }"""
            )
            print("      After clicking SC Top 5 #1 (23:05):", v_top1)
            assert v_top1["error"] is None, f"Video error on 23:05: {v_top1['error']}"
            assert v_top1["readyState"] >= 2, f"Video stalled on 23:05: {v_top1}"
            assert 1382.0 <= v_top1["currentTime"] <= 1387.0, f"Unexpected currentTime on 23:05 seek: {v_top1['currentTime']}"
            assert v_top1["activeId"] == "play-s-1385", f"Pre-roll bug! Expected activeId='play-s-1385', got {v_top1['activeId']}"
            assert "16 – 14" in v_top1["score"], f"Expected '16 – 14 (Final)' on scoreboard, got {v_top1['score']}"

            # Test C: Verify Day-to-Day Persistent Crew Roster Strip & 1-Click Regular Selector
            print("[6/7] Verifying Day-to-Day Persistent Crew Roster (Josh, Damien, Kenny, Brian, Donnie, Timor, Rock, Spider)...")
            crew_pills_count = page.locator("#crewMasterRosterStrip .crew-member-pill").count()
            print(f"      Found {crew_pills_count} persistent crew member cards in #crewMasterRosterStrip")
            assert crew_pills_count >= 8, f"Expected >= 8 regular crew members, got {crew_pills_count}"

            # Select 'Kenny' in the 1-Click Regular Crew dropdown and verify auto-fill
            page.locator("#crewRegularSelect").select_option("Kenny")
            filled_name = page.locator("#crewRealNameInput").input_value()
            filled_traits = page.locator("#crewTraitsInput").input_value()
            print(f"      1-Click Regular Select ('Kenny') -> Name='{filled_name}', Traits='{filled_traits}'")
            assert filled_name == "Kenny", f"Expected 'Kenny', got '{filled_name}'"
            assert "teal shoes" in filled_traits.lower(), f"Expected Kenny's traits, got '{filled_traits}'"

            # Test 3v3 Half-Court Hoop Calibration
            print("[7/7] Verifying 3v3 Half-Court & Interactive Hoop Calibration Overlay...")
            page.locator("#formatPicker").select_option("3v3_half_court")
            page.locator("#calibrateBtn").click()
            assert page.locator("#hoopCalibOverlay").is_visible(), "Hoop calibration overlay did not open"
            page.locator("#hoopCalibOverlay").click(position={"x": 300, "y": 200})
            time.sleep(0.4)
            btn_text = page.locator("#calibrateBtn").inner_text()
            print(f"      Calibration button status: '{btn_text}'")
            assert "Hoops Saved (1)" in btn_text, f"Expected 'Hoops Saved (1)', got '{btn_text}'"

            # Restore 5v5_full_court default
            page.locator("#formatPicker").select_option("5v5_full_court")
            time.sleep(0.3)

            # Take screenshot of the ESPN Broadcast UI
            screenshot_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "espn_film_room_qa.png")
            page.screenshot(path=screenshot_path, full_page=False)
            print(f"      Saved ESPN Broadcast UI screenshot to {screenshot_path}")

            browser.close()

        assert len(console_errors) == 0, f"Console errors detected: {console_errors}"
        assert len(page_errors) == 0, f"Uncaught page errors detected: {page_errors}"
        print("\n✅ ALL PLAYWRIGHT QA TESTS PASSED WITH ZERO ERRORS!")
    finally:
        if server_proc:
            server_proc.terminate()
            try:
                server_proc.wait(timeout=3)
            except Exception:
                server_proc.kill()


if __name__ == "__main__":
    run_qa()
