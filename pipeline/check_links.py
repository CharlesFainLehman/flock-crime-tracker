"""Link-rot audit: report rows whose source_url (and all additional_sources)
are unreachable. Read-only; prints a table and writes data/link_report.json.
Run occasionally: python pipeline/check_links.py
"""

import concurrent.futures as cf
import json
import subprocess

from config import DATA_DIR
from store import load_stories

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/126.0 Safari/537.36"


def status(url: str) -> str:
    try:
        return subprocess.run(
            ["curl", "-sIL", "-A", UA, "--max-time", "20", "-o", "/dev/null", "-w", "%{http_code}", url],
            capture_output=True, text=True, timeout=30).stdout.strip() or "ERR"
    except Exception:
        return "ERR"


def main() -> None:
    stories = load_stories()
    def check(r):
        urls = [r["source_url"]] + [u for u in r.get("additional_sources", "").split() if u]
        return r["id"], [(u, status(u)) for u in urls]
    with cf.ThreadPoolExecutor(8) as ex:
        results = list(ex.map(check, stories))
    dead, blocked = [], []
    for rid, codes in results:
        if any(c.startswith("2") or c.startswith("3") for _, c in codes):
            continue
        if any(c in ("403", "429", "ERR") for _, c in codes):
            blocked.append((rid, codes))
        else:
            dead.append((rid, codes))
    print(f"{len(stories)} rows checked: {len(dead)} all-dead (404/410), {len(blocked)} bot-blocked/unreachable")
    for rid, codes in dead:
        print(f"  DEAD {rid}: {codes[0][0]}")
    json.dump({"dead": dead, "blocked": blocked}, open(DATA_DIR / "link_report.json", "w"), indent=1)


if __name__ == "__main__":
    main()
