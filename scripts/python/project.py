from selenium import webdriver
from selenium.webdriver.common.by import By
import json
import time
from datetime import datetime
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException, SessionNotCreatedException, TimeoutException, StaleElementReferenceException, NoSuchElementException

def get_current_quarter():
   now = datetime.now()
   current_year = now.year
   current_quarter = f"Q{(now.month - 1) // 3 + 1}"
   return current_year, current_quarter

def fetch_data(tid, version):  
  url = f"https://www.oit.va.gov/Services/TRM/ToolPage.aspx?tid={tid}&tab2"
  

  try:
    chrome_options = Options()
    chrome_options.accept_insecure_certs = True
    driver = webdriver.Chrome(options=chrome_options)
    driver.get(url)
    WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "table:nth-of-type(4)"))
        )
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
     
     table = driver.find_element(By.CSS_SELECTOR, "table:nth-of-type(4)")
     rows = table.find_elements(By.CSS_SELECTOR, "tbody tr")
     decision_date_path = driver.find_element(By.XPATH, "//td[text()='Decision Date:']")
     decision_date = decision_date_path.find_element(By.XPATH, "following-sibling::td")
     decision = None
     
     entry = {
          "URL": url,
          "Name": driver.title.strip(), 
          "Tid": driver.find_element(By.ID, "ContentPlaceHolder1_hdnToolId").get_attribute("value"),
          "Version": version,
          "Decision": decision,
          "Decision_Date": decision_date.text.split(" ")[0]
          }
     return {
     "trm_base_url": url.split("?")[0],
     "trm_entries":[entry]
     }
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

if __name__ == "__main__":
    result = fetch_data(6367, "8.x")
    print(json.dumps(result, indent=2))