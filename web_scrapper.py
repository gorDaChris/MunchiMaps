from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import NoSuchElementException
import json
import re
from pathlib import Path

OUTPUT_PATH = Path(__file__).resolve().parent / "Website" / "data" / "building-hours.json"

BUILDING_NAME_MAP = {
    "amos eaton": "Amos Eaton Hall",
    "amos eaton hall": "Amos Eaton Hall",
    "academy hall": "Academy Hall",
    "davison hall": "Davison Hall",
    "dcc": "DCC",
    "darrin communications center": "DCC",
    "folsom library": "Folsom Library",
    "greene building": "Greene Building",
    "jec": "JEC",
    "jonsson engineering center": "JEC",
    "jrowl": "JROWL",
    "jonsson rowland": "JROWL",
    "mueller center": "Mueller Center",
    "north hall": "North Hall",
    "pittsburgh building": "Pittsburgh Building",
    "pub safe": "Pub Safe",
    "public safety": "Pub Safe",
    "quad": "Quad",
    "sage labs": "Sage Labs",
    "sharp hall": "Sharp Hall",
    "union": "Union",
    "voorhees computing center": "Voorhees Computing Center",
    "vcc": "Voorhees Computing Center",
    "warren hall": "Warren Hall",
    "west hall": "West Hall",
}


def normalize_name(name):
    return re.sub(r"\s+", " ", name.strip().lower())


def canonical_name(name):
    normalized = normalize_name(name)
    return BUILDING_NAME_MAP.get(normalized, name.strip())


def parse_time_token(token):
    cleaned = token.strip().lower().replace(".", "")
    match = re.match(r"(\d{1,2})(?::(\d{2}))?\s*([ap]m)", cleaned)
    if not match:
        return None

    hour = int(match.group(1))
    minute = int(match.group(2) or 0)
    meridiem = match.group(3)

    if meridiem == "pm" and hour != 12:
        hour += 12
    if meridiem == "am" and hour == 12:
        hour = 0

    return hour + (minute / 60.0)


def format_decimal_time(decimal_value):
    total_minutes = int(round(decimal_value * 60))
    hours = (total_minutes // 60) % 24
    minutes = total_minutes % 60
    suffix = "PM" if hours >= 12 else "AM"
    hour_12 = hours % 12 or 12
    return f"{hour_12}:{minutes:02d} {suffix}"


def extract_daily_range(*cells):
    for cell in cells:
        if not cell:
            continue
        cleaned = " ".join(cell.split())
        matches = re.findall(r"\d{1,2}(?::\d{2})?\s*[ap]\.?\s*m\.?", cleaned, flags=re.IGNORECASE)
        if len(matches) < 2:
            continue

        open_time = parse_time_token(matches[0])
        close_time = parse_time_token(matches[1])
        if open_time is None or close_time is None:
            continue

        return {
            "open": open_time,
            "close": close_time,
            "display": f"{format_decimal_time(open_time)} - {format_decimal_time(close_time)}",
            "source": cleaned,
        }
    return None

# Initialize Chrome options
chrome_options = Options()
chrome_options.add_argument("--headless=new")
chrome_options.add_argument("--disable-gpu")

driver = webdriver.Chrome(options=chrome_options)
driver.get('https://publicsafety.rpi.edu/campus-security/card-access-schedule')

# Wait until the table is present on the page
wait = WebDriverWait(driver, 10, ignored_exceptions=(NoSuchElementException))
wait.until(
    EC.visibility_of_element_located((By.XPATH, '//*[@id="block-paperclip-content"]/div/article/div/div/div/div/div/table'))
)

# Find the tbody element
tbody = driver.find_element(By.XPATH, '//*[@id="block-paperclip-content"]/div/article/div/div/div/div/div/table/tbody')
data = []
# Iterate through all rows in the table body
for tr in tbody.find_elements(By.XPATH, './/tr'):  # Use find_elements here to get all rows
    row = [item.text for item in tr.find_elements(By.XPATH, './td')]
    data.append(row)

hours_snapshot = {}
for row in data:
    if not row:
        continue

    building_name = canonical_name(row[0])
    parsed_range = extract_daily_range(*row[1:])
    if parsed_range is None:
        continue

    hours_snapshot[building_name] = {
        "open": parsed_range["open"],
        "close": parsed_range["close"],
        "display": parsed_range["display"],
    }

OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
with OUTPUT_PATH.open("w", encoding="utf-8") as output_file:
    json.dump(hours_snapshot, output_file, indent=2, sort_keys=True)

for building_name, hours in sorted(hours_snapshot.items()):
    print(f"{building_name}\t{hours['display']}")

driver.quit()
