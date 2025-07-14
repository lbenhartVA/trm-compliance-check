import unittest
from unittest.mock import MagicMock, patch

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

    def test_check_decision_status_compliance(test):
        result = check_decision_status("Authorized", "1.0", "Authorized", "1.0")
        test.assertEqual(result, "InCompliance")

    def test_check_decision_status_divest(test):
        result = check_decision_status("Authorized", "1.0", "Authorized (DIVEST)", "1.0")
        result2 = check_decision_status("Authorized (DIVEST)", "1.0", "Authorized (DIVEST)", "1.0")
        test.assertEqual(result, "InDivest")
        test.assertEqual(result2, "InDivest")

    def test_check_decision_status_mismatch(test):
         result = check_decision_status("Authorized", "1.0", "Authorized [1, 2]", "1.0")
         test.assertIn("Decision Mismatch", result)

    def test_check_decision_status_unapproved(test):
        result = check_decision_status("Authorized", "1.0", "Authorized [1, 2]", "2.0")
        result2 = check_decision_status("Authorized", "1.0", "Authorized", "2.0")
        test.assertEqual(result, "Unapproved")
        test.assertEqual(result2, "Unapproved")

    def test_check_decision_status_blank(test):
        result = check_decision_status("", "", "", "")
        result2 = check_decision_status("", "1.0", "Authorized [1, 2]", "2.0")
        result3 = check_decision_status("Authorized", "", "Authorized [1, 2]", "2.0")
        result4 = check_decision_status("Authorized", "1.0", "", "2.0")
        result5 = check_decision_status("Authorized", "1.0", "Authorized [1, 2]", "")
        test.assertEqual(result, "Unapproved")
        test.assertEqual(result2, "Unapproved")
        test.assertEqual(result3, "Unapproved")
        test.assertEqual(result4, "Unapproved")
        test.assertEqual(result5, "Unapproved")

    def test_generate_quarter_map_structure(test):
        year = 2024
        qmap = generate_quarter_map(year)
        test.assertIn("CY2025 Q2", qmap)
        test.assertIn("CY2024 Q3", qmap)
        test.assertIn("CY2023 Q1", qmap)

    def test_quarter_format(test):
        year, quarter = get_current_quarter()
        test.assertIsInstance(year, int)
        test.assertTrue(quarter.startswith("Q"))

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

    def test_get_decision(test):
        url = "https://www.oit.va.gov/Services/TRM/ToolPage.aspx?tid=9952&tab=2"
        version = "Win 10.x"
        test.driver.get(url)
        decision = get_current_decision(test.driver, version)
        test.assertTrue("Authorized" in decision or "Decision Not Found" != decision)
    
    def test_get_decision_one_row(test):
        driver = MagicMock()
        table = MagicMock()
        table.find_elements.return_value = [MagicMock()]
        driver.find_element.return_value = table
        decision = get_current_decision(driver, version="Win 10.x", curr_year=2025, curr_quarter="Q2")
        test.assertTrue(decision == "Decision Not Found")

    

    def test_vaild_entry(test):
        url = "https://www.oit.va.gov/Services/TRM/ToolPage.aspx?tid=9952&tab=2"
        version = "Win 10.x"
        entry = fetch_data(test.driver, url, version)
        test.assertIsInstance(entry, dict)
        test.assertEqual(entry["Tid"], "9952")
        test.assertEqual(entry["Version"], version)
        test.assertTrue(entry["Name"])
        test.assertIn("Decision", entry)


    def test_invalid_entry(test):
        url = "https://www.oit.va.gov/Services/TRM/ToolPage.aspx?tid=9952&tab=2"
        version = "Win 21.x"
        entry = fetch_data(test.driver, url, version)
        test.assertTrue(entry["Decision"] == "Decision Not Found")
    
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

    @patch("project.SessionNotCreatedException")
    @patch("project.logging.error") 
    def test_session_not_found(self, mock_log, mock_wait):
        mock_driver = MagicMock()
        mock_driver.get.side_effect = SessionNotCreatedException("Simulated SessionNotCreatedException")

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