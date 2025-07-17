import json
import yaml
import requests
import logging
from pathlib import Path
from datetime import datetime
from selenium import webdriver
from jinja2 import Environment, FileSystemLoader
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException, SessionNotCreatedException
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException, NoSuchElementException

#Uses datetime to get the current year and quarter
def get_current_quarter():
  now = datetime.now()
  current_year = now.year
  current_quarter = f"Q{(now.month - 1) // 3 + 1}"
  return current_year, current_quarter

#A helper function to make a map of the quarters of the current, pervious, and next year
def generate_quarter_map(year):
  quarters = ["Q1", "Q2", "Q3", "Q4"]
  return {
      f"CY{year} {q}": i
      for i, (year, q) in enumerate(
          (y, q) for y in range(year - 1, year + 2) for q in quarters
        )
    }


def get_current_decision(driver, version, curr_year=None, curr_quarter=None):
  # Use cached quarter if provided, otherwise compute it
  if not curr_year or not curr_quarter:
    curr_year, curr_quarter = get_current_quarter()
  target_header = f"CY{curr_year} {curr_quarter}"

  #Creates the quarter map
  QUARTER_MAP = generate_quarter_map(curr_year)
  table = driver.find_element(By.XPATH, "//table[.//th[contains(text(), 'CY')]]")
  rows = table.find_elements(By.TAG_NAME, "tr")

  if len(rows) < 2:
    logging.warning("Table does not have enough header rows.")
    return "Unapproved (Decision Not Found)"
  #finds how far our target header is in the map
  col_index = QUARTER_MAP.get(target_header)
  if col_index is None:
    logging.warning("Couldn't find column for %s", target_header)
    return "Unapproved (Decision Not Found)"
  col_index += 1

  # Search for the version row
  for row in rows[2:]:
    cells = row.find_elements(By.TAG_NAME, "td")
    if not cells:
      continue
    row_version = cells[0].text.strip()
    if row_version == version:
      if col_index < len(cells):
        return cells[col_index].text.strip()
      logging.warning("Column index %s out of range for version row %s", col_index, row_version)
      return "Unapproved (Decision Not Found)"

  logging.warning("Version %s not found in matrix", version)
  return "Unapproved (Decision Not Found)"

def get_all_decisions(driver):
  curr_year, curr_quarter = get_current_quarter()
  target_header = f"CY{curr_year} {curr_quarter}"

  #Creates the quarter map
  QUARTER_MAP = generate_quarter_map(curr_year)
  table = driver.find_element(By.XPATH, "//table[.//th[contains(text(), 'CY')]]")
  rows = table.find_elements(By.TAG_NAME, "tr")

  if len(rows) < 2:
    logging.warning("Table does not have enough header rows.")
    return "Unapproved (Decision Not Found)"
  #finds how far our target header is in the map
  col_index = QUARTER_MAP.get(target_header)
  if col_index is None:
    logging.warning("Couldn't find column for %s", target_header)
    return "Unapproved (Decision Not Found)"
  col_index += 1
  version_map = []

  # Search for the version row
  for row in rows[2:]:
    cells = row.find_elements(By.TAG_NAME, "td")
    if not cells:
      continue
    row_version = cells[0].text.strip()
    if col_index < len(cells):
      if any(char.isdigit() for char in row_version):
        decision =  cells[col_index].text.strip()
        version_map.append((row_version, decision))
    logging.warning("Column index %s out of range for version row %s", col_index, row_version)

  return version_map

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
    cur_year, cur_quarter = get_current_quarter()
    decision = get_current_decision(driver, version, cur_year, cur_quarter)
    clean_decision = decision.replace("\n", " ")

     #All the data needed is stored in this entry
    entry = {
      "URL": url,
      "Name": driver.title.strip(),
      "Tid": driver.find_element(By.ID, "ContentPlaceHolder1_hdnToolId").get_attribute("value"), 
      "Version": version,
      "Decision": clean_decision,
      "Status": "",
      "Decision Date": decision_date[0]
      }
    return entry
  #Runs all the expections that could cause the required elements not to be obtained
  except (NoSuchElementException, StaleElementReferenceException, TimeoutException) as e:
    logging.error("Failed to obtain elements: %s", e)
    return None
  

  
#Helper function to check if the url actually has the proper page
def is_url_valid(url, timeout=5):
  try:
    response = requests.get(url, timeout=timeout)
    if response.status_code != 200:
      return False
    # Look for the known error message in the page content
    if "The Entry you are looking for is invalid" in response.text:
      return False
    return True
  except requests.RequestException as e:
    logging.warning("URL check failed for %s: %s", url, e)
    return False

def check_decision_status(decision1, version1, decision2, version2):
  if "DIVEST" in decision2:
    return "InDivest"
  if "Unapproved" in decision2:
    return "Unapproved"
  if not decision1 or not version1 or  not decision2 or not version2:
    return "Unapproved"
  if decision1 == decision2 and version1 == version2:
    return "InCompliance"
  if decision1 != decision2 and version1 == version2:
    return f"Decision Mismatch (Was: {decision1} Now: {decision2})"
  return "Unapproved"


def process_entry(driver, b_url, tid, version, name, decision):
  url = f"{b_url}?tid={tid}&tab=2"
  if not is_url_valid(url):
    return {
    "URL": "Invalid",
    "Name": name,
    "Tid": tid,
    "Version": version,
    "Decision": "Unapproved (Invalid Link)",
    "Status": "Unapproved",
    "Decision Date": "None" 
    }

  entry_result = fetch_data(driver, url, version)
  verisions = get_all_decisions(driver)
  if entry_result is not None:
    entry_result["Status"] = check_decision_status(decision, version, entry_result["Decision"], entry_result["Version"])
    return entry_result
  return None

#Runs the code with a certain tid and version for testing
if __name__ == "__main__":
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
    #Here to keep track of the number of entries
  counter = 0

    #Iterates through each entry and runs fetch data on the valid entries
  try:
    for file_tid, file_version, entry_name, file_decision, date in input_data:
      try:
        result = process_entry(web_driver, base_url, file_tid, file_version, entry_name, file_decision)
        if date is not None and date != result["Decision Date"]:
          result["Decision Date"] = f"Updated from {date} to {result['Decision Date']}"
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
  
    