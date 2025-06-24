from selenium import webdriver
from selenium.webdriver.edge.service import Service 
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By
import json
import time
import os

def fetch_data(tid):  
  url = f"https://www.oit.va.gov/Services/TRM/ToolPage.aspx?tid={tid}&tab2"
  path = "C:\\Users\\abrahamn\\.vscode\\trm-compliance-check\\msedgedriver.exe"
  options = Options()


  try:
     driver = webdriver.Edge(service=Service(path), options=options)
     driver.get(url)
     time.sleep(3)

     entry = {
          "name": driver.find_element(By.ID, "ContentPlaceHolder1_hdnToolName").text, 
          "tid": int(driver.find_element(By.ID, "ContentPlaceHolder1_hdnToolID").text), 
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
    result = fetch_data(6367)
    print(json.dumps(result, indent=2))