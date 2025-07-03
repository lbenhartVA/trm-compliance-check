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

def get_current_decision(table, version):
  #Gets the current quarter and assigns them to variables
  curr_year, curr_quarter = get_current_quarter()
  target_header = f"CY{curr_year} {curr_quarter}"
  
  #Gets the two header rows and assigns them to variables
  rows = table.find_elements(By.TAG_NAME, "tr")
  year_row = rows[0].find_elements(By.TAG_NAME, "th")
  quarter_row = rows[1].find_elements(By.TAG_NAME, "th")

  # expands the year row to have the same amount of space as the quarter row
  expanded_years = []
  for cell in year_row:
     text = cell.text.strip()
     colspan = int(cell.get_attribute("colspan") or 1)
     expanded_years.extend([text] * colspan)

  # Builds full column labels like "CY2025 Q3"
  header_labels = []
  for year, quarter_cell in zip(expanded_years, quarter_row):
    quarter = quarter_cell.text.strip()
    if quarter:  # Only include non-empty quarters
        full_label = f"{year} {quarter}"
        header_labels.append(full_label)
  #Gets the index of the current year and quarter
  try:
     col_index = header_labels.index(target_header)
  except ValueError:
     print(f"Could not find column for {target_header}")
     return None
  #Skips the two header rows and finds the row that has the same version as the one inputed.
  #Then it gets the text from the cell a column index away and gets the text which is the decision
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
# Just a checker in case an invaild verision was inputed
  print(f"Version '{version}' not found in matrix")
  return "Not Found"

#Collects all the data into one entry and outputs said entry
def fetch_data(tid, version):  

  #Gets the url of any software on the trm compliance using the tid
  url = f"https://www.oit.va.gov/Services/TRM/ToolPage.aspx?tid={tid}&tab=2"
  

  try:
    #Opens a headless Chrome Browser with the set url and closes once it gets the decision table
    chrome_options = Options()
    chrome_options.add_argument("--headless") 
    chrome_options.add_argument("--disable-gpu") 
    chrome_options.add_argument("--disable-dev-shm-usage") 
    chrome_options.accept_insecure_certs = True
    driver = webdriver.Chrome(options=chrome_options)
    driver.get(url)
    WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "table:nth-of-type(4)"))
        )
    
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
     table = driver.find_element(By.CSS_SELECTOR, "table:nth-of-type(4)")

     label = driver.find_element(By.XPATH, "//td[text()='Decision Date:']")
     value = label.find_element(By.XPATH, "following-sibling::td")
     decision_date = value.text.strip()

     #All the data needed is stored in this array
     entry = {
          "URL": url,
          "Name": driver.title.strip(), 
          "Version": version,
          "Decision": get_current_decision(table, version),
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
  finally:
     driver.quit()

def read_yml_file(filename):
     with open(filename, 'r') as file:
       data = yaml.safe_load(file)
       entries = data.get("trm_entries", [])
       return [(entry["tid"], entry["version"]) for entry in entries]
#Runs the code with a certain tid and version for testing
if __name__ == "__main__":
    results = []
    counter = 0
    #input_data = read_yml_file(r"C:\Users\abrahamn\.vscode\trm-compliance-check\files\trm_usage.yml")
    input_data = [(6367, "8.x"), (35, "2019")]
    for tid, version in input_data:
        try:
          result = fetch_data(tid, version)
          if result:
             results.append(result)
             counter+=1
             print(counter)
        except Exception as e:
           print(f"Error processing TID {tid} with version {version}: {e}")

    print(json.dumps(results, indent=2))