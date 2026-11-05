import os
import socket
import subprocess
import sys
import time
import urllib.request
import re
from playwright.sync_api import sync_playwright

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def get_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def extract_meta_from_html(html_text):
    def get_prop(prop):
        m = re.search(rf'<meta\s+property=["\']{re.escape(prop)}["\']\s+content=["\']([^"\']*)["\']', html_text, re.I)
        if not m:
            m = re.search(rf'<meta\s+content=["\']([^"\']*)["\']\s+property=["\']{re.escape(prop)}["\']', html_text, re.I)
        return m.group(1) if m else None

    return {
        "og:title": get_prop("og:title"),
        "og:description": get_prop("og:description"),
        "og:image": get_prop("og:image"),
    }


def run_mobile_qa():
    port = get_free_port()
    base_url = os.environ.get("TARGET_URL", f"http://127.0.0.1:{port}")
    server_proc = None

    if "127.0.0.1" in base_url or "localhost" in base_url:
        env = os.environ.copy()
        env["PORT"] = str(port)
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
        # Check dynamic ?play=1385 OpenGraph tags from server response
        with urllib.request.urlopen(f"{base_url}/?play=1385", timeout=5) as resp:
            play_1385_html = resp.read().decode("utf-8", errors="replace")
        dynamic_og_1385 = extract_meta_from_html(play_1385_html)

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={"width": 390, "height": 844},
                is_mobile=True,
                has_touch=True,
                device_scale_factor=3,
                user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
            )
            page = context.new_page()

            page.on(
                "console",
                lambda msg: console_errors.append(msg.text)
                if msg.type == "error"
                else None,
            )
            page.on("pageerror", lambda err: page_errors.append(str(err)))

            print(f"[Mobile QA] Navigating to {base_url} on 390x844 iPhone 14 Pro viewport...")
            page.goto(base_url, wait_until="networkidle")
            time.sleep(1.0)

            # 1. Measure initial layout metrics
            init_metrics = page.evaluate(
                """() => {
                const header = document.querySelector('header');
                const videoWrapper = document.getElementById('videoWrapper');
                const headerRect = header ? header.getBoundingClientRect() : { height: 0 };
                const videoRect = videoWrapper ? videoWrapper.getBoundingClientRect() : { top: 0, bottom: 0, height: 0 };
                const ogTitle = document.querySelector('meta[property="og:title"]');
                const ogDesc = document.querySelector('meta[property="og:description"]');
                const ogImage = document.querySelector('meta[property="og:image"]');
                const leftTeam = document.getElementById('leftTeamName');
                const rightTeam = document.getElementById('rightTeamName');
                const leftRect = leftTeam ? leftTeam.getBoundingClientRect() : { width: 0, height: 0 };
                const rightRect = rightTeam ? rightTeam.getBoundingClientRect() : { width: 0, height: 0 };
                const navTabs = document.getElementById('mobileNavTabs');
                const navTabsRect = navTabs ? navTabs.getBoundingClientRect() : { width: 0, height: 0 };
                const top5WaBtns = document.querySelectorAll('.top5-card button, .top5-card a');
                let top5WaCount = 0;
                top5WaBtns.forEach(b => { if ((b.textContent || '').includes('WhatsApp')) top5WaCount++; });
                const pbpWaBtns = document.querySelectorAll('.play-card button, .play-card a');
                let pbpWaCount = 0;
                pbpWaBtns.forEach(b => { if ((b.textContent || '').includes('WhatsApp')) pbpWaCount++; });

                return {
                    innerWidth: window.innerWidth,
                    innerHeight: window.innerHeight,
                    scrollWidth: document.documentElement.scrollWidth,
                    headerHeightPx: Math.round(headerRect.height * 10) / 10,
                    headerPctOf844: +(headerRect.height / 844 * 100).toFixed(1),
                    videoTopPx: Math.round(videoRect.top * 10) / 10,
                    videoHeightPx: Math.round(videoRect.height * 10) / 10,
                    videoBottomPx: Math.round(videoRect.bottom * 10) / 10,
                    leftTeamWidthPx: Math.round(leftRect.width * 10) / 10,
                    leftTeamHeightPx: Math.round(leftRect.height * 10) / 10,
                    rightTeamWidthPx: Math.round(rightRect.width * 10) / 10,
                    rightTeamHeightPx: Math.round(rightRect.height * 10) / 10,
                    mobileNavTabsVisible: navTabs ? (navTabsRect.height > 0 && getComputedStyle(navTabs).display !== 'none') : false,
                    mobileNavTabsCount: navTabs ? navTabs.querySelectorAll('button').length : 0,
                    top5WaCount: top5WaCount,
                    pbpWaCount: pbpWaCount,
                    ogTags: {
                        title: ogTitle ? ogTitle.getAttribute('content') : null,
                        description: ogDesc ? ogDesc.getAttribute('content') : null,
                        image: ogImage ? ogImage.getAttribute('content') : null,
                    }
                };
            }"""
            )

            # Save post-fix screenshot at top of page
            scratch_dir = r"C:\Users\Nick\.gemini\antigravity\brain\92e691fb-4334-4d76-9835-87d6d959086f\scratch"
            os.makedirs(scratch_dir, exist_ok=True)
            after_img = os.path.join(scratch_dir, "mobile_after.png")
            page.screenshot(path=after_img, full_page=False)
            print(f"[Mobile QA] Saved top-of-page mobile screenshot to {after_img}")

            # 2. Scroll down to #play-s-1385 and check if #videoWrapper stays sticky at top == 0
            scroll_metrics = page.evaluate(
                """() => {
                const playEl = document.getElementById('play-s-1385');
                if (playEl) {
                    playEl.scrollIntoView({ behavior: 'instant', block: 'center' });
                } else {
                    window.scrollTo(0, 1200);
                }
                const videoWrapper = document.getElementById('videoWrapper');
                const vRect = videoWrapper.getBoundingClientRect();
                const pRect = playEl ? playEl.getBoundingClientRect() : null;
                return {
                    scrollY: Math.round(window.scrollY),
                    videoTopAfterScrollPx: Math.round(vRect.top * 10) / 10,
                    videoBottomAfterScrollPx: Math.round(vRect.bottom * 10) / 10,
                    videoHeightAfterScrollPx: Math.round(vRect.height * 10) / 10,
                    videoStaysVisibleOnScroll: vRect.top >= 0 && vRect.bottom <= window.innerHeight && vRect.height > 50,
                    play1385TopPx: pRect ? Math.round(pRect.top * 10) / 10 : null
                };
            }"""
            )
            time.sleep(0.3)
            scrolled_img = os.path.join(scratch_dir, "mobile_scrolled_play1385.png")
            page.screenshot(path=scrolled_img, full_page=False)
            print(f"[Mobile QA] Saved scrolled play-1385 mobile screenshot to {scrolled_img}")

            # 3. Also test Android 412x915 viewport quick check
            android_ctx = browser.new_context(
                viewport={"width": 412, "height": 915},
                is_mobile=True,
                has_touch=True,
                device_scale_factor=2.625,
            )
            android_page = android_ctx.new_page()
            android_page.goto(base_url, wait_until="networkidle")
            android_metrics = android_page.evaluate(
                """() => ({
                    innerWidth: window.innerWidth,
                    scrollWidth: document.documentElement.scrollWidth,
                    headerHeightPx: Math.round(document.querySelector('header').getBoundingClientRect().height * 10) / 10
                })"""
            )
            android_ctx.close()

            print("\n=== POST-UPGRADE MOBILE & WHATSAPP QA METRICS (390x844 iPhone 14 Pro) ===")
            print(f"1. Compact Mobile Header: headerHeightPx = {init_metrics['headerHeightPx']}px ({init_metrics['headerPctOf844']}% of 844px viewport) [Target: <= 64px]")
            print(f"2. Zero Horizontal Overflow: scrollWidth = {init_metrics['scrollWidth']}px, innerWidth = {init_metrics['innerWidth']}px [Target: 390 == 390]")
            print(f"   (Android 412x915 check: scrollWidth = {android_metrics['scrollWidth']}px, innerWidth = {android_metrics['innerWidth']}px, headerHeightPx = {android_metrics['headerHeightPx']}px)")
            print(f"3. Sticky Video Player on Scroll to #play-s-1385 (scrollY={scroll_metrics['scrollY']}px):")
            print(f"   - Initial #videoWrapper top = {init_metrics['videoTopPx']}px (height = {init_metrics['videoHeightPx']}px)")
            print(f"   - Scrolled #videoWrapper.getBoundingClientRect().top = {scroll_metrics['videoTopAfterScrollPx']}px (bottom = {scroll_metrics['videoBottomAfterScrollPx']}px)")
            print(f"   - videoStaysVisibleOnScroll = {scroll_metrics['videoStaysVisibleOnScroll']}")
            print(f"4. Scorebug Readability:")
            print(f"   - #leftTeamName ('NEAR HOOP SQUAD'): width = {init_metrics['leftTeamWidthPx']}px, height = {init_metrics['leftTeamHeightPx']}px")
            print(f"   - #rightTeamName ('FAR HOOP SQUAD'): width = {init_metrics['rightTeamWidthPx']}px, height = {init_metrics['rightTeamHeightPx']}px")
            print(f"5. WhatsApp OpenGraph & Share Controls:")
            print(f"   - Static OG Tags: {init_metrics['ogTags']}")
            print(f"   - Dynamic ?play=1385 OG Tags: {dynamic_og_1385}")
            print(f"   - Mobile Quick-Jump Tabs (#mobileNavTabs): visible={init_metrics['mobileNavTabsVisible']}, count={init_metrics['mobileNavTabsCount']}")
            print(f"   - '📲 WhatsApp' buttons: {init_metrics['top5WaCount']} on Top 5 cards, {init_metrics['pbpWaCount']} on Play-by-Play cards")

            # Assertions
            assert init_metrics["headerHeightPx"] <= 64, f"Header too tall: {init_metrics['headerHeightPx']}px"
            assert init_metrics["scrollWidth"] == 390 and init_metrics["innerWidth"] == 390, f"Horizontal overflow: scrollWidth={init_metrics['scrollWidth']}, innerWidth={init_metrics['innerWidth']}"
            assert scroll_metrics["videoTopAfterScrollPx"] == 0, f"Expected sticky video top == 0, got {scroll_metrics['videoTopAfterScrollPx']}"
            assert scroll_metrics["videoStaysVisibleOnScroll"] is True, "Video not visible on scroll"
            assert init_metrics["leftTeamWidthPx"] >= 55 and init_metrics["rightTeamWidthPx"] >= 55, "Scorebug team names too narrow!"
            assert init_metrics["ogTags"]["title"] and init_metrics["ogTags"]["description"] and init_metrics["ogTags"]["image"], "Missing static OG tags!"
            assert dynamic_og_1385["og:title"] and "23:05" in dynamic_og_1385["og:title"], f"Dynamic ?play=1385 og:title unexpected: {dynamic_og_1385}"
            assert init_metrics["mobileNavTabsVisible"] and init_metrics["mobileNavTabsCount"] >= 4, "Missing #mobileNavTabs!"
            assert init_metrics["top5WaCount"] == 5, f"Expected 5 WhatsApp buttons in Top 5, got {init_metrics['top5WaCount']}"
            assert init_metrics["pbpWaCount"] >= 20, f"Expected >=20 WhatsApp buttons in Play-by-Play, got {init_metrics['pbpWaCount']}"
            assert len(console_errors) == 0, f"Console errors: {console_errors}"
            assert len(page_errors) == 0, f"Page errors: {page_errors}"

            print("\n✅ ALL MOBILE & WHATSAPP PLAYWRIGHT QA CHECKS PASSED!")
            browser.close()
    finally:
        if server_proc:
            server_proc.terminate()
            try:
                server_proc.wait(timeout=3)
            except Exception:
                server_proc.kill()


if __name__ == "__main__":
    run_mobile_qa()
