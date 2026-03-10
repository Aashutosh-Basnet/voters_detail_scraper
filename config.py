from pathlib import Path

# URLs
BASE_URL    = "https://voterlist.election.gov.np"
INDEX_PROC  = f"{BASE_URL}/index_process.php"
VIEW_WARD   = f"{BASE_URL}/view_ward.php"

# Default Scraping Settings
DEFAULT_STATE    = 3
DEFAULT_DISTRICT = 17
DELAY_BETWEEN_REQUESTS = 1.5   # seconds
MAX_RETRIES            = 3
RETRY_BACKOFF          = 5     # seconds per retry

# File System
OUTPUT_DIR  = Path("output")
LOG_FILE    = Path("scraper.log")
CHECKPOINT  = Path("checkpoint.json")

# HTTP Headers
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

# Data Mappings
STATE_MAP = {
    1: "Koshi",
    2: "Madhesh",
    3: "Bagmati",
    4: "Gandaki",
    5: "Lumbini",
    6: "Karnali",
    7: "Sudurpashchim"
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
