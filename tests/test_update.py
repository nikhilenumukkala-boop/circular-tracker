"""Tests for the data.json merge logic in scraper/update.py."""
import copy
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scraper"))
from update import merge, load_data, EMPTY

T1 = "2026-07-01T00:00:00+00:00"
T2 = "2026-07-02T00:00:00+00:00"

ITEMS = [
    {"source": "SEBI", "ref_no": None, "title": "Circular A", "url": "https://sebi/a", "date": "2026-06-30"},
    {"source": "RBI", "ref_no": "RBI/2026-27/1", "title": "Circular B", "url": "https://rbi/b", "date": "2026-06-29"},
    {"source": "AMFI", "ref_no": None, "title": "  Circular C  ", "url": "https://amfi/c", "date": None},
]


def fresh():
    return copy.deepcopy(EMPTY)


def test_first_merge_adds_all():
    data = fresh()
    added = merge(data, ITEMS, {}, now=T1)
    assert added == 3 and len(data["circulars"]) == 3
    assert all(c["first_seen"] == T1 for c in data["circulars"])
    assert data["last_updated"] == T1
    # titles are stripped
    assert any(c["title"] == "Circular C" for c in data["circulars"])
    print("first merge OK")


def test_rerun_adds_nothing_and_preserves_first_seen():
    data = fresh()
    merge(data, ITEMS, {}, now=T1)
    added = merge(data, ITEMS, {}, now=T2)
    assert added == 0, added
    assert len(data["circulars"]) == 3
    assert all(c["first_seen"] == T1 for c in data["circulars"]), "first_seen must be preserved"
    assert data["last_updated"] == T2, "last_updated must advance"
    print("re-run idempotency OK")


def test_new_item_gets_new_first_seen():
    data = fresh()
    merge(data, ITEMS, {}, now=T1)
    newer = ITEMS + [{"source": "SEBI", "ref_no": None, "title": "Circular D",
                      "url": "https://sebi/d", "date": "2026-07-01"}]
    added = merge(data, newer, {}, now=T2)
    assert added == 1
    d = next(c for c in data["circulars"] if c["title"] == "Circular D")
    assert d["first_seen"] == T2
    print("new item first_seen OK")


def test_failed_source_never_wipes_data():
    data = fresh()
    merge(data, ITEMS, {}, now=T1)
    # AMFI fails: scraper returns only SEBI+RBI items plus an error
    partial = [i for i in ITEMS if i["source"] != "AMFI"]
    added = merge(data, partial, {"AMFI": "HTTP 403"}, now=T2)
    assert added == 0
    amfi = [c for c in data["circulars"] if c["source"] == "AMFI"]
    assert len(amfi) == 1, "AMFI history must survive a failed scrape"
    assert data["errors"] == {"AMFI": "HTTP 403"}
    # next run recovers: error cleared
    merge(data, ITEMS, {}, now=T2)
    assert data["errors"] == {}
    print("failed-source safety OK")


def test_sorting_newest_first():
    data = fresh()
    merge(data, ITEMS, {}, now=T1)
    dates = [(c.get("date") or c["first_seen"][:10]) for c in data["circulars"]]
    assert dates == sorted(dates, reverse=True), dates
    print("sort order OK")


def test_skips_blank_items():
    data = fresh()
    junk = [{"source": "SEBI", "title": "  ", "url": "https://x"},
            {"source": "SEBI", "title": "ok", "url": None}]
    added = merge(data, junk, {}, now=T1)
    assert added == 0 and data["circulars"] == []
    print("blank-item guard OK")


def test_load_data_missing_file():
    data = load_data("/nonexistent/data.json")
    assert data == EMPTY and data is not EMPTY
    print("missing-file load OK")


if __name__ == "__main__":
    test_first_merge_adds_all()
    test_rerun_adds_nothing_and_preserves_first_seen()
    test_new_item_gets_new_first_seen()
    test_failed_source_never_wipes_data()
    test_sorting_newest_first()
    test_skips_blank_items()
    test_load_data_missing_file()
    print("ALL UPDATE TESTS PASSED")
