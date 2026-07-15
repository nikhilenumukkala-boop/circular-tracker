"""One-time archive backfill: pull historical SEBI and RBI circulars into docs/data.json.

- SEBI: walks the Legal → Circulars listing pagination until an empty page.
- RBI: walks the NotificationUser.aspx archive month by month (one POST per
  month; the page is an ASP.NET form navigated via hdnYear/hdnMonth).
- AMFI needs no backfill — its circulars page already carries the full archive.

Run from GitHub Actions (SEBI blocks most residential/other IPs but serves
GitHub's), via the "Backfill archive" workflow. Safe to re-run: merging is
append-only with the same dedup as the 6-hourly update.
"""
import argparse
import re
import sys
import time
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from scrapers import HEADERS, scrape_sebi, _parse_date
from update import load_data, save_data, merge

RBI_ARCHIVE = "https://www.rbi.org.in/Scripts/NotificationUser.aspx"


def _rbi_hidden_fields(soup):
    return {i.get("name"): i.get("value", "")
            for i in soup.select("input[type=hidden]") if i.get("name")}


def parse_rbi_month(html):
    """Parse one month's listing: tables where a tableheader cell carries the
    date and following rows link each notification."""
    soup = BeautifulSoup(html, "lxml")
    items, date = [], None
    for table in soup.select("table.tablebg"):
        for tr in table.find_all("tr"):
            head = tr.find("td", class_="tableheader")
            if head is not None:
                date = _parse_date(head.get_text(" ", strip=True), ["%b %d, %Y"])
                continue
            a = tr.find("a", href=re.compile(r"NotificationUser\.aspx\?Id="))
            if a is None:
                continue
            title = a.get_text(" ", strip=True)
            if not title:
                continue
            items.append({
                "source": "RBI",
                "ref_no": None,
                "title": title,
                "url": urljoin(RBI_ARCHIVE, a["href"]),
                "date": date,
            })
    return items


def backfill_rbi(from_year, to_year=None, delay=1.0, log=print):
    now = datetime.now(timezone.utc)
    to_year = to_year or now.year
    session = requests.Session()
    session.headers.update(HEADERS)
    r = session.get(RBI_ARCHIVE, timeout=30)
    r.raise_for_status()
    form = _rbi_hidden_fields(BeautifulSoup(r.text, "lxml"))
    items = []
    for year in range(to_year, from_year - 1, -1):
        year_n = 0
        for month in range(1, 13):
            if year == now.year and month > now.month:
                continue
            time.sleep(delay)
            data = dict(form)
            data.update({"hdnYear": str(year), "hdnMonth": str(month),
                         "UsrFontCntr$btn": ""})
            try:
                r = session.post(RBI_ARCHIVE, data=data, timeout=30)
                r.raise_for_status()
            except requests.RequestException as e:
                log(f"RBI {year}-{month:02d}: request failed ({e}); skipping month")
                continue
            got = parse_rbi_month(r.text)
            year_n += len(got)
            items.extend(got)
            # keep the ASP.NET form state fresh for the next post
            form = _rbi_hidden_fields(BeautifulSoup(r.text, "lxml")) or form
        log(f"RBI {year}: {year_n} notifications")
    return items


def backfill_sebi(max_pages, delay=1.0, log=print):
    items = scrape_sebi(pages=max_pages, delay=delay)
    log(f"SEBI: {len(items)} circulars across up to {max_pages} pages")
    return items


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sebi-pages", type=int, default=0,
                    help="max SEBI listing pages to walk (0 = skip SEBI)")
    ap.add_argument("--rbi-from-year", type=int, default=0,
                    help="earliest RBI year to fetch (0 = skip RBI)")
    ap.add_argument("--delay", type=float, default=1.0,
                    help="seconds between requests")
    args = ap.parse_args()

    data = load_data()
    before = len(data["circulars"])
    items, errors = [], {}

    if args.sebi_pages:
        try:
            items += backfill_sebi(args.sebi_pages, args.delay)
        except Exception as e:
            errors["SEBI"] = f"backfill: {e}"
            print(f"SEBI backfill failed: {e}")
    if args.rbi_from_year:
        try:
            items += backfill_rbi(args.rbi_from_year, delay=args.delay)
        except Exception as e:
            errors["RBI"] = f"backfill: {e}"
            print(f"RBI backfill failed: {e}")

    # keep any existing error state for sources we did not touch
    merged_errors = dict(data.get("errors") or {})
    merged_errors.update(errors)
    added = merge(data, items, merged_errors)
    save_data(data)
    print(f"backfill scraped {len(items)}, added {added} new "
          f"({before} -> {len(data['circulars'])} total); errors: {errors or 'none'}")


if __name__ == "__main__":
    main()
