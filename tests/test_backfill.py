"""Offline test for the RBI archive month parser (fixture: March 2024 listing
captured live from rbi.org.in)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scraper"))
from backfill import parse_rbi_month

HERE = os.path.dirname(__file__)


def test_parse_rbi_month():
    html = open(os.path.join(HERE, "rbi_month_fixture.html"), encoding="utf-8").read()
    items = parse_rbi_month(html)
    assert len(items) == 12, len(items)
    assert all(i["source"] == "RBI" for i in items)
    assert all(i["title"] and i["url"].startswith("https://www.rbi.org.in/Scripts/NotificationUser.aspx?Id=")
               for i in items)
    assert all(i["date"] and i["date"].startswith("2024-03") for i in items), \
        [i["date"] for i in items]
    titles = [i["title"] for i in items]
    assert "Currency Chests (CCs) operations on March 31, 2024" in titles
    # several notifications share one date header row
    assert len({i["date"] for i in items}) < len(items)
    print(f"RBI month parser OK: {len(items)} items, "
          f"{len({i['date'] for i in items})} distinct dates")


if __name__ == "__main__":
    test_parse_rbi_month()
    print("ALL BACKFILL TESTS PASSED")
