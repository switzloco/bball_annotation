import subprocess
import sys
import json
import urllib.request
from bs4 import BeautifulSoup

sys.stdout.reconfigure(encoding="utf-8")

# 1. Check @majestichoops YouTube channel
cmd = [
    sys.executable,
    "-m",
    "yt_dlp",
    "--flat-playlist",
    "--dump-single-json",
    "--playlist-end",
    "80",
    "https://www.youtube.com/@majestichoops/videos",
]
out = subprocess.check_output(cmd, text=True, encoding="utf-8", errors="replace")
data = json.loads(out)
entries = data.get("entries", [])
print(f"=== @majestichoops YouTube Channel (fetched {len(entries)} videos) ===")
for i, e in enumerate(entries):
    t = e.get("title", "")
    if any(k in t.lower() for k in ["campbell", "mustang", "cu ", " vs "]) or i < 50:
        print(f"{i:3d}: {e.get('id')} | {t} | {e.get('duration')}s")

# 2. Check https://www.majestichoops.com
req = urllib.request.Request("https://www.majestichoops.com", headers={"User-Agent": "Mozilla/5.0"})
html = urllib.request.urlopen(req).read().decode("utf-8", errors="replace")
soup = BeautifulSoup(html, "html.parser")
print("\n=== https://www.majestichoops.com Links ===")
for a in soup.find_all("a", href=True):
    print(" ", a.get_text(" ", strip=True), "->", a["href"])
