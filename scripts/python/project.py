from selenium import webdriver
from selenium.webdriver.common.by import By
import json
from datetime import datetime
import yaml
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


def get_current_decision(driver, version, curr_year=None, curr_quarter=None):
    # Use cached quarter if provided, otherwise compute it
    if not curr_year or not curr_quarter:
        curr_year, curr_quarter = get_current_quarter()
    target_header = f"CY{curr_year} {curr_quarter}"

    try:
        # Wait for the table to be present
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.XPATH, "//table[.//th[contains(text(), 'CY')]]"))
        )
        table = driver.find_element(By.XPATH, "//table[.//th[contains(text(), 'CY')]]")
        rows = table.find_elements(By.TAG_NAME, "tr")

        if len(rows) < 2:
            print("Table does not have enough header rows.")
            return None

        year_row = rows[0].find_elements(By.TAG_NAME, "th")
        quarter_row = rows[1].find_elements(By.TAG_NAME, "th")

        # Expand year headers
        expanded_years = []
        for cell in year_row:
            text = cell.text.strip()
            colspan = int(cell.get_attribute("colspan") or 1)
            expanded_years.extend([text] * colspan)

        # Build full column labels
        header_labels = []
        for year, quarter_cell in zip(expanded_years, quarter_row):
            quarter = quarter_cell.text.strip()
            if quarter:
                full_label = f"{year} {quarter}"
                header_labels.append(full_label)
        try:
            col_index = header_labels.index(target_header)
        except ValueError:
            print(f"Could not find column for {target_header}")
            return None

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
                    print(f"Column index {col_index} out of range for version row '{row_version}'")
                    return None

        print(f"Version '{version}' not found in matrix")
        return "Not Found"

    except TimeoutException:
        print("Timed out waiting for the decision table to load.")
        return None

#Collects all the data into one entry and outputs said entry
def fetch_data(driver, url, version):  

  try:
    driver.get(url)
    
  #Runs all the expections that could cause the Chrome Browers to fail
  except ConnectionError as e:
    print("Connection error occurred:")
    print(e)
    return
  except WebDriverException as e:
    print("WebDriver error occurred:")
    print(e)
    return
  except TimeoutException as e:
    print("Timeout while trying to start the browser:")
    print(e)
    return
  except SessionNotCreatedException as e:
    print("Failed to create session:")
    print(e)
    return

  try:
     #loads the decision table of the website
     label = driver.find_element(By.XPATH, "//td[text()='Decision Date:']")
     value = label.find_element(By.XPATH, "following-sibling::td")
     decision_date = value.text.strip()
     cur_year, cur_quarter = get_current_quarter()

     #All the data needed is stored in this array
     entry = {
          "URL": url,
          "Name": driver.title.strip(), 
          "Version": version,
          "Decision": get_current_decision(driver, version, cur_year, cur_quarter),
          "Decision Date": decision_date
          }
     return {
     "trm_base_url": url.split("?")[0],
     "trm_entries":[entry]
     }
  #Runs all the expections that could cause the required elements not to be obtained
  except NoSuchElementException as e:
    print("Couldn't locate a required element on the page:")
    print(e)
  except TimeoutException as e:
    print("Operation timed out while trying to access elements:")
    print(e)
  except StaleElementReferenceException as e:
    print("Encountered stale element reference:")
    print(e)


#Runs the code with a certain tid and version for testing
if __name__ == "__main__":
    
    #Opens a headless Chrome Browser
    chrome_options = Options()
    chrome_options.add_argument("--headless") 
    chrome_options.add_argument("--disable-gpu") 
    chrome_options.add_argument("--disable-dev-shm-usage") 
    chrome_options.accept_insecure_certs = True
    driver = webdriver.Chrome(options=chrome_options)

    results = []
    counter = 0

    yaml_path = r"C:\Users\abrahamn\.vscode\trm-compliance-check\files\trm_usage.yml"
    with open(yaml_path, 'r') as file:
      data = yaml.safe_load(file)
      base_url = data.get("trm_base_url", "")
      input_data = [(entry["tid"], entry["version"]) for entry in data.get("trm_entries", [])]
    try:
      for tid, version in input_data:
        try:
          url = f"{base_url}?tid={tid}&tab=2"
          result = fetch_data(driver, url, version)
          if result:
             results.append(result)
             counter+=1
             print(counter)
        except Exception as e:
           print(f"Error processing TID {tid} with version {version}: {e}")
    finally:
            driver.quit()

    print(json.dumps(results, indent=2))