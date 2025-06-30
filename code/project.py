from selenium import webdriver
from selenium.webdriver.edge.service import Service 
from selenium.webdriver.edge.options import Options
from selenium.webdriver.common.by import By
import json
import time
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import re

def fetch_data(tid):  
  url = f"https://www.oit.va.gov/Services/TRM/ToolPage.aspx?tid={tid}&tab2"
  path = "C:\\Users\\abrahamn\\.vscode\\trm-compliance-check\\msedgedriver.exe"
  options = Options()


  try:
     #Sets up the edgedriver
     driver = webdriver.Edge(service=Service(path), options=options)
     driver.get(url)
     time.sleep(30)

     #
     label = driver.find_element(By.XPATH, "//td[text()='Decision Date:']")
     value = label.find_element(By.XPATH, "following-sibling::td")
     f_table = driver.find_element(By.XPATH, "//table[.//a[text()='Past']]]")
     found = False
     decision = None
     a_decision = None
     if f_table:
        rows = f_table.find_elements(By.TAG_NAME, "tr")
        for row in rows:
           cells = row.find_elements(By.TAG_NAME ,"td")
           if not cells:
              continue
           version = cells[0].text.strip()
           for cell in cells:
              style = cell.get_attribute("style") or ""
              if "border-color: black" in style and "border-width: 2px" in style:
                 decision = cell.text.strip()
                 if "Authorized" in decision:
                    a_verison = version
                    a_decision = decision
                    found = True   
                    break
           if found:
              break

     entry = {
          "URL": url,
          "Name": driver.title.strip(), 
          "Tid": driver.find_element(By.ID, "ContentPlaceHolder1_hdnToolId").get_attribute("value"),
          "Version": a_verison,
          "Decision": a_decision,
          "Decision_Date": value.text.split(" ")[0]
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