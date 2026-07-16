"""Offline tests for the archive backfill parsers (fixtures captured live)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scraper"))
from backfill import parse_rbi_month, parse_sebi_detail

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


def test_parse_sebi_detail():
    html = open(os.path.join(HERE, "sebi_detail_fixture.html"), encoding="utf-8").read()
    url = "https://www.sebi.gov.in/legal/circulars/apr-1992/registration-of-brokers_19382.html"
    it = parse_sebi_detail(html, url)
    assert it["title"] == "Registration of brokers", it["title"]
    assert it["date"] == "1992-04-10", it["date"]
    assert it["source"] == "SEBI" and it["url"] == url
    print("SEBI detail parser OK:", it["date"], "|", it["title"])


if __name__ == "__main__":
    test_parse_rbi_month()
    test_parse_sebi_detail()
    print("ALL BACKFILL TESTS PASSED")
