"""
Nepal Election Commission - Voter List Scraper
==============================================
Scrapes voter data from https://voterlist.election.gov.np/

API Flow:
  1. GET  /           -> get session cookie (PHPSESSID)
  2. POST /index_process.php  state=3&list_type=district      -> districts
  3. POST /index_process.php  district=17&list_type=vdc       -> municipalities
  4. POST /index_process.php  vdc=<id>&list_type=ward         -> wards
  5. POST /index_process.php  vdc=<id>&ward=<n>&list_type=reg_centre -> reg centres
  6. POST /view_ward.php      full params                     -> voter HTML table

Usage:
    python scraper.py                     # scrape all of Dolakha
    python scraper.py --district 17       # same (explicit district id)
    python scraper.py --vdc 5176          # single municipality
    python scraper.py --resume            # resume from checkpoint
"""

import argparse
import csv
import json
import logging
import os
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

# ─── Configuration ────────────────────────────────────────────────────────────

BASE_URL    = "https://voterlist.election.gov.np"
INDEX_PROC  = f"{BASE_URL}/index_process.php"
VIEW_WARD   = f"{BASE_URL}/view_ward.php"

# Dolakha = state 3, district 17
DEFAULT_STATE    = 3
DEFAULT_DISTRICT = 17

DELAY_BETWEEN_REQUESTS = 1.5   # seconds — be respectful to the server
MAX_RETRIES            = 3
RETRY_BACKOFF          = 5     # seconds per retry

OUTPUT_DIR  = Path("output")
LOG_FILE    = "scraper.log"
CHECKPOINT  = "checkpoint.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,ne;q=0.8",
    "Origin":          BASE_URL,
    "Referer":         BASE_URL + "/",
}

CSV_FIELDS = [
    "state", "state_name",
    "district", "district_name",
    "vdc_mun_id", "vdc_mun_name",
    "ward_no",
    "reg_centre_id", "reg_centre_name",
    "serial_no", "voter_no", "voter_name",
    "age", "gender", "spouse_name", "parents_name",
]

# ─── Logging ──────────────────────────────────────────────────────────────────

def setup_logging():
    fmt = "%(asctime)s [%(levelname)s] %(message)s"
    logging.basicConfig(
        level=logging.INFO,
        format=fmt,
        handlers=[
            logging.FileHandler(LOG_FILE, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )

log = logging.getLogger(__name__)

# ─── Session helpers ──────────────────────────────────────────────────────────

def make_session() -> requests.Session:
    """Create a session and acquire a valid PHPSESSID."""
    session = requests.Session()
    session.headers.update(HEADERS)
    log.info("Acquiring session cookie from %s …", BASE_URL)
    resp = session.get(BASE_URL, timeout=30)
    resp.raise_for_status()
    log.info("Session established. Cookies: %s", dict(session.cookies))
    return session


def post_with_retry(session: requests.Session, url: str, data: dict, label: str = "") -> requests.Response:
    """POST with automatic retry + back-off on transient failures."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            time.sleep(DELAY_BETWEEN_REQUESTS)
            resp = session.post(url, data=data, timeout=60)
            resp.raise_for_status()
            return resp
        except requests.RequestException as exc:
            log.warning(
                "Attempt %d/%d failed for %s%s: %s",
                attempt, MAX_RETRIES, label or url, f" ({label})" if label else "", exc,
            )
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF * attempt)
            else:
                raise
    raise RuntimeError("Unreachable")  # just for type checkers

# ─── API wrappers ─────────────────────────────────────────────────────────────

def get_districts(session: requests.Session, state: int) -> list[dict]:
    resp = post_with_retry(session, INDEX_PROC, {"state": state, "list_type": "district"}, "districts")
    items = parse_json_or_html_options(resp)
    log.info("Districts found: %d", len(items))
    return items


def get_municipalities(session: requests.Session, district: int) -> list[dict]:
    resp = post_with_retry(session, INDEX_PROC, {"district": district, "list_type": "vdc"}, "municipalities")
    items = parse_json_or_html_options(resp)
    log.info("  Municipalities in district %s: %d", district, len(items))
    return items


def get_wards(session: requests.Session, vdc_id: int) -> list[dict]:
    resp = post_with_retry(session, INDEX_PROC, {"vdc": vdc_id, "list_type": "ward"}, f"wards vdc={vdc_id}")
    items = parse_json_or_html_options(resp)
    log.debug("    Wards in vdc %s: %s", vdc_id, [i["value"] for i in items])
    return items


def get_reg_centres(session: requests.Session, vdc_id: int, ward: int) -> list[dict]:
    resp = post_with_retry(
        session, INDEX_PROC,
        {"vdc": vdc_id, "ward": ward, "list_type": "reg_centre"},
        f"reg_centres vdc={vdc_id} ward={ward}",
    )
    items = parse_json_or_html_options(resp)
    log.debug("      RegCentres vdc=%s ward=%s: %s", vdc_id, ward, [i["value"] for i in items])
    return items


def get_voter_page(
    session: requests.Session,
    state: int, district: int,
    vdc_mun: int, ward: int, reg_centre: int,
) -> str:
    resp = post_with_retry(
        session, VIEW_WARD,
        {
            "state":      state,
            "district":   district,
            "vdc_mun":    vdc_mun,
            "ward":       ward,
            "reg_centre": reg_centre,
        },
        f"voters vdc={vdc_mun} ward={ward} rc={reg_centre}",
    )
    return resp.text

# ─── Parsers ─────────────────────────────────────────────────────────────────

def parse_json_or_html_options(resp: requests.Response) -> list[dict]:
    """
    The index_process.php endpoint returns:
        - UTF-8 BOM (\xef\xbb\xbf) + \r\n\r\n prefix + JSON
        - JSON structure: {"status": "1", "result": "<option ...>...</option>"}
    We strip the BOM/whitespace, parse JSON, then parse inner HTML options.
    """
    # Strip BOM (\xef\xbb\xbf) and leading/trailing whitespace
    text = resp.content.decode("utf-8-sig").strip()
    
    # Primary path: JSON envelope wrapping HTML option tags
    try:
        data = json.loads(text)
        if isinstance(data, dict) and "result" in data:
            html_fragment = data["result"]
            return _parse_html_options(html_fragment)
        # Rare: plain JSON array [{"id":…,"name":…}, …]
        if isinstance(data, list):
            result = []
            for item in data:
                val  = str(item.get("id") or item.get("value") or item.get("vdc_id") or "")
                name = str(item.get("name") or item.get("text") or item.get("label") or "")
                if val and val not in ("0", ""):
                    result.append({"value": val, "label": name})
            return result
    except (json.JSONDecodeError, AttributeError):
        pass

    # Fallback: plain HTML <option> tags
    items = _parse_html_options(text)
    if not items:
        log.debug("Unparseable response (first 500 chars): %s", text[:500])
    return items


def _parse_html_options(html_fragment: str) -> list[dict]:
    """Extract (value, label) pairs from an HTML string of <option> tags."""
    soup = BeautifulSoup(html_fragment, "lxml")
    result = []
    for opt in soup.find_all("option"):
        val   = opt.get("value", "").strip()
        label = opt.get_text(strip=True)
        if val and val not in ("0", ""):   # skip placeholder options
            result.append({"value": val, "label": label})
    return result


def parse_voter_table(html: str) -> list[dict]:
    """Parse the tbody of #tbl_data from view_ward.php response."""
    soup = BeautifulSoup(html, "lxml")
    
    # The table has id="tbl_data " (note trailing space in source)
    table = soup.find("table", id=lambda x: x and "tbl_data" in x)
    if not table:
        # Try any table with thead/tbody
        table = soup.find("table", class_=lambda x: x and "bbvrs_data" in (x or ""))
    if not table:
        log.debug("No voter table found in response.")
        return []

    rows = []
    tbody = table.find("tbody")
    if not tbody:
        return []
    
    for tr in tbody.find_all("tr"):
        cells = tr.find_all("td")
        if len(cells) < 7:
            continue
        rows.append({
            "serial_no":    cells[0].get_text(strip=True),
            "voter_no":     cells[1].get_text(strip=True),
            "voter_name":   cells[2].get_text(strip=True),
            "age":          cells[3].get_text(strip=True),
            "gender":       cells[4].get_text(strip=True),
            "spouse_name":  cells[5].get_text(strip=True),
            "parents_name": cells[6].get_text(strip=True),
        })
    return rows

# ─── Checkpoint ───────────────────────────────────────────────────────────────

def load_checkpoint() -> set[str]:
    """Return a set of already-scraped keys: 'vdc_ward_rc'."""
    if not Path(CHECKPOINT).exists():
        return set()
    with open(CHECKPOINT, encoding="utf-8") as f:
        return set(json.load(f))


def save_checkpoint(done: set[str]):
    with open(CHECKPOINT, "w", encoding="utf-8") as f:
        json.dump(list(done), f, ensure_ascii=False, indent=2)

# ─── CSV output ───────────────────────────────────────────────────────────────

def get_csv_writer(district_name: str):
    OUTPUT_DIR.mkdir(exist_ok=True)
    safe_name = district_name.replace(" ", "_").replace("/", "-")
    path = OUTPUT_DIR / f"voters_{safe_name}_district{DEFAULT_DISTRICT}.csv"
    exists = path.exists()
    fp = open(path, "a", newline="", encoding="utf-8-sig")  # utf-8-sig for Excel compatibility
    writer = csv.DictWriter(fp, fieldnames=CSV_FIELDS, extrasaction="ignore")
    if not exists:
        writer.writeheader()
    return fp, writer, path

# ─── Core scraping logic ──────────────────────────────────────────────────────

def scrape_district(
    session: requests.Session,
    state: int,
    district: int,
    vdc_filter: int | None = None,
    resume: bool = False,
):
    done_keys = load_checkpoint() if resume else set()

    # Get district name
    districts = get_districts(session, state)
    district_info = next(
        (d for d in districts if d["value"] == str(district)),
        {"value": str(district), "label": f"District-{district}"},
    )
    district_name = district_info["label"]
    log.info("=" * 60)
    log.info("Scraping district: %s (id=%s)", district_name, district)
    log.info("=" * 60)

    fp, writer, csv_path = get_csv_writer(district_name)
    log.info("Output CSV: %s", csv_path)

    municipalities = get_municipalities(session, district)
    if vdc_filter:
        municipalities = [m for m in municipalities if m["value"] == str(vdc_filter)]
        log.info("Filtered to VDC %s: %s", vdc_filter, municipalities)

    total_voters = 0
    total_reg_centres = 0

    try:
        for mun in tqdm(municipalities, desc="Municipalities", unit="mun", position=0):
            mun_id   = int(mun["value"])
            mun_name = mun["label"]
            log.info("  ▶ Municipality: %s (%s)", mun_name, mun_id)

            wards = get_wards(session, mun_id)
            if not wards:
                log.warning("    No wards found for %s", mun_name)
                continue

            for ward in tqdm(wards, desc=f"  {mun_name[:20]}", unit="ward", position=1, leave=False):
                ward_no = ward["value"]

                reg_centres = get_reg_centres(session, mun_id, ward_no)
                if not reg_centres:
                    log.warning("    No reg centres for ward %s", ward_no)
                    continue

                for rc in reg_centres:
                    rc_id   = rc["value"]
                    rc_name = rc["label"]
                    key     = f"{mun_id}_{ward_no}_{rc_id}"

                    if key in done_keys:
                        log.debug("    [SKIP] Already done: %s", key)
                        continue

                    log.info(
                        "    Ward %-4s | RegCentre %-6s | %s",
                        ward_no, rc_id, rc_name,
                    )

                    try:
                        html = get_voter_page(
                            session, state, district, mun_id, ward_no, rc_id
                        )
                        voters = parse_voter_table(html)
                        log.info(
                            "      → %d voters", len(voters)
                        )

                        for v in voters:
                            writer.writerow({
                                **v,
                                "state":          state,
                                "state_name":     "बागमती प्रदेश",
                                "district":       district,
                                "district_name":  district_name,
                                "vdc_mun_id":     mun_id,
                                "vdc_mun_name":   mun_name,
                                "ward_no":        ward_no,
                                "reg_centre_id":  rc_id,
                                "reg_centre_name": rc_name,
                            })
                        fp.flush()

                        total_voters     += len(voters)
                        total_reg_centres += 1
                        done_keys.add(key)
                        save_checkpoint(done_keys)

                    except Exception as exc:
                        log.error("    ERROR processing %s: %s", key, exc, exc_info=True)
                        # Continue with next reg centre instead of aborting
                        continue

    finally:
        fp.close()

    log.info("=" * 60)
    log.info("DONE. Total voters: %d  |  Reg centres scraped: %d", total_voters, total_reg_centres)
    log.info("Output: %s", csv_path)
    log.info("=" * 60)

# ─── Entry point ──────────────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description="Nepal Voter List Scraper — Election Commission Nepal",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--state",    type=int, default=DEFAULT_STATE,    help="Province/State number (default: 3)")
    parser.add_argument("--district", type=int, default=DEFAULT_DISTRICT, help="District number   (default: 17 = Dolakha)")
    parser.add_argument("--vdc",      type=int, default=None,             help="Scrape only this municipality ID")
    parser.add_argument("--resume",   action="store_true",                help="Resume from checkpoint (skip already-done entries)")
    parser.add_argument("--delay",    type=float, default=DELAY_BETWEEN_REQUESTS,
                        help=f"Seconds between requests (default: {DELAY_BETWEEN_REQUESTS})")
    return parser.parse_args()


def main():
    args = parse_args()
    global DELAY_BETWEEN_REQUESTS
    DELAY_BETWEEN_REQUESTS = args.delay

    setup_logging()
    log.info("Nepal Voter List Scraper starting")
    log.info("Target: state=%d, district=%d%s",
             args.state, args.district,
             f", vdc={args.vdc}" if args.vdc else " (all municipalities)")

    session = make_session()

    try:
        scrape_district(
            session,
            state    = args.state,
            district = args.district,
            vdc_filter = args.vdc,
            resume   = args.resume,
        )
    except KeyboardInterrupt:
        log.info("Interrupted by user. Checkpoint saved — run with --resume to continue.")
        sys.exit(0)
    except Exception as exc:
        log.critical("Fatal error: %s", exc, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
