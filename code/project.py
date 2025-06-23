from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
import json
import time

def fetch_data(tid):  
  url = f"https://www.oit.va.gov/Services/TRM/ToolPage.aspx?tid={tid}&tab2"
  
  options = webdriver.ChromeOptions()
  options.add_argument("--headless ")
  driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

  try:
     driver.get(url)
     time.sleep(3)
     entry = {
          "name": driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_hdnToolName").text, 
          "tid": driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_hdnToolID").text, 
          "decision": driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_hdnDecision").text,
          "version": driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_hdnVersion").text, 
          "approval_date": driver.find_element(By.ID, "ctl00_ContentPlaceHolder1_hdnDecisionDate").text
          }
     return {
     "trm_base_url": url.split("?")[0],
     "trm_entries":[entry]
     }
  finally:
     driver.quit()

if __name__ == "__main__":
    tid = 6367
    result = fetch_data(tid)
    print(json.dumps(result, indent=2))