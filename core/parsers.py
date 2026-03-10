import json
import logging
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

def parse_json_or_html_options(resp_content: bytes) -> list[dict]:
    """Parse JSON or HTML <option> tags from a response."""
    # Strip BOM (\xef\xbb\xbf) and leading/trailing whitespace
    text = resp_content.decode("utf-8-sig").strip()
    
    # Primary path: JSON envelope wrapping HTML option tags
    try:
        data = json.loads(text)
        if isinstance(data, dict) and "result" in data:
            return _parse_html_options(data["result"])
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
    """Parse the voter table from the EC website."""
    soup = BeautifulSoup(html, "lxml")
    table = soup.find("table", id=lambda x: x and "tbl_data" in x)
    if not table:
        table = soup.find("table", class_=lambda x: x and "bbvrs_data" in (x or ""))
    if not table:
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
