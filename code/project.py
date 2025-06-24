from selenium import webdriver
from selenium.webdriver.edge.service import Service 
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By
import json
import time

def fetch_data(tid):  
  url = f"https://www.oit.va.gov/Services/TRM/ToolPage.aspx?tid={tid}&tab2"
  path = "C:\\Users\\abrahamn\\.vscode\\trm-compliance-check\\msedgedriver.exe"
  options = Options()


  try:
     driver = webdriver.Edge(service=Service(path), options=options)
     driver.get(url)
     time.sleep(15)
     label = driver.find_element(By.XPATH, "//td[text()='Decision Date:']")
     value = label.find_element(By.XPATH, "following-sibling::td")
     entry = {
          "name": driver.title.strip(), 
          "tid": driver.find_element(By.ID, "ContentPlaceHolder1_hdnToolId").get_attribute("value"),
          "approval_date": value.text.split(" ")[0]
          }
     return {
     "trm_base_url": url.split("?")[0],
     "trm_entries":[entry]
     }
  finally:
     driver.quit()

if __name__ == "__main__":
    result = fetch_data(13552)
    print(json.dumps(result, indent=2))