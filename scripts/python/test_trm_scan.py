import unittest
from unittest.mock import MagicMock, mock_open, patch
import yaml
import json
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, SessionNotCreatedException, WebDriverException

from project import check_decision_status
from project import generate_quarter_map
from project import get_current_quarter
from project import get_current_decision
from project import fetch_data

#This class is used to test the helper functions in my code
class TestTRMHelpers(unittest.TestCase):

    def test_check_decision_status_compliance(self):
        result = check_decision_status("Authorized", "1.0", "Authorized", "1.0")
        self.assertEqual(result, "InCompliance")

    def test_check_decision_status_divest(self):
        result = check_decision_status("Authorized", "1.0", "Authorized (DIVEST)", "1.0")
        result2 = check_decision_status("Authorized (DIVEST)", "1.0", "Authorized (DIVEST)", "1.0")
        self.assertEqual(result, "InDivest")
        self.assertEqual(result2, "InDivest")

    def test_check_decision_status_mismatch(self):
         result = check_decision_status("Authorized", "1.0", "Authorized [1, 2]", "1.0")
         self.assertIn("Decision Mismatch", result)

    def test_check_decision_status_unapproved(self):
        result = check_decision_status("Authorized", "1.0", "Authorized [1, 2]", "2.0")
        result2 = check_decision_status("Authorized", "1.0", "Authorized", "2.0")
        result3 = check_decision_status("Unapproved", "1.0", "Unapproved", "1.0")
        self.assertEqual(result, "Unapproved")
        self.assertEqual(result2, "Unapproved")
        self.assertEqual(result3, "Unapproved")


    def test_check_decision_status_blank(self):
        result = check_decision_status("", "", "", "")
        result2 = check_decision_status("", "1.0", "Authorized [1, 2]", "2.0")
        result3 = check_decision_status("Authorized", "", "Authorized [1, 2]", "2.0")
        result4 = check_decision_status("Authorized", "1.0", "", "2.0")
        result5 = check_decision_status("Authorized", "1.0", "Authorized [1, 2]", "")
        self.assertEqual(result, "Unapproved")
        self.assertEqual(result2, "Unapproved")
        self.assertEqual(result3, "Unapproved")
        self.assertEqual(result4, "Unapproved")
        self.assertEqual(result5, "Unapproved")

    def test_generate_quarter_map_structure(self):
        year = 2024
        qmap = generate_quarter_map(year)
        self.assertIn("CY2025 Q2", qmap)
        self.assertIn("CY2024 Q3", qmap)
        self.assertIn("CY2023 Q1", qmap)

    def test_quarter_format(self):
        year, quarter = get_current_quarter()
        self.assertIsInstance(year, int)
        self.assertTrue(quarter.startswith("Q"))
    def test_parse_yml_file_reads_data(self):
        mock_yaml = """
        trm_base_url: "https://example.com"
        trm_entries:
          - tid: "1234"
            version: "Win 10.x"
            name: "ToolX"
            decision: "Authorized"
        """
        with patch("builtins.open", mock_open(read_data=mock_yaml)):
            result = yaml.safe_load(mock_yaml)
            self.assertIn("trm_base_url", result)
            self.assertEqual(result["trm_entries"][0]["tid"], "1234")

    def test_json_file_write(self):
        mock_data = {"trm_base_url": "https://base.url", "trm_entries": []}
        json_report = json.dumps(mock_data, indent=2)

        with patch("builtins.open", mock_open()) as mocked_file:
            with open("trm_report.json", "w", encoding="utf-8") as f:
                f.write(json_report)

            mocked_file.assert_called_with("trm_report.json", "w", encoding="utf-8")
            mocked_file().write.assert_called_once_with(json_report)
            
    def test_html_file_write(self):
        mock_data = {"trm_base_url": "https://base.url", "trm_entries": []}
        json_report = json.dumps(mock_data, indent=2)

        with patch("builtins.open", mock_open()) as mocked_file:
            with open("trm_report.html", "w", encoding="utf-8") as f:
                f.write(json_report)

            mocked_file.assert_called_with("trm_report.html", "w", encoding="utf-8")
            mocked_file().write.assert_called_once_with(json_report)

#This class is used to test the functions that use the selenium WebDriver
class TestSeleniumFunctions(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        cls.driver = webdriver.Chrome(options=chrome_options)

    @classmethod
    def tearDownClass(cls):
        cls.driver.quit()

    def test_get_decision(self):
        url = "https://www.oit.va.gov/Services/TRM/ToolPage.aspx?tid=9952&tab=2"
        version = "Win 10.x"
        self.driver.get(url)
        decision = get_current_decision(self.driver, version)
        self.assertTrue("Authorized" in decision or "Decision Not Found" != decision)
    
    def test_get_decision_one_row(self):
        driver = MagicMock()
        table = MagicMock()
        table.find_elements.return_value = [MagicMock()]
        driver.find_element.return_value = table
        decision = get_current_decision(driver, version="Win 10.x", curr_year=2025, curr_quarter="Q2")
        self.assertTrue(decision == "Decision Not Found")

    

    def test_vaild_entry(self):
        url = "https://www.oit.va.gov/Services/TRM/ToolPage.aspx?tid=9952&tab=2"
        version = "Win 10.x"
        entry = fetch_data(self.driver, url, version)
        self.assertIsInstance(entry, dict)
        self.assertEqual(entry["Tid"], "9952")
        self.assertEqual(entry["Version"], version)
        self.assertTrue(entry["Name"])
        self.assertIn("Decision", entry)


    def test_invalid_entry(self):
        url = "https://www.oit.va.gov/Services/TRM/ToolPage.aspx?tid=9952&tab=2"
        version = "Win 21.x"
        entry = fetch_data(self.driver, url, version)
        self.assertTrue(entry["Decision"] == "Decision Not Found")
    
class TestFetchDataExceptions(unittest.TestCase):

    @patch("project.logging.error")
    @patch("project.WebDriverWait")
    def test_timeout_exception(self, mock_wait, mock_log):
     mock_driver = MagicMock()
     mock_driver.get.side_effect = TimeoutException("Simulated timeout")
     result = fetch_data(mock_driver, "https://example.com", "Win 10.x")
     self.assertIsNone(result)

       
    @patch("project.WebDriverWait")
    @patch("project.logging.error") 
    def test_connection_error(self, mock_log, mock_wait):
        mock_driver = MagicMock()
        mock_driver.get.side_effect = ConnectionError("Simulated connection error")

        result = fetch_data(mock_driver, "https://example.com", "Win 10.x")
        self.assertIsNone(result)


    @patch("project.WebDriverWait")
    @patch("project.logging.error") 
    def test_webdriver_error(self, mock_log, mock_wait):
        mock_driver = MagicMock()
        mock_driver.get.side_effect = WebDriverException("Simulated WebDriverException")

        result = fetch_data(mock_driver, "https://example.com", "Win 10.x")
        self.assertIsNone(result)

if __name__ == "__main__":
    unittest.main()