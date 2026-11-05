import sys
import json
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

def get_json(path):
    url = "https://mh.majesticstats.com" + path
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return json.loads(urllib.request.urlopen(req).read().decode("utf-8"))

print("=== SEASONS ===")
print(json.dumps(get_json("/api/games/seasons"), indent=2))

print("\n=== SEARCH CAMPBELL ===")
search_res = get_json("/api/search?q=Campbell")
print(json.dumps(search_res, indent=2))
