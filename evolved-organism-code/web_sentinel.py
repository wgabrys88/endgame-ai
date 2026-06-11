
import urllib.request
import json
import time
import os
from datetime import datetime

class WebSentinel:
    def __init__(self, log_file="sentinel_log.txt"):
        self.log_file = log_file
        self.cache = {}

    def fetch(self, url="https://timeapi.io/api/Time/current/zone?timeZone=UTC"):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "endgame-ai-sentinel/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = resp.read().decode()
                self.cache[url] = {"data": data, "ts": datetime.now().isoformat()}
                self.log(f"FETCH OK: {url[:60]} -> {len(data)} bytes")
                return data
        except Exception as e:
            self.log(f"FETCH FAIL: {url[:60]} -> {e}")
            return None

    def get_headlines(self):
        # Use a public API for external data
        try:
            url = "https://hacker-news.firebaseio.com/v0/topstories.json"
            req = urllib.request.Request(url, headers={"User-Agent": "endgame-ai-sentinel/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                ids = json.loads(resp.read().decode())[:5]
            headlines = []
            for story_id in ids:
                item_url = f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json"
                req2 = urllib.request.Request(item_url, headers={"User-Agent": "endgame-ai-sentinel/1.0"})
                with urllib.request.urlopen(req2, timeout=5) as resp2:
                    item = json.loads(resp2.read().decode())
                    headlines.append(item.get("title", "untitled"))
            self.log(f"HEADLINES: fetched {len(headlines)} stories")
            return headlines
        except Exception as e:
            self.log(f"HEADLINES FAIL: {e}")
            return ["Could not fetch headlines"]

    def log(self, msg):
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] SENTINEL: {msg}"
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(line + "\n")
        print(line)

if __name__ == "__main__":
    s = WebSentinel()
    print("=== Web Sentinel Active ===")
    data = s.fetch()
    print(f"Time API: {data[:200] if data else 'failed'}")
    headlines = s.get_headlines()
    print(f"Headlines: {headlines}")
    # Write results for reactor integration
    with open("sentinel_output.json", "w") as f:
        json.dump({"time_data": data, "headlines": headlines, "ts": datetime.now().isoformat()}, f, indent=2)
    print("Sentinel output saved to sentinel_output.json")
