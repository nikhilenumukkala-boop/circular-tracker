# Circular Tracker — SEBI · RBI · AMFI

One place to track and search new circulars from SEBI, RBI and AMFI.
**No server needed**: GitHub Actions scrapes every 6 hours and commits new
circulars to `docs/data.json` (history persists forever in git), and GitHub
Pages serves the static UI.

## How it works

- **Scrapes** three sources every 6 hours via GitHub Actions:
  - SEBI: Legal → Circulars listing (latest page)
  - RBI: official notifications RSS feed
  - AMFI: distributor circulars page
- **Stores** everything append-only in [docs/data.json](docs/data.json) —
  each run merges new circulars in (dedup on source+url+title), never
  deletes, and preserves `first_seen`. One source failing never touches
  another's data; the site shows a warning banner instead.
- **UI** ([docs/index.html](docs/index.html)): 3-column view, client-side
  search, "N new since your last visit" banner + NEW badges (per-browser
  via localStorage).

## Deploy (one time, ~5 min)

1. Create a **public** repo named `circular-tracker` on github.com
2. Push this folder:

   ```bash
   git init && git add -A && git commit -m "Circular tracker"
   git branch -M main
   git remote add origin https://github.com/<YOUR-USERNAME>/circular-tracker.git
   git push -u origin main
   ```

3. **Settings → Pages** → Source: *Deploy from a branch* → `main` / `/docs`
4. **Actions** tab → *Update circulars* → *Run workflow* (first run may need
   you to enable workflows)

Site: `https://<your-username>.github.io/circular-tracker/`

## Tests (offline, no network)

```bash
pip install -r requirements.txt
python3 tests/test_parsers.py   # scrapers against captured fixtures
python3 tests/test_update.py    # data.json merge logic
```

## Notes

- SEBI only exposes the latest listing page (~25 circulars) per fetch —
  plenty for change detection; history accumulates in git from day one.
- RBI RSS carries the latest entries only; same accumulation model.
- If SEBI/AMFI ever block GitHub's datacenter IPs, the Actions log will show
  the error and the site keeps serving previously collected data.
