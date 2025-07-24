import json
import re
import logging
from pathlib import Path
from datetime import datetime
import yaml
import requests
from packaging.version import parse as parse_version, InvalidVersion
from jinja2 import Environment, FileSystemLoader
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    WebDriverException,
    SessionNotCreatedException,
    TimeoutException,
    StaleElementReferenceException,
    NoSuchElementException
)


# === Utility Functions ===
def get_current_quarter():
  """Returns the current calendar year and quarter, CY2025 Q3 as of the time of writing this."""
  now = datetime.now()
  return now.year, f"Q{(now.month - 1) // 3 + 1}"


def generate_quarter_map(year):
  """
  Generates a mapping of CY-year-quarter strings to column indices.
  Includes previous, current, and next year.
  """
  quarters = ["Q1", "Q2", "Q3", "Q4"]
  return {
       f"CY{yr} {q}": i
       for i, (yr, q) in enumerate(
           (y, q) for y in range(year - 1, year + 2) for q in quarters
       )
    }

def extract_numeric_version(v_str):
  """
  Extracts and parses the numeric part of a version string.
  Returns a packaging.version.Version object or None.
  """
  match = re.search(r'\d+(\.\d+)?', v_str)
  if match:
    try:
      return parse_version(match.group(0))
    except InvalidVersion:
      return None
  return None


def normalize_version_string(v_str):
  """
  Normalizes a version string for comparison.
  - Removes `.x` if present.
  - Adds `.x` to versions like '1.2'.
  """
  if v_str.endswith(".x"):
    return v_str[:-2]
  if re.match(r"^\d+\.\d+$", v_str):
    return f"{v_str}.x"
  return v_str

def is_url_valid(url, timeout=10):
  """
  Checks if the given TRM URL is reachable and not flagged as invalid.
  Returns True if valid, False otherwise.
  """
  headers = {"User-Agent": "Mozilla/5.0"}
  try:
    response = requests.get(url, headers=headers, timeout=timeout)
    if response.status_code != 200:
      return False
    if "The Entry you are looking for is invalid" in response.text:
      return False
    return True
  except requests.RequestException as e:
    logging.warning("URL check failed for %s: %s", url, e)
    return False

# === Constants ===
TABLE_XPATH = "//table[.//th[contains(text(), 'CY')]]"

DECISION_NOT_FOUND = "Decision Not Found"
INVALID_LINK_DECISION = "Unapproved (Invalid Link)"

CURR_YEAR, CURR_QUARTER = get_current_quarter()
QUARTER_MAP = generate_quarter_map(CURR_YEAR)

# === Selenium-Based Functions ===
def get_decision_date(driver):
  """
  Extracts the decision date from the TRM page content using JavaScript.
  Returns a list split from the raw string or 'Not Found' if unavailable.
  """
  try:
    script = (
      "return document.body.innerText.match(/Decision Date \\((.*?)\\)/)?.[1] || 'Unknown';"
    )
    decision_text = driver.execute_script(script)
    if decision_text:
      return decision_text.split(" ")

    logging.warning("Decision date not found.")
    return "Not Found"

  except NoSuchElementException:
    logging.warning("Element with decision date not found.")
    return "Not Found"

def get_current_decision(driver, version):
  """
  Locates the decision for a specific version within the TRM quarter table.
  Uses both original and normalized version values for flexibility.
  Returns a tuple: (matched_version, decision).
  """
  target_header = f"CY{CURR_YEAR} {CURR_QUARTER}"

  table = driver.find_element(By.XPATH, TABLE_XPATH)
  rows = table.find_elements(By.TAG_NAME, "tr")

  if len(rows) < 2:
    logging.warning("Table does not have enough header rows.")
    return None, DECISION_NOT_FOUND

  col_index = QUARTER_MAP.get(target_header)
  if col_index is None:
    logging.warning("Couldn't find column for %s", target_header)
    return None, DECISION_NOT_FOUND
  col_index += 1

  original_version = extract_numeric_version(version)
  normalized_version = extract_numeric_version(normalize_version_string(version))

  for row in rows[2:]:
    cells = row.find_elements(By.TAG_NAME, "td")
    if not cells:
      continue

    row_version = cells[0].text.strip()
    parsed_row_version = extract_numeric_version(row_version)

    if parsed_row_version in [original_version, normalized_version]:
      if col_index < len(cells):
        decision = cells[col_index].text.strip()
        return row_version, decision
      logging.warning("Column index %s out of range for version row %s", col_index, row_version)
      return row_version, DECISION_NOT_FOUND

  logging.warning("No matching version found for %s (normalized as %s)", version, normalize_version_string(version))
  return None, DECISION_NOT_FOUND


def get_all_version_decisions(driver):
  """
  Scrapes all version-decision pairs from the TRM quarter table.
  Returns a list of tuples (version, decision) for the active quarter column.
  """
  target_header = f"CY{CURR_YEAR} {CURR_QUARTER}"

  table = driver.find_element(By.XPATH, TABLE_XPATH)
  rows = table.find_elements(By.TAG_NAME, "tr")

  col_index = QUARTER_MAP.get(target_header)
  if col_index is None or len(rows) < 2:
    logging.warning("Couldn't find valid column or table rows.")
    return []

  col_index += 1
  version_map = []

  for row in rows[2:]:
    cells = row.find_elements(By.TAG_NAME, "td")
    if not cells or col_index >= len(cells):
      continue

    version = cells[0].text.strip()
    decision = cells[col_index].text.strip()

    if any(char.isdigit() for char in version):
      version_map.append((version, decision))

  return version_map


def check_decision_status(decision1, version1, decision2, version2):
  """
  Compares stored vs. scraped decision/version to determine status.
  Returns status string: 'InCompliance', 'InDivest', 'Decision Mismatch', or 'Unapproved'.
  """
  v1 = extract_numeric_version(version1)
  v2 = extract_numeric_version(version2)

  if not decision2 or DECISION_NOT_FOUND in decision2 or "Unapproved" in decision2:
    return "Unapproved"
  if "DIVEST" in decision2:
    return "InDivest"
  if v1 == v2 and decision1 == decision2:
    return "InCompliance"
  if v1 == v2 and decision1 != decision2:
    return f"Decision Mismatch (Was: {decision1} Now: {decision2})"
  return "Unapproved"


def find_next_valid_version(current_version, version_map):
  """
  Finds the next authorized version that is newer than the current one.
  Returns the best candidate (version, decision) or (None, None) if none found.
  """
  original = extract_numeric_version(current_version)
  alt_version_str = normalize_version_string(current_version)
  alt = extract_numeric_version(alt_version_str)

  candidates = []
  for version, decision in version_map:
    parsed_version = extract_numeric_version(version)
    if parsed_version is None:
      continue

    # Only consider clean authorized versions
    if "Authorized" in decision and "DIVEST" not in decision and "POA&M" not in decision:
      if original and parsed_version > original:
        candidates.append((parsed_version, version, decision))
      elif alt and parsed_version > alt:
        candidates.append((parsed_version, version, decision))

    # Fallback logic: pick any authorized version
  if not candidates:
    for version, decision in version_map:
      parsed_version = extract_numeric_version(version)
      if parsed_version and "Authorized" in decision and "DIVEST" not in decision and "POA&M" not in decision:
        candidates.append((parsed_version, version, decision))

  if candidates:
    candidates.sort()
    _, next_version, next_decision = candidates[0]
    return next_version, next_decision
  return None, None


# === Data Collection ===
def fetch_data(driver, url, version):
  """
  Loads a TRM tool page and extracts core metadata for the specified version.
  Returns a dictionary with details, or None if an error occurs.
  """
  try:
    driver.get(url)
    WebDriverWait(driver, 15).until(
      EC.presence_of_element_located((By.XPATH, "//table[.//th[contains(text(), 'CY')]]"))
    )

  except SessionNotCreatedException as e:
    logging.error("Failed to create session: %s", e)
    return None
  except TimeoutException as e:
    logging.error("Timeout while trying to start the browser: %s", e)
    return None
  except WebDriverException as e:
    logging.error("WebDriver error occurred: %s", e)
    return None
  except ConnectionError as e:
    logging.error("Connection error occurred: %s", e)
    return None

  try:
    decision_date = get_decision_date(driver)
    matched_version, decision = get_current_decision(driver, version)
    clean_decision = decision.replace("\n", " ") if decision else DECISION_NOT_FOUND

    return {
      "URL": url,
      "Name": driver.title.strip(),
      "Tid": driver.find_element(By.ID, "ContentPlaceHolder1_hdnToolId").get_attribute("value"),
      "Version": matched_version if matched_version else version,
      "Decision": clean_decision,
      "Status": "",
      "Decision Date": decision_date[0]
    }

  except (NoSuchElementException, StaleElementReferenceException, TimeoutException) as e:
    logging.error("Failed to obtain elements: %s", e)
    return None

def process_entry(driver, base_url, tid, version, name, decision):
  """
  Validates and processes a TRM tool entry. If valid, compares decisions
  and finds next approved version if needed.
  Returns a populated entry dictionary or None.
  """
  url = f"{base_url}?tid={tid}&tab=2"
  if not is_url_valid(url):
    return {
      "URL": url,
      "Name": name,
      "Tid": tid,
      "Version": version,
      "Decision": INVALID_LINK_DECISION,
      "Status": "Unapproved",
      "Next Approved Version": "None Found",
      "Decision Date": "None"
    }

  entry = fetch_data(driver, url, version)
  if not entry:
    return None

  entry["Status"] = check_decision_status(decision, version, entry["Decision"], entry["Version"])
  if any(flag in entry["Decision"] for flag in ["Unapproved", DECISION_NOT_FOUND, "DIVEST"]):
    version_map = get_all_version_decisions(driver)
    next_version, next_decision = find_next_valid_version(version, version_map)
    entry["Next Approved Version"] = f"{next_version }\n {next_decision}" if next_version else "No Approved Version Found"

  return entry


# === Report Generation ===
def generate_report():
  """
  Main logic for generating the TRM compliance report.
  Loads data, runs extraction, and outputs both JSON and HTML.
  """
  # Setup headless browser
  chrome_options = Options()
  chrome_options.add_argument("--headless")
  chrome_options.add_argument("--disable-gpu")
  chrome_options.add_argument("--disable-dev-shm-usage")
  chrome_options.accept_insecure_certs = True
  driver = webdriver.Chrome(options=chrome_options)

  # Load input YAML
  script_dir = Path(__file__).resolve().parent
  yaml_path = script_dir.parent.parent / "files" / "trm_usage.yml"

  with open(yaml_path, "r", encoding="utf-8") as file:
    config = yaml.safe_load(file)

  base_url = config.get("trm_base_url", "")
  entries = config.get("trm_entries", [])

  # Build report structure
  report = {
    "trm_base_url": base_url,
    "trm_entries": []
  }

  try:
    for entry in entries:
      tid = entry["tid"]
      version = entry["version"]
      name = entry["name"]
      decision = entry["decision"]
      try:
        result = process_entry(driver, base_url, tid, version, name, decision)
        report["trm_entries"].append(result)
      except Exception as e:
        logging.error("Error processing TID %s with version %s: %s", tid, version, e)
  finally:
    driver.quit()

  # Write JSON report
  with open("trm_report.json", "w", encoding="utf-8") as f_json:
    json.dump(report, f_json, indent=2)

  # Render HTML report
  template_dir = script_dir / "templates"
  env = Environment(loader=FileSystemLoader(template_dir))
  template = env.get_template("report_template.html.j2")
  html_output = template.render(trm_entries=report["trm_entries"])

  with open("trm_report.html", "w", encoding="utf-8") as f_html:
    f_html.write(html_output)

# === Main Function ===
if __name__ == "__main__":
  generate_report()
