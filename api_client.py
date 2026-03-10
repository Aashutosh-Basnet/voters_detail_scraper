import time
import requests
import logging
from config import BASE_URL, INDEX_PROC, VIEW_WARD, HEADERS, MAX_RETRIES, RETRY_BACKOFF, DELAY_BETWEEN_REQUESTS
from parsers import parse_json_or_html_options

log = logging.getLogger(__name__)

class ElectionClient:
    def __init__(self, delay=DELAY_BETWEEN_REQUESTS):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.delay = delay

    def establish_session(self):
        log.info("Acquiring session cookie from %s …", BASE_URL)
        resp = self.session.get(BASE_URL, timeout=30)
        resp.raise_for_status()
        log.info("Session established. Cookies: %s", dict(self.session.cookies))

    def _post(self, url: str, data: dict, label: str = "") -> requests.Response:
        """POST with automatic retry."""
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                time.sleep(self.delay)
                resp = self.session.post(url, data=data, timeout=60)
                resp.raise_for_status()
                return resp
            except requests.RequestException as exc:
                log.warning("Attempt %d/%d failed for %s: %s", attempt, MAX_RETRIES, label or url, exc)
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_BACKOFF * attempt)
                else:
                    raise
        raise RuntimeError("Unreachable")

    def get_districts(self, state: int) -> list[dict]:
        resp = self._post(INDEX_PROC, {"state": state, "list_type": "district"}, f"state {state}")
        items = parse_json_or_html_options(resp.content)
        log.info("Districts found for state %d: %d", state, len(items))
        return items

    def get_municipalities(self, district: int) -> list[dict]:
        resp = self._post(INDEX_PROC, {"district": district, "list_type": "vdc"}, f"district {district}")
        items = parse_json_or_html_options(resp.content)
        return items

    def get_wards(self, vdc_id: int) -> list[dict]:
        resp = self._post(INDEX_PROC, {"vdc": vdc_id, "list_type": "ward"}, f"vdc {vdc_id}")
        return parse_json_or_html_options(resp.content)

    def get_reg_centres(self, vdc_id: int, ward: int) -> list[dict]:
        resp = self._post(INDEX_PROC, {"vdc": vdc_id, "ward": ward, "list_type": "reg_centre"}, f"vdc {vdc_id} wrd {ward}")
        return parse_json_or_html_options(resp.content)

    def get_voter_page(self, state: int, district: int, vdc_mun: int, ward: int, reg_centre: int) -> str:
        resp = self._post(VIEW_WARD, {
            "state": state, "district": district, "vdc_mun": vdc_mun, "ward": ward, "reg_centre": reg_centre
        }, f"voters vdc={vdc_mun} ward={ward} rc={reg_centre}")
        return resp.text
