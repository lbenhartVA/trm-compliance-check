from selenium import webdriver
from selenium.webdriver.edge.service import Service 
from selenium.webdriver.common.by import By
import json
import time
from datetime import datetime
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import WebDriverException, SessionNotCreatedException, TimeoutException, StaleElementReferenceException, NoSuchElementException

def get_current_quarter():
   now = datetime.now()
   current_year = now.year
   current_quarter = f"Q{(now.month - 1) // 3 + 1}"
   current_year, current_quarter

def fetch_data(tid):  
  url = f"https://www.oit.va.gov/Services/TRM/ToolPage.aspx?tid={tid}&tab2"
  

  try:
     driver = webdriver.Chrome(service= Service(ChromeDriverManager().install()))
     driver.get(url)
     time.sleep(30)
  except (ConnectionError, WebDriverException, TimeoutException, SessionNotCreatedException) as e:
     print("failed to download edgedriver using webdriver-manager:")
     print(e)
     return
  try:
     
     #
     decision_date_path = driver.find_element(By.XPATH, "//td[text()='Decision Date:']")
     decision_date = decision_date_path.find_element(By.XPATH, "following-sibling::td")
     
     table = driver.find_element(By.CSS_SELECTOR, "table:nth-of-type(4)")
     
     decision = None
     verison = None
     #decision = driver.find_element(By.CSS_SELECTOR, "table:nth-of-type(4) tbody tr:nth-of-type(2) td:nth-of-type(5)").text
     #verison = driver.find_element(By.CSS_SELECTOR, "table:nth-of-type(4) thead tr:nth-of-type(5) th:nth-of-type(7)").text
     entry = {
          "URL": url,
          "Name": driver.title.strip(), 
          "Tid": driver.find_element(By.ID, "ContentPlaceHolder1_hdnToolId").get_attribute("value"),
          "Version": verison,
          "Decision": decision,
          "Decision_Date": decision_date.text.split(" ")[0]
          }
     return {
     "trm_base_url": url.split("?")[0],
     "trm_entries":[entry]
     }
  except(NoSuchElementException, TimeoutException, StaleElementReferenceException):
     print("Error locating or interactinng with the page elements")
  finally:
     driver.quit()

if __name__ == "__main__":
    result = fetch_data(6367)
    print(json.dumps(result, indent=2))