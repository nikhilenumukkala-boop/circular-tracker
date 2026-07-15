"""Scrapers for AMFI, SEBI and RBI circulars.

Each scraper returns a list of dicts:
    {source, ref_no, title, url, date}  (date = ISO yyyy-mm-dd or None)
"""
import re
import logging
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

log = logging.getLogger("scrapers")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

AMFI_URL = "https://www.amfiindia.com/distributor/amfi-circulars"
SEBI_URL = "https://www.sebi.gov.in/sebiweb/home/HomeAction.do?doListing=yes&sid=1&ssid=7&smid=0"
RBI_RSS = "https://www.rbi.org.in/notifications_rss.xml"
RBI_PRESS_RSS = "https://www.rbi.org.in/pressreleases_rss.xml"


def _parse_date(text, fmts):
    text = (text or "").strip()
    for fmt in fmts:
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


# ---------------------------------------------------------------- AMFI
AMFI_REF_RE = re.compile(r"^(?:AMFI|CIR|\d+)[\w/ .-]*$")
AMFI_DATE_FMTS = ["%d %b %Y", "%d-%b-%Y", "%d %B %Y"]

def _amfi_row_items(ref_text, link_cell, date_text):
    """Extract circular entries from one row (ref | subject-links | date)."""
    out = []
    ref = (ref_text or "").strip()
    date = _parse_date(date_text, AMFI_DATE_FMTS)
    for a in link_cell.find_all("a", href=True):
        title = a.get_text(" ", strip=True)
        if title:
            out.append({
                "source": "AMFI",
                "ref_no": ref if AMFI_REF_RE.match(ref) else None,
                "title": title,
                "url": urljoin(AMFI_URL, a["href"]),
                "date": date,
            })
    return out


def scrape_amfi():
    r = requests.get(AMFI_URL, headers=HEADERS, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")
    items = []

    # Layout A: classic <table> rows (ref | subject | date)
    for row in soup.select("table tr"):
        cells = row.find_all(["td", "th"])
        if len(cells) >= 3:
            items.extend(_amfi_row_items(
                cells[0].get_text(" ", strip=True), cells[1],
                cells[-1].get_text(" ", strip=True)))

    # Layout B (current site, Next.js/MUI): row = <div> with exactly 3 child
    # divs where the last one is a parseable date and the middle holds links.
    if not items:
        for div in soup.find_all("div"):
            kids = div.find_all(recursive=False)
            if len(kids) != 3 or kids[1].name != "div":
                continue
            date_text = kids[2].get_text(" ", strip=True)
            if not _parse_date(date_text, AMFI_DATE_FMTS):
                continue
            items.extend(_amfi_row_items(
                kids[0].get_text(" ", strip=True), kids[1], date_text))

    # Layout C fallback: any pdf link on the page
    if not items:
        log.warning("AMFI structured parse found nothing; falling back to pdf links")
        for a in soup.find_all("a", href=re.compile(r"\.pdf", re.I)):
            title = a.get_text(" ", strip=True)
            if title:
                items.append({"source": "AMFI", "ref_no": None, "title": title,
                              "url": urljoin(AMFI_URL, a["href"]), "date": None})
    return items


# ---------------------------------------------------------------- SEBI
def scrape_sebi(pages=1, delay=0):
    """Scrape SEBI circulars listing. pages>1 walks pagination via POST."""
    session = requests.Session()
    session.headers.update(HEADERS)
    items, seen = [], set()
    for page in range(pages):
        if delay and page:
            time.sleep(delay)
        err = None
        for attempt in range(3):
            try:
                if page == 0:
                    r = session.get(SEBI_URL, timeout=30)
                else:
                    r = session.post(
                        "https://www.sebi.gov.in/sebiweb/home/HomeAction.do?doListing=yes&sid=1&ssid=7&smid=0",
                        data={"nextValue": "1", "next": "n", "search": "", "fromDate": "", "toDate": "",
                              "fromYear": "", "toYear": "", "deptId": "-1", "sid": "1", "ssid": "7",
                              "smid": "0", "ssSubSectionId": "7", "intmId": "-1", "sText": "Legal",
                              "ssText": "Circulars", "smText": "", "doDirect": str(page)},
                        timeout=30)
                r.raise_for_status()
                err = None
                break
            except Exception as e:
                err = e
                time.sleep(15 * (attempt + 1))
        if err is not None:
            if not items:
                raise err  # nothing salvaged — let callers record the failure
            log.warning("SEBI page %d failed after retries (%s); keeping %d items", page, err, len(items))
            break
        soup = BeautifulSoup(r.text, "lxml")
        found = 0
        for row in soup.select("table tr"):
            cells = row.find_all("td")
            if len(cells) < 2:
                continue
            a = cells[1].find("a", href=True)
            if not a:
                continue
            url = urljoin("https://www.sebi.gov.in/", a["href"])
            if not re.search(r"/legal/circulars/", url):
                continue
            if url in seen:
                continue
            seen.add(url)
            items.append({
                "source": "SEBI",
                "ref_no": None,
                "title": a.get_text(" ", strip=True),
                "url": url,
                "date": _parse_date(cells[0].get_text(" ", strip=True), ["%b %d, %Y", "%d-%b-%Y"]),
            })
            found += 1
        if found == 0:
            break
    return items


# ---------------------------------------------------------------- RBI
RBI_REF_RE = re.compile(r"(RBI/[\w/.-]+)")
RBI_DATE_RE = re.compile(r"([A-Z][a-z]+ \d{1,2}, \d{4})")

def _scrape_rbi_feed(url, source="RBI"):
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    root = ET.fromstring(r.content)
    items = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        desc = item.findtext("description") or ""
        pub = (item.findtext("pubDate") or "").strip()
        if not title or not link:
            continue
        ref = None
        m = RBI_REF_RE.search(desc)
        if m:
            ref = m.group(1)
        date = _parse_date(pub, ["%a, %d %b %Y %H:%M:%S %Z", "%a, %d %b %Y %H:%M:%S %z"])
        if not date:
            m = RBI_DATE_RE.search(desc)
            if m:
                date = _parse_date(m.group(1), ["%B %d, %Y"])
        items.append({"source": source, "ref_no": ref, "title": title, "url": link, "date": date})
    return items


def scrape_rbi():
    return _scrape_rbi_feed(RBI_RSS)


# ---------------------------------------------------------------- All
SCRAPERS = {"AMFI": scrape_amfi, "SEBI": scrape_sebi, "RBI": scrape_rbi}

def scrape_all():
    results, errors = [], {}
    for name, fn in SCRAPERS.items():
        try:
            got = fn()
            log.info("%s: %d items", name, len(got))
            results.extend(got)
        except Exception as e:  # keep other sources working
            log.exception("%s scrape failed", name)
            errors[name] = str(e)
    return results, errors
