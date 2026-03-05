# Nepal Voter List Scraper

Scrapes voter list data from the **Election Commission Nepal** website:  
`https://voterlist.election.gov.np/`

---

## Project Structure

```
election_commision/
├── venv/                    # Python virtual environment
├── output/                  # CSV files are saved here
├── scraper.py               # Main scraper
├── requirements.txt
├── checkpoint.json          # Auto-created; tracks progress for resume
├── scraper.log              # Full run log
└── README.md
```

---

## Setup

```powershell
# 1. Create and activate virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# 2. Install dependencies
pip install -r requirements.txt
```

---

## Usage

```powershell
# Activate venv first (always)
.\venv\Scripts\Activate.ps1

# Scrape all of Dolakha district (default)
python scraper.py

# Scrape a specific municipality only (e.g. Bhimeshwor = 5176)
python scraper.py --vdc 5176

# Resume an interrupted run (skips already-done entries)
python scraper.py --resume

# Change delay between requests (default 1.5s — don't go too low)
python scraper.py --delay 2.0

# Different district (future use)
python scraper.py --state 3 --district 15
```

---

## Output

A CSV file is saved to `output/voters_<district_name>_district17.csv` with these columns:

| Column            | Description                              |
|-------------------|------------------------------------------|
| `state`           | Province number (3 = Bagmati)            |
| `state_name`      | Province name in Nepali                  |
| `district`        | District number (17 = Dolakha)           |
| `district_name`   | District name in Nepali                  |
| `vdc_mun_id`      | Municipality/VDC numeric ID              |
| `vdc_mun_name`    | Municipality name in Nepali              |
| `ward_no`         | Ward number                              |
| `reg_centre_id`   | Registration centre ID                   |
| `reg_centre_name` | Registration centre name                 |
| `serial_no`       | Serial number in ward list               |
| `voter_no`        | Unique voter ID number                   |
| `voter_name`      | Voter full name (in Nepali)              |
| `age`             | Age in years                             |
| `gender`          | Gender (पुरुष / महिला / अन्य)           |
| `spouse_name`     | Spouse name                              |
| `parents_name`    | Father / Mother name                     |

---

## Municipalities in Dolakha (District 17)

| ID   | Name (Nepali)              | Type          |
|------|---------------------------|---------------|
| 5172 | कालिन्चोक गाउँपालिका     | Rural         |
| 5173 | गौरिशंकर गाउँपालिका      | Rural         |
| 5174 | जिरी नगरपालिका            | Municipality  |
| 5175 | तामाकोशी गाउँपालिका      | Rural         |
| 5176 | भिमेश्वर नगरपालिका        | Municipality  |
| 5177 | मेलुङ गाउँपालिका          | Rural         |
| 5178 | विगु गाउँपालिका            | Rural         |
| 5179 | वैतेश्वर गाउँपालिका       | Rural         |
| 5180 | शैलुङ गाउँपालिका          | Rural         |

---

## Notes

- The scraper is **respectful** — it waits 1.5 seconds between requests by default.
- **Checkpoint** is saved after every registration centre, so you can safely `Ctrl+C` and resume later with `--resume`.
- The CSV uses **UTF-8 with BOM** (`utf-8-sig`) so Nepali text opens correctly in Excel.
- Logs are written to both console and `scraper.log`.
