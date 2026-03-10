import logging
from tqdm import tqdm
from .config import STATE_MAP
from .parsers import parse_voter_table
from .storage import load_checkpoint, save_checkpoint, get_csv_writer, is_district_completed

log = logging.getLogger(__name__)

def scrape_district(client, state: int, district: int, vdc_filter: int = None, resume: bool = False):
    """Scrapes a single district end-to-end."""
    done_keys = load_checkpoint() if resume else set()

    # Get district name
    districts = client.get_districts(state)
    district_info = next(
        (d for d in districts if d["value"] == str(district)),
        {"value": str(district), "label": f"District-{district}"},
    )
    district_name = district_info["label"]
    
    log.info("=" * 60)
    log.info("Scraping district: %s (id=%s)", district_name, district)
    log.info("=" * 60)

    fp, writer, csv_path = get_csv_writer(district_name, district)
    log.info("Output CSV: %s", csv_path)

    municipalities = client.get_municipalities(district)
    if vdc_filter:
        municipalities = [m for m in municipalities if m["value"] == str(vdc_filter)]

    total_voters = 0
    total_rc = 0

    try:
        for mun in tqdm(municipalities, desc="Municipalities", position=0):
            mun_id, mun_name = int(mun["value"]), mun["label"]
            wards = client.get_wards(mun_id)
            if not wards: continue

            for ward in tqdm(wards, desc=f"  {mun_name[:15]}", position=1, leave=False):
                ward_no = ward["value"]
                reg_centres = client.get_reg_centres(mun_id, ward_no)

                for rc in reg_centres:
                    rc_id, rc_name = rc["value"], rc["label"]
                    key = f"{mun_id}_{ward_no}_{rc_id}"
                    if key in done_keys: continue

                    try:
                        html = client.get_voter_page(state, district, mun_id, ward_no, rc_id)
                        voters = parse_voter_table(html)
                        for v in voters:
                            writer.writerow({
                                **v, "state": state, "state_name": STATE_MAP.get(state, ""),
                                "district": district, "district_name": district_name,
                                "vdc_mun_id": mun_id, "vdc_mun_name": mun_name,
                                "ward_no": ward_no, "reg_centre_id": rc_id, "reg_centre_name": rc_name
                            })
                        fp.flush()
                        total_voters += len(voters)
                        total_rc += 1
                        done_keys.add(key)
                        save_checkpoint(done_keys)
                    except Exception as e:
                        log.error("Error on %s: %s", key, e)
                        continue
    finally:
        fp.close()
    
    log.info("District %s done. Voters: %d, RC: %d", district_name, total_voters, total_rc)

def scrape_all(client, resume: bool = False):
    """Bulk scrape all districts."""
    for state_id in range(1, 8):
        log.info("\n" + "#" * 60)
        log.info("### STATE %d: %s", state_id, STATE_MAP.get(state_id, "Unknown"))
        log.info("#" * 60)
        
        try:
            districts = client.get_districts(state_id)
        except Exception as e:
            log.error("Failed to get districts for state %d: %s", state_id, e)
            continue
            
        for d in districts:
            d_id, d_label = int(d["value"]), d["label"]
            if is_district_completed(d_id, d_label):
                log.info(">>> Skipping %s (id=%d) - already exists.", d_label, d_id)
                continue
            
            try:
                scrape_district(client, state_id, d_id, resume=resume)
            except Exception as e:
                log.error("Failed scraping %s: %s", d_label, e)
                continue
