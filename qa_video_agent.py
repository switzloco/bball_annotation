import os
import time
import json
from playwright.sync_api import sync_playwright

LIVE_URL = "https://bball-film-room-615717094211.us-central1.run.app"
SCREENSHOT_DIR = r"C:\Users\Nick\.gemini\antigravity\brain\f7aa97bb-346a-4ff4-986d-b1d19e148b19\scratch"
os.makedirs(SCREENSHOT_DIR, exist_ok=True)


def get_video_metrics(page):
    return page.evaluate("""() => {
        const v = document.getElementById('bballVideo');
        if (!v) return null;
        return {
            src: v.currentSrc || v.src,
            videoWidth: v.videoWidth,
            videoHeight: v.videoHeight,
            readyState: v.readyState,
            networkState: v.networkState,
            paused: v.paused,
            muted: v.muted,
            seeking: v.seeking,
            currentTime: v.currentTime,
            duration: v.duration,
            webkitDecodedFrameCount: v.webkitDecodedFrameCount || 0,
            webkitDroppedFrameCount: v.webkitDroppedFrameCount || 0,
            error: v.error ? { code: v.error.code, message: v.error.message } : null
        };
    }""")


def run_qa(url=LIVE_URL, label="cloud_run"):
    print(f"=== Running Real Google Chrome Video QA against {url} ({label}) ===")
    results = {"url": url, "label": label, "plays": {}, "early_click_test": None, "rapid_click_test": None}

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        context = browser.new_context(viewport={"width": 1600, "height": 950})
        page = context.new_page()

        console_errors = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)

        # 1. Test Early Click (within 100ms of DOMContentLoaded before metadata finishes loading)
        page.goto(url, wait_until="domcontentloaded")
        early_initial = get_video_metrics(page)
        print(f"[Early Click Test] Initial state on domcontentloaded: readyState={early_initial['readyState']}, currentTime={early_initial['currentTime']}")
        page.locator("#top5-s-1355").click()
        # Wait for metadata + seek + 1.5s playback (1355 - 5.0 = 1350.0s, catching Rock's 22:33 dish!)
        page.wait_for_function("""() => {
            const v = document.getElementById('bballVideo');
            return v && v.readyState >= 2 && !v.seeking && v.currentTime >= 1349;
        }""", timeout=15000)
        t_early_before = get_video_metrics(page)
        time.sleep(1.5)
        t_early_after = get_video_metrics(page)
        early_dt = t_early_after["currentTime"] - t_early_before["currentTime"]
        early_df = t_early_after["webkitDecodedFrameCount"] - t_early_before["webkitDecodedFrameCount"]
        results["early_click_test"] = {
            "initial_readyState": early_initial["readyState"],
            "before": t_early_before,
            "after": t_early_after,
            "dt_1_5s": round(early_dt, 3),
            "decoded_frames_delta": early_df,
            "pass": (1349.0 <= t_early_before["currentTime"] <= 1353.0) and (early_dt >= 0.8) and (early_df >= 20) and (not t_early_after["paused"])
        }
        print(f"[Early Click Test] Target=1350.0s (22:30 setup before 22:33 dish) | Before={t_early_before['currentTime']:.2f}s -> After={t_early_after['currentTime']:.2f}s (dt={early_dt:.2f}s, +frames={early_df}, paused={t_early_after['paused']})")

        # 2. Reload cleanly and wait for metadata to test all 5 target plays + rapid clicking
        page.goto(url, wait_until="networkidle")
        page.wait_for_function("() => document.getElementById('bballVideo').readyState >= 1", timeout=15000)
        base_metrics = get_video_metrics(page)
        results["initial_metadata"] = base_metrics
        print(f"[Metadata Ready] {base_metrics['videoWidth']}x{base_metrics['videoHeight']}, duration={base_metrics['duration']}s, readyState={base_metrics['readyState']}, error={base_metrics['error']}")

        test_cases = [
            ("play_1_0001", "#play-s-1 .play-main-row", 1, 0.5),
            ("top5_1_1385", "#top5-s-1385", 1385, 1380.0),
            ("top5_2_1355", "#top5-s-1355", 1355, 1350.0),
            ("top5_3_1297", "#top5-s-1297", 1297, 1292.0),
            ("top5_4_2141", "#top5-s-2141", 2141, 2136.0),
        ]

        for name, selector, sec, expected_target in test_cases:
            loc = page.locator(selector)
            loc.scroll_into_view_if_needed()
            loc.click()

            # Wait until seek completes and readyState >= 2
            page.wait_for_function(f"""() => {{
                const v = document.getElementById('bballVideo');
                return v && !v.seeking && v.readyState >= 2 && Math.abs(v.currentTime - {expected_target}) < 2.5;
            }}""", timeout=15000)

            m_before = get_video_metrics(page)
            time.sleep(1.5)
            m_after = get_video_metrics(page)

            dt = m_after["currentTime"] - m_before["currentTime"]
            df = m_after["webkitDecodedFrameCount"] - m_before["webkitDecodedFrameCount"]
            active_card_ok = page.evaluate(f"() => document.getElementById('play-s-{sec}')?.classList.contains('active-play') || false")

            shot_path = os.path.join(SCREENSHOT_DIR, f"qa_{label}_{name}.png")
            page.screenshot(path=shot_path)

            passed = (
                abs(m_before["currentTime"] - expected_target) < 1.5
                and dt >= 0.8
                and df >= 20
                and m_after["paused"] is False
                and m_after["videoWidth"] == 1280
                and m_after["videoHeight"] == 720
                and m_after["error"] is None
            )
            results["plays"][name] = {
                "selector": selector,
                "play_seconds": sec,
                "expected_target": expected_target,
                "t_before": round(m_before["currentTime"], 3),
                "t_after": round(m_after["currentTime"], 3),
                "dt_over_1_5s": round(dt, 3),
                "frames_before": m_before["webkitDecodedFrameCount"],
                "frames_after": m_after["webkitDecodedFrameCount"],
                "frames_decoded_delta": df,
                "videoWidth": m_after["videoWidth"],
                "videoHeight": m_after["videoHeight"],
                "readyState": m_after["readyState"],
                "paused": m_after["paused"],
                "error": m_after["error"],
                "active_card_highlighted": active_card_ok,
                "screenshot": shot_path,
                "pass": passed
            }
            print(f"[{name}] target={expected_target}s | t_before={m_before['currentTime']:.2f}s -> t_after={m_after['currentTime']:.2f}s | dt={dt:.2f}s | +frames={df} | paused={m_after['paused']} | active={active_card_ok} | PASS={passed}")

        # 3. Rapid Multi-Click Test (click 3 plays within 150ms, verify final play wins)
        page.locator("#top5-s-1297").click()
        time.sleep(0.05)
        page.locator("#top5-s-1355").click()
        time.sleep(0.05)
        page.locator("#top5-s-1385").click()

        page.wait_for_function("""() => {
            const v = document.getElementById('bballVideo');
            return v && !v.seeking && v.readyState >= 2 && Math.abs(v.currentTime - 1380.0) < 2.5;
        }""", timeout=15000)
        r_before = get_video_metrics(page)
        time.sleep(1.5)
        r_after = get_video_metrics(page)
        r_dt = r_after["currentTime"] - r_before["currentTime"]
        r_df = r_after["webkitDecodedFrameCount"] - r_before["webkitDecodedFrameCount"]
        results["rapid_click_test"] = {
            "expected_target": 1380.0,
            "t_before": round(r_before["currentTime"], 3),
            "t_after": round(r_after["currentTime"], 3),
            "dt_over_1_5s": round(r_dt, 3),
            "frames_decoded_delta": r_df,
            "paused": r_after["paused"],
            "pass": abs(r_before["currentTime"] - 1380.0) < 1.5 and r_dt >= 0.8 and r_df >= 20 and not r_after["paused"]
        }
        print(f"[Rapid Click Test] Final=1380.0s | t_before={r_before['currentTime']:.2f}s -> t_after={r_after['currentTime']:.2f}s | dt={r_dt:.2f}s | +frames={r_df} | PASS={results['rapid_click_test']['pass']}")

        results["console_errors"] = console_errors
        browser.close()

    out_json = os.path.join(SCREENSHOT_DIR, f"qa_results_{label}.json")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"Saved results to {out_json}")
    return results


if __name__ == "__main__":
    run_qa()
