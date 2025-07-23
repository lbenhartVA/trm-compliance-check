import json
import re
from pathlib import Path
from datetime import datetime
import logging
from selenium import webdriver
import yaml
import requests
from jinja2 import Environment, FileSystemLoader
from packaging.version import parse as parse_version, InvalidVersion
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException, SessionNotCreatedException
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException, NoSuchElementException



# === Utility Functions ===

#Returns the current year and quarter
def get_current_quarter():
  now = datetime.now()
  return now.year,  f"Q{(now.month - 1) // 3 + 1}"

#Generates a map of the quarters of the current, pervious, and next year
def generate_quarter_map(year):
  quarters = ["Q1", "Q2", "Q3", "Q4"]
  return {
      f"CY{yr} {q}": i
      for i, (yr, q) in enumerate(
          (y, q) for y in range(year - 1, year + 2) for q in quarters
        )
    }

def extract_numeric_version(v_str):
  match = re.search(r'\d+(\.\d+)?', v_str)
  if match:
    try:
      return parse_version(match.group(0))
    except InvalidVersion:
      return None
  return None

def normalize_version_string(v_str):
  # Removes `.x` if present, adds `.x` if missing
  if v_str.endswith(".x"):
    return v_str[:-2]
  if re.match(r"^\d+\.\d+$", v_str):
    return f"{v_str}.x"
  return v_str

#Helper function to check if the url actually has the proper page
def is_url_valid(url, timeout=10):
  headers = {"User-Agent": "Mozilla/5.0"}
  try:
    response = requests.get(url, headers=headers, timeout=timeout)
    if response.status_code != 200:
      return False
    # Look for the known error message in the page content
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
  try:
    decision_text = driver.execute_script("return document.body.innerText.match(/Decision Date \\((.*?)\\)/)?.[1] || 'Unknown';")
    if decision_text:
      return decision_text.split(" ")

    logging.warning("Decision date not found.")
    return "Not Found"

  except NoSuchElementException:
    logging.warning("Element with decision date not found.")
    return "Not Found"

def get_current_decision(driver, version):
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
        return row_version, cells[col_index].text.strip()
      logging.warning("Column index %s out of range for version row %s", col_index, row_version)
      return row_version, DECISION_NOT_FOUND

  logging.warning("No matching version found for %s (normalized as %s)", version, normalize_version_string(version))
  return None, DECISION_NOT_FOUND

def get_all_version_decisions(driver):
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
  original = extract_numeric_version(current_version)
  alt_version_str = normalize_version_string(current_version)
  alt = extract_numeric_version(alt_version_str)

  candidates = []
  for version, decision in version_map:
    parsed_version = extract_numeric_version(version)
    if parsed_version is None:
      continue

    if "Authorized" in decision and "DIVEST" not in decision and "POA&M" not in decision:
      # Accept if it's greater than either version interpretation
      if original and parsed_version > original:
        candidates.append((parsed_version, version, decision))
      elif alt and parsed_version > alt:
        candidates.append((parsed_version, version, decision))

  # If no higher versions found, attempt to match any authorized version (fallback)
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

#Collects all the data into one entry and outputs said entry
def fetch_data(driver, url, version):
  try:
    driver.get(url)
    WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.XPATH, "//table[.//th[contains(text(), 'CY')]]"))
        )

  #Runs all the expections that could cause the Chrome Browers to fail
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
     #Obtains the decision of the given version
    decision_date = get_decision_date(driver)
    matched_version, decision = get_current_decision(driver, version)
    clean_decision = decision.replace("\n", " ") if decision else DECISION_NOT_FOUND

     #All the data needed is stored in this entry
    entry = {
      "URL": url,
      "Name": driver.title.strip(),
      "Tid": driver.find_element(By.ID, "ContentPlaceHolder1_hdnToolId").get_attribute("value"), 
      "Version": matched_version if matched_version else version,
      "Decision": clean_decision,
      "Status": "",
      "Decision Date": decision_date[0]
      }
    return entry
  #Runs all the expections that could cause the required elements not to be obtained
  except (NoSuchElementException, StaleElementReferenceException, TimeoutException) as e:
    logging.error("Failed to obtain elements: %s", e)
    return None




def process_entry(driver, b_url, tid, version, name, decision):
  url = f"{b_url}?tid={tid}&tab=2"
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

  entry_result = fetch_data(driver, url, version)
  if entry_result is not None:
    entry_result["Status"] = check_decision_status(decision, version, entry_result["Decision"], entry_result["Version"])
    if any(x in entry_result["Decision"] for x in ["Unapproved", DECISION_NOT_FOUND, "DIVEST"]):
      version_map = get_all_version_decisions(driver)
      next_version, next_decision = find_next_valid_version(version, version_map)
      if next_version:
        entry_result["Next Approved Version"] = f"{next_version}\n {next_decision}"
      else:
        entry_result["Next Approved Version"] = "No Approved Version Found"
    return entry_result
  return None

# === Report Generation ===
def generate_report():
#Opens a headless Chrome Browser
  chrome_options = Options()
  chrome_options.add_argument("--headless")
  chrome_options.add_argument("--disable-gpu")
  chrome_options.add_argument("--disable-dev-shm-usage")
  chrome_options.accept_insecure_certs = True
  web_driver = webdriver.Chrome(options=chrome_options)

  #Gets the relative path of the trm_usage file
  script_dir = Path(__file__).resolve().parent
  yaml_path = script_dir.parent.parent / "files" / "trm_usage.yml"

  #Reads in and passes the yml file
  with open(yaml_path, 'r', encoding="utf-8") as file:
    data = yaml.safe_load(file)
    base_url = data.get("trm_base_url", "")
    input_data = [(entry["tid"], entry["version"],
                    entry["name"], entry["decision"], entry["approval_date"]) for entry in data.get("trm_entries", [])]

    #The structure to build the json report
  report = {
  "trm_base_url": base_url,
  "trm_entries": []
}
  #Iterates through each entry and runs fetch data on the valid entries
  try:
    for file_tid, file_version, entry_name, file_decision, date in input_data:
      try:
        result = process_entry(web_driver, base_url, file_tid, file_version,
                               entry_name, file_decision)
        report["trm_entries"].append(result)
      except Exception as e:
        logging.error("Error processing TID %s with version %s: %s", file_tid, file_version, e)
  finally:
    web_driver.quit()

  #Prints out the full report
  json_report = json.dumps(report, indent=2)
  with open("trm_report.json", "w", encoding="utf-8") as file:
    file.write(json_report)

  script_dir = Path(__file__).resolve().parent
  template_dir = script_dir / "templates"

  env = Environment(loader=FileSystemLoader(template_dir))
  template = env.get_template("report_template.html.j2")

  # Render HTML with your report data
  html_output = template.render(trm_entries=report["trm_entries"])

  # Save to file
  with open("trm_report.html", "w", encoding="utf-8") as f:
    f.write(html_output)


# === Main Function ===
if __name__ == "__main__":
  generate_report()
