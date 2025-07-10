import unittest

from selenium import webdriver
from selenium.webdriver.chrome.options import Options

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

if __name__ == "__main__":
    unittest.main()