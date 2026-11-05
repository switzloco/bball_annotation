import sys
import urllib.request
from bs4 import BeautifulSoup

sys.stdout.reconfigure(encoding="utf-8")

urls = [
    "https://www.recleague.net/leagues/majestichoops/teams/431571",
    "https://www.recleague.net/sites/majestichoops/teams/431571",
    "https://www.recleague.net/leagues/majestichoops",
    "https://www.recleague.net/organizations/38805",
    "https://www.recleague.net/organizations/38805/players/404843",
]

for url in urls:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        html = urllib.request.urlopen(req).read().decode("utf-8", errors="replace")
        soup = BeautifulSoup(html, "html.parser")
        print(f"\n==================== {url} ====================")
        for a in soup.find_all("a", href=True):
            href = a["href"]
            txt = " ".join(a.get_text(" ", strip=True).split())
            if any(k in href.lower() for k in ["youtube", "youtu.be", "games", "seasons", "leagues", "schedule", "standings", "videos"]) or any(k in txt.lower() for k in ["mustang", "campbell", "oct", "nov", "video", "youtube"]):
                print(f"  A: {txt[:90]} -> {href}")
    except Exception as e:
        print(f"Error {url}: {e}")
