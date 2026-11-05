import sys
import urllib.request
from bs4 import BeautifulSoup

sys.stdout.reconfigure(encoding="utf-8")

urls = [
    "https://www.recleague.net/leagues/majestichoops/posts/80454",
    "https://www.recleague.net/leagues/majestichoops/about",
    "https://www.recleague.net/leagues/majestichoops/teams/431571/schedule",
    "https://www.recleague.net/leagues/91937/teams/419266/schedule",
    "https://www.recleague.net/leagues/88571/teams/404980/schedule",
    "https://www.recleague.net/leagues/85790/teams/393302/schedule",
]

for url in urls:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        html = urllib.request.urlopen(req).read().decode("utf-8", errors="replace")
        soup = BeautifulSoup(html, "html.parser")
        print(f"\n==================== {url} ====================")
        if "posts" in url or "about" in url:
            print(soup.get_text(" ", strip=True)[:1500])
            for a in soup.find_all("a", href=True):
                if "http" in a["href"]:
                    print("  EXT LINK:", a.get_text(strip=True), "->", a["href"])
        else:
            for tr in soup.find_all("tr"):
                row_txt = " | ".join(" ".join(td.get_text(" ", strip=True).split()) for td in tr.find_all(["th", "td"]))
                links = [a["href"] for a in tr.find_all("a", href=True)]
                if row_txt:
                    print(f"  ROW: {row_txt} -> {links}")
    except Exception as e:
        print(f"Error {url}: {e}")
