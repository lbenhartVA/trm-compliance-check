import unittest
from unittest.mock import MagicMock, mock_open, patch, Mock
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, WebDriverException
from requests.exceptions import RequestException, Timeout
from project import check_decision_status
from project import generate_quarter_map
from project import get_current_quarter
from project import fetch_data
from project import find_next_valid_version
from project import is_url_valid
from project import get_all_version_decisions
from project import generate_report
from project import process_entry, INVALID_LINK_DECISION

# === Constants ===
CURR_YEAR, CURR_QUARTER = get_current_quarter()
QUARTER_MAP = generate_quarter_map(CURR_YEAR)

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

    self.assertIn("CY2025 Q2", QUARTER_MAP)
    self.assertIn("CY2024 Q3", QUARTER_MAP)
    self.assertIn("CY2026 Q1", QUARTER_MAP)

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


  def test_vaild_entry(self):
    url = "https://www.oit.va.gov/Services/TRM/ToolPage.aspx?tid=9952&tab=2"
    version = "Win 10.x"
    entry = fetch_data(self.driver, url, version, CURR_YEAR, CURR_QUARTER, QUARTER_MAP)
    self.assertIsInstance(entry, dict)
    self.assertEqual(entry["Tid"], "9952")
    self.assertEqual(entry["Version"], version)
    self.assertTrue(entry["Name"])
    self.assertIn("Decision", entry)


  def test_invalid_entry(self):
    url = "https://www.oit.va.gov/Services/TRM/ToolPage.aspx?tid=9952&tab=2"
    version = "Win 21.x"
    entry = fetch_data(self.driver, url, version, CURR_YEAR, CURR_QUARTER, QUARTER_MAP)
    self.assertTrue(entry["Decision"] == "Decision Not Found")

  def test_invalid_current_version(self):
    result = find_next_valid_version("abc", [("2.0", "Authorized")])
    self.assertEqual(result, (None, None))

  def test_skips_invalid_versions_in_map(self):
    version_map = [
      ("abc", "Authorized"),
      ("1.5", "Authorized"),
      ("bad.version", "Authorized")
    ]
    result = find_next_valid_version("1.0", version_map)
    self.assertEqual(result, ("1.5", "Authorized"))

  def test_valid_versions_sorted(self):
    version_map = [
      ("1.0", "Authorized"),
      ("2.0", "Authorized"),
      ("3.0", "Authorized")
    ]
    current = "1.0"
    result = find_next_valid_version(current, version_map)
    self.assertEqual(result, ("1.0", "Authorized"))

  def test_skips_divest_and_poam(self):
    version_map = [
      ("1.0", "Authorized"),
      ("2.0", "DIVEST"),
      ("3.0", "POA&M"),
      ("4.0", "Authorized")
      ]
    current = "1.0"
    result = find_next_valid_version(current, version_map)
    self.assertEqual(result, ("1.0", "Authorized"))

  def test_no_authorized_version_found(self):
    version_map = [
      ("2.0", "DIVEST"),
      ("3.0", "Unapproved")
    ]
    result = find_next_valid_version("1.0", version_map)
    self.assertEqual(result, (None, None))

class TestFetchDataExceptions(unittest.TestCase):
  @patch("project.logging.error")
  @patch("project.WebDriverWait")
  def test_timeout_exception(self, mock_wait, mock_log):
    mock_driver = MagicMock()
    mock_driver.get.side_effect = TimeoutException("Simulated timeout")
    result = fetch_data(mock_driver, "https://example.com", "Win 10.x", CURR_YEAR, CURR_QUARTER, QUARTER_MAP)
    self.assertIsNone(result)

  @patch("project.WebDriverWait")
  @patch("project.logging.error")
  def test_connection_error(self, mock_log, mock_wait):
    mock_driver = MagicMock()
    mock_driver.get.side_effect = ConnectionError("Simulated connection error")
    result = fetch_data(mock_driver, "https://example.com", "Win 10.x", CURR_YEAR, CURR_QUARTER, QUARTER_MAP)
    self.assertIsNone(result)

  @patch("project.WebDriverWait")
  @patch("project.logging.error")
  def test_webdriver_error(self, mock_log, mock_wait):
    mock_driver = MagicMock()
    mock_driver.get.side_effect = WebDriverException("Simulated WebDriverException")
    result = fetch_data(mock_driver, "https://example.com", "Win 10.x", CURR_YEAR, CURR_QUARTER, QUARTER_MAP)
    self.assertIsNone(result)


class TestIsUrlValid(unittest.TestCase):

  @patch("project.requests.get")
  def test_valid_response(self, mock_get):
    mock_response = Mock(status_code=200, text="All good here")
    mock_get.return_value = mock_response

    result = is_url_valid("http://example.com")
    self.assertTrue(result)

  @patch("project.requests.get")
  def test_invalid_status_code(self, mock_get):
    mock_response = Mock(status_code=404, text="Page not found")
    mock_get.return_value = mock_response

    result = is_url_valid("http://example.com")
    self.assertFalse(result)

  @patch("project.requests.get")
  def test_error_message_in_text(self, mock_get):
    mock_response = Mock(status_code=200, text="The Entry you are looking for is invalid")
    mock_get.return_value = mock_response

    result = is_url_valid("http://example.com")
    self.assertFalse(result)

  @patch("project.requests.get")
  def test_request_exception(self, mock_get):
    mock_get.side_effect = RequestException("Connection error")
    result = is_url_valid("http://example.com")
    self.assertFalse(result)

  @patch("project.requests.get")
  def test_timeout_exception(self, mock_get):
    mock_get.side_effect = Timeout("Request timed out")
    result = is_url_valid("http://example.com")
    self.assertFalse(result)


class TestGetAllVersionDecisions(unittest.TestCase):

  def setUp(self):
    # Sample header setup
    self.quarter_map = {"CY2025 Q3": 2}

  def mock_table_structure(self, cell_matrix):
    """
    Mocks a table with tr elements and td elements.
    cell_matrix is a list of rows, each containing a list of cell texts.
    """
    row_mocks = []
    for row in cell_matrix:
      cell_mocks = []
      for cell_text in row:
        cell = Mock()
        cell.text = cell_text
        cell_mocks.append(cell)
        row = Mock()
        row.find_elements.return_value = cell_mocks
        row_mocks.append(row)
    return row_mocks

  def test_missing_column(self):
    driver = Mock()
    driver.find_element.return_value.find_elements.return_value = []
    bad_quarter_map = {"CY2025 Q3": None}

    result = get_all_version_decisions(driver, 2025, "Q3", bad_quarter_map)
    self.assertEqual(result, [])

  def test_insufficient_rows(self):
    driver = Mock()
    table = Mock()
    driver.find_element.return_value = table
    table.find_elements.return_value = self.mock_table_structure([["Header"]])  # Only 1 row

    result = get_all_version_decisions(driver, 2025, "Q3", self.quarter_map)
    self.assertEqual(result, [])

  def test_column_index_out_of_bounds(self):
    driver = Mock()
    table = Mock()
    driver.find_element.return_value = table
    # All rows have fewer columns than col_index
    table.find_elements.return_value = self.mock_table_structure([
      ["Header1", "Header2"],
      ["Subheader1", "Subheader2"],
      ["1.0"],  # Missing col_index
      ["2.5"]   # Missing col_index
    ])

    result = get_all_version_decisions(driver, 2025, "Q3", self.quarter_map)
    self.assertEqual(result, [])

class TestGenerateReport(unittest.TestCase):

  @patch("project.webdriver.Chrome")
  @patch("project.Environment")
  @patch("project.yaml.safe_load")
  @patch("project.open", new_callable=mock_open)
  @patch("project.Path")
  @patch("project.json.dumps")
  @patch("project.process_entry")
  @patch("project.get_current_quarter", return_value=(2025, "Q3"))
  @patch("project.generate_quarter_map", return_value={"CY2025 Q3": 2})
  def test_generate_report_successful(
    self, mock_quarter, mock_map, mock_process_entry, mock_dumps,
    mock_path, mock_open_fn, mock_yaml, mock_env, mock_chrome
    ):
      # Setup YAML data
    mock_yaml.return_value = {
      "trm_base_url": "http://example.com",
      "trm_entries": [
        {"tid": "001", "version": "1.0", "name": "ToolA", "decision": "Unapproved", "approval_date": "2025-01-01"}
        ]
    }

    # Simulate a processed result
    mock_process_entry.return_value = {
      "Tid": "001", "Version": "1.0", "Decision": "Unapproved", "Status": "Unapproved"
    }

    # Mock template rendering
    mock_template = MagicMock()
    mock_template.render.return_value = "<html>Report</html>"
    mock_env.return_value.get_template.return_value = mock_template

    # Run function
    generate_report()

    # Check that report was rendered and written
    mock_template.render.assert_called()

    mock_open_fn.assert_any_call("trm_report.json", "w", encoding="utf-8")
    mock_open_fn.assert_any_call("trm_report.html", "w", encoding="utf-8")
    mock_dumps.assert_called_once()
    mock_process_entry.assert_called_once()

class TestProcessEntry(unittest.TestCase):

  def setUp(self):
    self.driver = Mock()
    self.base_url = "http://example.com"
    self.tid = "123"
    self.version = "1.0"
    self.name = "Tool A"
    self.decision = "Unapproved"
    self.year = 2025
    self.quarter = "Q3"
    self.q_map = {"CY2025 Q3": 2}

  @patch("project.is_url_valid", return_value=False)
  def test_invalid_url(self, mock_url_check):
    result = process_entry(self.driver, self.base_url, self.tid, self.version, self.name,
                           self.decision, self.year, self.quarter, self.q_map)
    expected_url = f"{self.base_url}?tid={self.tid}&tab=2"
    self.assertEqual(result["URL"], expected_url)
    self.assertEqual(result["Decision"], INVALID_LINK_DECISION)
    self.assertEqual(result["Status"], "Unapproved")
    self.assertEqual(result["Next Approved Version"], "None Found")

  @patch("project.is_url_valid", return_value=True)
  @patch("project.fetch_data", return_value=None)
  def test_fetch_data_none(self, mock_fetch, mock_url_check):
    result = process_entry(self.driver, self.base_url, self.tid, self.version, self.name,
                            self.decision, self.year, self.quarter, self.q_map)
    self.assertIsNone(result)

  @patch("project.is_url_valid", return_value=True)
  @patch("project.fetch_data")
  @patch("project.get_all_version_decisions")
  @patch("project.find_next_valid_version", return_value=("2.0", "Authorized"))
  @patch("project.check_decision_status", return_value="Unapproved")
  def test_unapproved_decision_path(self, mock_status, mock_next_version,
                                     mock_get_versions, mock_fetch, mock_url_check):
    mock_fetch.return_value = {
      "URL": f"{self.base_url}?tid={self.tid}&tab=2",
      "Name": self.name,
      "Tid": self.tid,
      "Version": self.version,
      "Decision": "Unapproved",
      "Decision Date": "2025-01-01"
      }

    result = process_entry(self.driver, self.base_url, self.tid, self.version, self.name,
                               self.decision, self.year, self.quarter, self.q_map)

    self.assertEqual(result["Status"], "Unapproved")
    self.assertEqual(result["Next Approved Version"], "2.0\n Authorized")

  @patch("project.is_url_valid", return_value=True)
  @patch("project.fetch_data")
  @patch("project.check_decision_status", return_value="InCompliance")
  def test_compliant_decision_no_next_version(self, mock_status, mock_fetch, mock_url_check):
    mock_fetch.return_value = {
      "URL": f"{self.base_url}?tid={self.tid}&tab=2",
      "Name": self.name,
      "Tid": self.tid,
      "Version": self.version,
      "Decision": "Authorized",
      "Decision Date": "2025-01-01"
    }

    result = process_entry(self.driver, self.base_url, self.tid, self.version, self.name,
                               self.decision, self.year, self.quarter, self.q_map)

    self.assertEqual(result["Status"], "InCompliance")
    self.assertNotIn("Next Approved Version", result)


if __name__ == "__main__":
  unittest.main()