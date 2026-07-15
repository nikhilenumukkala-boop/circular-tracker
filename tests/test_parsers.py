"""Offline parser tests using fixtures captured from the live sites (Jul 2026)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scraper"))
from bs4 import BeautifulSoup
import scrapers

HERE = os.path.dirname(__file__)

# Real row markup captured from amfiindia.com (Next.js/MUI div grid)
AMFI_FIXTURE = """
<html><body><div class="MuiBox-root css-1f8ksoa">
<div class="MuiBox-root css-gtmwth"><div class="MuiBox-root css-1o42u8j">Circular Reference</div><div class="MuiBox-root css-3sr3xb">Subject</div><div class="MuiBox-root css-1f3hanw">Date of Circular</div></div>
<div class="MuiBox-root css-gtmwth"><div class="MuiBox-root css-1o42u8j">AMFI/MFD-CIR/32/2025-26</div><div class="MuiBox-root css-3sr3xb"><div class="MuiBox-root css-1821gv5"><div class="MuiBox-root css-0"><a target="_blank" rel="noopener noreferrer" href="https://www.amfiindia.com/uploads/AMFI_Master_Cicular_for_MF_Ds_3c7f5ee44f.pdf"><span class="MuiTypography-root MuiTypography-body1 css-13so4bx">AMFI Master Circular for Mutual Fund Distributors</span></a></div></div></div><div class="MuiBox-root css-1f3hanw">14 Jan 2026</div></div>
<div class="MuiBox-root css-gtmwth"><div class="MuiBox-root css-1o42u8j">CIR/ARN-25/2023-24</div><div class="MuiBox-root css-3sr3xb"><div class="MuiBox-root css-1821gv5"><div class="MuiBox-root css-0"><a href="/Themes/Theme1/downloads/circulars/a.pdf"><span>ARN Circular no. 25 - Centralised Process for AUM Transfer</span></a></div><div class="MuiBox-root css-0"><a href="/Themes/Theme1/downloads/circulars/b.pdf"><span>Annexure 1a &amp; 1b - Sample of letter</span></a></div></div></div><div class="MuiBox-root css-1f3hanw">28 Mar 2024</div></div>
</div></body></html>
"""

# Real row markup captured from sebi.gov.in listing table
SEBI_FIXTURE = """
<html><body><table id="sample_1"><tbody>
<tr role="row" class="odd"><td>Jun 24, 2026</td><td><a href="https://www.sebi.gov.in/legal/circulars/jun-2026/ease-of-doing-business-relaxation_102385.html" class="points"> Ease of Doing Business - Relaxation in certification requirement</a></td></tr>
<tr role="row" class="even"><td>Jun 19, 2026</td><td><a href="/legal/circulars/jun-2026/clarification-early-pay-in_102229.html" class="points">Clarification with respect to applicability of the benefit of early pay-in</a></td></tr>
<tr><td>Jun 16, 2026</td><td><a href="https://www.sebi.gov.in/other/page.html">Not a circular link</a></td></tr>
</tbody></table></body></html>
"""


def test_amfi():
    orig = scrapers.requests.get
    class FakeResp:
        text = AMFI_FIXTURE
        def raise_for_status(self): pass
    scrapers.requests.get = lambda *a, **k: FakeResp()
    try:
        items = scrapers.scrape_amfi()
    finally:
        scrapers.requests.get = orig
    assert len(items) == 3, items
    assert items[0]["ref_no"] == "AMFI/MFD-CIR/32/2025-26"
    assert items[0]["date"] == "2026-01-14"
    assert items[0]["url"].endswith(".pdf")
    assert items[1]["date"] == "2024-03-28" and items[2]["date"] == "2024-03-28"
    assert items[2]["title"].startswith("Annexure 1a")
    assert items[1]["url"].startswith("https://www.amfiindia.com/")  # relative resolved
    print("AMFI parser OK:", len(items), "items")


def test_sebi():
    orig = scrapers.requests.Session
    class FakeResp:
        text = SEBI_FIXTURE
        def raise_for_status(self): pass
    class FakeSession:
        headers = {}
        def get(self, *a, **k): return FakeResp()
        def post(self, *a, **k): return FakeResp()
    scrapers.requests.Session = lambda: FakeSession()
    try:
        items = scrapers.scrape_sebi()
    finally:
        scrapers.requests.Session = orig
    assert len(items) == 2, items   # third row filtered (not /legal/circulars/)
    assert items[0]["date"] == "2026-06-24"
    assert items[1]["url"].startswith("https://www.sebi.gov.in/legal/circulars/")
    print("SEBI parser OK:", len(items), "items")


def test_rbi():
    xml_bytes = open(os.path.join(HERE, "rbi_rss_fixture.xml"), "rb").read()
    orig = scrapers.requests.get
    class FakeResp:
        content = xml_bytes
        def raise_for_status(self): pass
    scrapers.requests.get = lambda *a, **k: FakeResp()
    try:
        items = scrapers.scrape_rbi()
    finally:
        scrapers.requests.get = orig
    assert len(items) > 5, len(items)
    assert all(i["title"] and i["url"] for i in items)
    with_ref = [i for i in items if i["ref_no"]]
    with_date = [i for i in items if i["date"]]
    print(f"RBI parser OK: {len(items)} items, {len(with_ref)} with ref, {len(with_date)} with date")
    print("  sample:", items[0]["date"], "|", items[0]["ref_no"], "|", items[0]["title"][:60])


if __name__ == "__main__":
    test_amfi(); test_sebi(); test_rbi()
    print("ALL PARSER TESTS PASSED")
