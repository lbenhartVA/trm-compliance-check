from selenium import webdriver
import logging
from selenium.webdriver.common.by import By
import json
from datetime import datetime
import yaml
import requests
from pathlib import Path
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException, SessionNotCreatedException, TimeoutException, StaleElementReferenceException, NoSuchElementException

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
       return "Unapproved(Decision Not Found)"
    
    #finds how far our target header is in the map
    col_index = QUARTER_MAP.get(target_header)
    if col_index is None:
        logging.warning(f"Couldn't find column for {target_header}")
        return "Unapproved(Decision Not Found)"
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
          else:
           logging.warning(f"Column index {col_index} out of range for version row '{row_version}'")
           return "Unapproved(Decision Not Found)"

    logging.warning(f"Version '{version}' not found in matrix")
    return "Unapproved (Decision Not Found)"


#Collects all the data into one entry and outputs said entry
def fetch_data(driver, url, version):  
  try:
    driver.get(url)
    WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.XPATH, "//table[.//th[contains(text(), 'CY')]]"))
        )
    
  #Runs all the expections that could cause the Chrome Browers to fail
  except ConnectionError as e:
    logging.error("Connection error occurred:", e)
    return
  except WebDriverException as e:
    logging.error("WebDriver error occurred:", e)
    return
  except TimeoutException as e:
    logging.error("Timeout while trying to start the browser:", e)
    return
  except SessionNotCreatedException as e:
    logging.error("Failed to create session:", e)
    return

  try:
     #Obtains the decision of the given version
     cur_year, cur_quarter = get_current_quarter()
     decsion = get_current_decision(driver, version, cur_year, cur_quarter)

     #All the data needed is stored in this entry
     entry = {
          "Entry Number": 1,
          "URL": url,
          "Name": driver.title.strip(),
          "Tid": driver.find_element(By.ID, "ContentPlaceHolder1_hdnToolId").get_attribute("value"), 
          "Version": version,
          "Decision": decsion,
          "Decision Date": "None"
          }
     return entry
  
    #Runs all the expections that could cause the required elements not to be obtained
  except NoSuchElementException as e:
    logging.error("Couldn't locate a required element on the page:", e)
    return
  except TimeoutException as e:
    logging.error("Operation timed out while trying to access elements:", e)
    return
  except StaleElementReferenceException as e:
    logging.error("Encountered stale element reference:", e)
    return
  
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

#Runs the code with a certain tid and version for testing
if __name__ == "__main__":
    
    #Opens a headless Chrome Browser
    chrome_options = Options()
    chrome_options.add_argument("--headless") 
    chrome_options.add_argument("--disable-gpu") 
    chrome_options.add_argument("--disable-dev-shm-usage") 
    chrome_options.accept_insecure_certs = True
    driver = webdriver.Chrome(options=chrome_options)

    #Gets the relative path of the trm_usage file
    script_dir = Path(__file__).resolve().parent
    yaml_path = script_dir.parent.parent / "files" / "trm_usage.yml"

    #Reads in and passes the yml file
    with open(yaml_path, 'r') as file:
      data = yaml.safe_load(file)
      base_url = data.get("trm_base_url", "")
      input_data = [(entry["tid"], entry["version"], entry["name"]) for entry in data.get("trm_entries", [])]

    #The structure to build the json report
    report = {
    "trm_base_url": base_url,
    "trm_entries": []
}
    #Here to keep track of the number of entries
    counter = 0

    #Iterates through each entry and runs fetch data on the valid entries
    try:
      for tid, version, name in input_data:
        try:
          url = f"{base_url}?tid={tid}&tab=2"
          if not is_url_valid(url):
            logging.warning("Skipping invalid or unreachable URL: %s", url)
            result = {
            "Entry Number": counter,
            "URL": "Invalid",
            "Name": name,
            "Tid": tid,
            "Version": version,
            "Decision": "Unapproved (Invaild Link)",
            "Decision Date": "None"
           }
            report["trm_entries"].append(result)
            continue

          result = fetch_data(driver, url, version)
          if result:
             counter += 1
             result["Entry Number"] = counter 
             report["trm_entries"].append(result)
             print("Processed", counter, "entries")
        except Exception as e:
           logging.error(f"Error processing TID {tid} with version {version}: {e}")
    finally:
            driver.quit()

    #Prints out the full report        
    print(json.dumps(report, indent=2))