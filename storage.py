import csv
import json
import logging
from config import OUTPUT_DIR, CHECKPOINT, CSV_FIELDS

log = logging.getLogger(__name__)

def load_checkpoint() -> set[str]:
    """Return a set of already-scraped keys: 'vdc_ward_rc'."""
    if not CHECKPOINT.exists():
        return set()
    try:
        with open(CHECKPOINT, encoding="utf-8") as f:
            return set(json.load(f))
    except Exception:
        return set()

def save_checkpoint(done: set[str]):
    with open(CHECKPOINT, "w", encoding="utf-8") as f:
        json.dump(list(done), f, ensure_ascii=False, indent=2)

def is_district_completed(district_id: int, district_label: str) -> bool:
    """Check if the district CSV already exists."""
    if not OUTPUT_DIR.exists():
        return False
    
    pattern_id = f"district{district_id}.csv"
    safe_label = district_label.replace(" ", "_").replace("/", "-")
    
    for file in OUTPUT_DIR.glob("*.csv"):
        if pattern_id in file.name or safe_label in file.name:
            return True
    return False

def get_csv_writer(district_name: str, district_id: int):
    """Setup CSV writer for a specific district."""
    OUTPUT_DIR.mkdir(exist_ok=True)
    safe_name = district_name.replace(" ", "_").replace("/", "-")
    path = OUTPUT_DIR / f"voters_{safe_name}_district{district_id}.csv"
    exists = path.exists()
    fp = open(path, "a", newline="", encoding="utf-8-sig")
    writer = csv.DictWriter(fp, fieldnames=CSV_FIELDS, extrasaction="ignore")
    if not exists:
        writer.writeheader()
    return fp, writer, path
