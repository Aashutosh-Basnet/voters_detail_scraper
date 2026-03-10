import sys
import argparse
import logging
from config import LOG_FILE, DEFAULT_STATE, DEFAULT_DISTRICT, DELAY_BETWEEN_REQUESTS
from api_client import ElectionClient
from engine import scrape_district, scrape_all

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

def parse_args():
    parser = argparse.ArgumentParser(description="Nepal Voter List Scraper")
    parser.add_argument("--state", type=int, default=DEFAULT_STATE)
    parser.add_argument("--district", type=int, default=DEFAULT_DISTRICT)
    parser.add_argument("--vdc", type=int, default=None)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--delay", type=float, default=DELAY_BETWEEN_REQUESTS)
    parser.add_argument("--all", action="store_true")
    return parser.parse_args()

def main():
    args = parse_args()
    setup_logging()
    log = logging.getLogger(__name__)
    log.info("Nepal Voter List Scraper Refactored Version starting")
    
    client = ElectionClient(delay=args.delay)
    client.establish_session()

    try:
        is_default = (args.state == DEFAULT_STATE and args.district == DEFAULT_DISTRICT and not args.vdc)
        if args.all or is_default:
            log.info("Starting bulk scrape mode")
            scrape_all(client, resume=args.resume)
        else:
            log.info("Target: state=%d, district=%d%s", args.state, args.district, f", vdc={args.vdc}" if args.vdc else "")
            scrape_district(client, args.state, args.district, vdc_filter=args.vdc, resume=args.resume)
    except KeyboardInterrupt:
        log.info("Interrupted by user.")
        sys.exit(0)
    except Exception as exc:
        log.critical("Fatal error: %s", exc, exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
