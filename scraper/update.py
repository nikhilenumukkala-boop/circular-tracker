"""Scrape AMFI/SEBI/RBI and merge new circulars into docs/data.json.

Append-only: existing circulars are never removed or modified, so history
accumulates in git. A source failing only records an error message — its
previously collected circulars stay untouched.
"""
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

DATA_PATH = os.environ.get(
    "DATA_JSON",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs", "data.json"),
)

EMPTY = {"last_updated": None, "errors": {}, "circulars": []}


def load_data(path=DATA_PATH):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return json.loads(json.dumps(EMPTY))


def save_data(data, path=DATA_PATH):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write("\n")


def merge(data, items, errors, now=None):
    """Merge scraped items into data in place. Returns number of new circulars.

    Dedup key is (source, url, title) — same as the old SQLite UNIQUE
    constraint — so re-running on unchanged sources adds nothing and
    first_seen of existing entries is preserved.
    """
    now = now or datetime.now(timezone.utc).isoformat()
    seen = {(c["source"], c["url"], c["title"]) for c in data["circulars"]}
    added = 0
    for it in items:
        title = (it.get("title") or "").strip()
        url = it.get("url")
        if not title or not url:
            continue
        key = (it["source"], url, title)
        if key in seen:
            continue
        seen.add(key)
        data["circulars"].append({
            "source": it["source"],
            "ref_no": it.get("ref_no"),
            "title": title,
            "url": url,
            "date": it.get("date"),
            "first_seen": now,
        })
        added += 1
    data["circulars"].sort(
        key=lambda c: ((c.get("date") or c["first_seen"][:10]), c["first_seen"]),
        reverse=True,
    )
    data["last_updated"] = now
    data["errors"] = errors
    return added


def main():
    from scrapers import scrape_all
    data = load_data()
    items, errors = scrape_all()
    added = merge(data, items, errors)
    save_data(data)
    print(f"scraped {len(items)} items, added {added} new "
          f"(total {len(data['circulars'])}); errors: {errors or 'none'}")


if __name__ == "__main__":
    main()
