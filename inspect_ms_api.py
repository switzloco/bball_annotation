import sys
import re
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

for path in ["/", "/js/ms-league.js?v=4"]:
    url = "https://mh.majesticstats.com" + path
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    txt = urllib.request.urlopen(req).read().decode("utf-8", errors="replace")
    print(f"=== {url} (len={len(txt)}) ===")
    if path.endswith(".js?v=4"):
        print(txt[:4000])
    else:
        for m in re.finditer(r"fetch\([^)]+\)|/api/[a-zA-Z0-9_/\-\$\{\}\?=&]+", txt):
            print("  MATCH:", m.group(0))
