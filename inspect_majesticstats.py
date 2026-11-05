import sys
import urllib.request
from bs4 import BeautifulSoup

sys.stdout.reconfigure(encoding="utf-8")

url = "https://mh.majesticstats.com/"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
html = urllib.request.urlopen(req).read().decode("utf-8", errors="replace")
print("HTML len:", len(html))
print(html[:3000])
soup = BeautifulSoup(html, "html.parser")
for a in soup.find_all("a", href=True):
    print("LINK:", a.get_text(" ", strip=True), "->", a["href"])
for s in soup.find_all("script"):
    if s.get("src"):
        print("SCRIPT SRC:", s["src"])
    elif s.string and len(s.string) > 20:
        print("INLINE SCRIPT:", s.string[:500])
