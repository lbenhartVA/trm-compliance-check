import requests
from bs4 import BeautifulSoup

def fetch_entry(tid):
  base_url = "https://trm.oit.va.gov/ToolPage.aspx"
  param = {"tid": tid, "tab": 2}
  headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"}
  resp = requests.get(base_url, params=param, headers=headers)
  resp.raise_for_status()
  return resp.text, resp.url

def parse_trm(html, url):
  soup = BeautifulSoup(html, "html.parser")
  entry = {}
  entry["name"] = soup.select_one("#ctl00$ContentPlaceHolder1$hdnToolName").get_text(strip =True)
  entry["tid"] = int(soup.select_one("#ctl00$ContentPlaceHolder1$hdnToolID").get_text(strip =True)) # Added .get_text()
  entry["decision"] = soup.select_one("#ctl00_ContentPlaceHolder1_lblDecision").get_text(strip =True)
  entry["verison"] = soup.select_one("#ctl00_ContentPlaceHolder1_lblVersion").get_text(strip =True)
  entry["approve_date"] = soup.select_one("#ctl00_ContentPlaceHolder1_lblApproveDate").get_text(strip =True)
  return {"trm_base_url": url.split("?")[0], "trm_entries":[entry]}

if __name__ == "__main__":
    tid = 6367
    html, url = fetch_entry(tid)
    entry = parse_trm(html, url)
    print(entry)