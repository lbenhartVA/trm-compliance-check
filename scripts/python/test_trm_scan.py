import unittest
from unittest.mock import patch, MagicMock, Mock, mock_open
from requests.exceptions import  Timeout, ConnectionError
from selenium.webdriver import Chrome, ChromeOptions
from selenium.common.exceptions import (
    WebDriverException,
    TimeoutException
)
from project import (
    check_decision_status,
    generate_quarter_map,
    get_current_quarter,
    fetch_data,
    find_next_valid_version,
    is_url_valid,
    get_all_version_decisions,
    process_entry,
    generate_report,
    INVALID_LINK_DECISION
    )


# === Setup Global Context ===
CURR_YEAR, CURR_QUARTER = get_current_quarter()
QUARTER_MAP = generate_quarter_map(CURR_YEAR)

# === Helper Function Tests ===
class TestTRMHelpers(unittest.TestCase):
  """Tests helper logic for decision status and quarter mapping."""

  def test_in_compliance(self):
    self.assertEqual(check_decision_status("Authorized", "1.0", "Authorized", "1.0"), "InCompliance")

  def test_divest_status(self):
    self.assertEqual(check_decision_status("Authorized", "1.0", "Authorized (DIVEST)", "1.0"), "InDivest")
    self.assertEqual(check_decision_status("Authorized (DIVEST)", "1.0", "Authorized (DIVEST)", "1.0"), "InDivest")

  def test_mismatched_decisions(self):
    result = check_decision_status("Authorized", "1.0", "Authorized [1, 2]", "1.0")
    self.assertIn("Decision Mismatch", result)

  def test_unapproved_cases(self):
    cases = [
      ("Authorized", "1.0", "Authorized [1, 2]", "2.0"),
      ("Authorized", "1.0", "Authorized", "2.0"),
      ("Unapproved", "1.0", "Unapproved", "1.0")
    ]

    for c in cases:
      self.assertEqual(check_decision_status(*c), "Unapproved")

  def test_blank_fields(self):
    blanks = [
      ("", "", "", ""),
      ("", "1.0", "Authorized [1, 2]", "2.0"),
      ("Authorized", "", "Authorized [1, 2]", "2.0"),
      ("Authorized", "1.0", "", "2.0"),
      ("Authorized", "1.0", "Authorized [1, 2]", "")
    ]

    for case in blanks:
      self.assertEqual(check_decision_status(*case), "Unapproved")

  def test_quarter_map_contents(self):
    self.assertIn("CY2025 Q2", QUARTER_MAP)
    self.assertIn("CY2024 Q3", QUARTER_MAP)
    self.assertIn("CY2026 Q1", QUARTER_MAP)

# === Selenium Integration Tests ===
class TestSeleniumFunctions(unittest.TestCase):
  """Tests fetch logic and version compliance using live Chrome headless driver."""

  @classmethod
  def setUpClass(cls):
    options = ChromeOptions()
    options.add_argument("--headless")
    cls.driver = Chrome(options=options)

  @classmethod
  def tearDownClass(cls):
    cls.driver.quit()

  def test_valid_entry_fetch(self):
    entry = fetch_data(self.driver, "https://www.oit.va.gov/Services/TRM/ToolPage.aspx?tid=9952&tab=2", "Linux 1.8")
    self.assertIsInstance(entry, dict)
    self.assertEqual(entry["Tid"], "9952")
    self.assertEqual(entry["Version"], "Linux 1.8")
    self.assertTrue(entry["Name"])
    self.assertIn("Decision", entry)

  def test_invalid_entry_fetch(self):
    entry = fetch_data(self.driver, "https://www.oit.va.gov/Services/TRM/ToolPage.aspx?tid=9952&tab=2", "Win 21.x")
    self.assertEqual(entry["Decision"], "Decision Not Found")

  def test_version_parsing_and_fallback(self):
    result = find_next_valid_version("abc", [("2.0", "Authorized")])
    self.assertEqual(result, ("2.0", "Authorized"))

  def test_skips_bad_versions(self):
    version_map = [("abc", "Authorized"), ("1.5", "Authorized"), ("bad.version", "Authorized")]
    self.assertEqual(find_next_valid_version("1.0", version_map), ("1.5", "Authorized"))

  def test_valid_versions_are_sorted(self):
    version_map = [("1.0", "Authorized"), ("2.0", "Authorized"), ("3.0", "Authorized")]
    self.assertEqual(find_next_valid_version("1.0", version_map), ("2.0", "Authorized"))

  def test_divest_and_poam_are_skipped(self):
    version_map = [("1.0", "Authorized"), ("2.0", "DIVEST"), ("3.0", "POA&M"), ("4.0", "Authorized")]
    self.assertEqual(find_next_valid_version("1.0", version_map), ("4.0", "Authorized"))

  def test_no_approved_versions(self):
    version_map = [("2.0", "DIVEST"), ("3.0", "Unapproved")]
    self.assertEqual(find_next_valid_version("1.0", version_map), (None, None))


# === Exception Handling Tests ===
class TestFetchDataExceptions(unittest.TestCase):
  """Tests error handling during fetch_data execution."""

  @patch("project.logging.error")
  @patch("project.WebDriverWait")
  def test_timeout(self, mock_wait, mock_log):
    mock_driver = MagicMock()
    mock_driver.get.side_effect = TimeoutException("Timeout")
    self.assertIsNone(fetch_data(mock_driver, "https://example.com", "Win 10.x"))

  @patch("project.WebDriverWait")
  @patch("project.logging.error")
  def test_connection_failure(self, mock_log, mock_wait):
    mock_driver = MagicMock()
    mock_driver.get.side_effect = WebDriverException("Simulated connection error")
    self.assertIsNone(fetch_data(mock_driver, "https://example.com", "Win 10.x"))

  @patch("project.WebDriverWait")
  @patch("project.logging.error")
  def test_webdriver_failure(self, mock_log, mock_wait):
    mock_driver = MagicMock()
    mock_driver.get.side_effect = WebDriverException("WebDriver error")
    self.assertIsNone(fetch_data(mock_driver, "https://example.com", "Win 10.x"))



# === URL Validation Tests ===
class TestIsUrlValid(unittest.TestCase):
  """Tests for validating TRM URLs."""

  @patch("project.requests.get")
  def test_valid_status(self, mock_get):
    mock_get.return_value = Mock(status_code=200, text="OK")
    self.assertTrue(is_url_valid("http://example.com"))

  @patch("project.requests.get")
  def test_404_status(self, mock_get):
    mock_get.return_value = Mock(status_code=404, text="Not Found")
    self.assertFalse(is_url_valid("http://example.com"))

  @patch("project.requests.get")
  def test_invalid_entry_text(self, mock_get):
    mock_get.return_value = Mock(status_code=200, text="The Entry you are looking for is invalid")
    self.assertFalse(is_url_valid("http://example.com"))

  @patch("project.requests.get")
  def test_connection_error(self, mock_get):
    mock_get.side_effect = ConnectionError("Connection error")
    self.assertFalse(is_url_valid("http://example.com"))

  @patch("project.requests.get")
  def test_timeout(self, mock_get):
    mock_get.side_effect = Timeout("Request timed out")
    self.assertFalse(is_url_valid("http://example.com"))

# === Quarter Map Parsing Tests ===
class TestGetAllVersionDecisions(unittest.TestCase):
  """Tests parsing version decisions from TRM tables."""

  def setUp(self):
    self.mock_map = {"CY2025 Q3": 2}

  def mock_table_structure(self, rows):
    mocks = []
    for row_cells in rows:
      cells = [Mock(text=txt) for txt in row_cells]
      row = Mock()
      row.find_elements.return_value = cells
      mocks.append(row)
    return mocks

  def test_missing_column_index(self):
    driver = Mock()
    driver.find_element.return_value.find_elements.return_value = []
    result = get_all_version_decisions(driver)
    self.assertEqual(result, [])

  def test_table_too_short(self):
    driver = Mock()
    driver.find_element.return_value.find_elements.return_value = self.mock_table_structure([["Header"]])
    result = get_all_version_decisions(driver)
    self.assertEqual(result, [])

  def test_column_index_out_of_bounds(self):
    driver = Mock()
    table = Mock()
    table.find_elements.return_value = self.mock_table_structure([
      ["Header1", "Header2"],
      ["Subheader1", "Subheader2"],
      ["1.0"],  # no decision column
      ["2.5"]   # no decision column
    ])
    driver.find_element.return_value = table
    result = get_all_version_decisions(driver)
    self.assertEqual(result, [])

# === Report Genreration Tests ===
class TestGenerateReport(unittest.TestCase):
  """Ensures the report generation flow completes and writes output files correctly."""

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
        mock_path, mock_open_fn, mock_yaml, mock_env, mock_chrome):
    # Mock TRM data input
    mock_yaml.return_value = {
      "trm_base_url": "http://example.com",
      "trm_entries": [{
          "tid": "001",
          "version": "1.0",
          "name": "ToolA",
          "decision": "Unapproved",
          "approval_date": "2025-01-01"
          }]
        }

    # Simulate processed output
    mock_process_entry.return_value = {
        "Tid": "001",
        "Version": "1.0",
        "Decision": "Unapproved",
        "Status": "Unapproved"
      }

    # Mock template rendering
    mock_template = MagicMock()
    mock_template.render.return_value = "<html>Report</html>"
    mock_env.return_value.get_template.return_value = mock_template

    # Run report generation
    generate_report()

    # Assertions to verify behavior
    mock_template.render.assert_called()
    mock_open_fn.assert_any_call("trm_report.json", "w", encoding="utf-8")
    mock_open_fn.assert_any_call("trm_report.html", "w", encoding="utf-8")
    mock_process_entry.assert_called_once()

# === Entry Processing Tests ===
class TestProcessEntry(unittest.TestCase):
  """Validates the behavior of processing TRM tool entries."""

  def setUp(self):
    self.driver = Mock()
    self.base_url = "http://example.com"
    self.tid = "123"
    self.version = "1.0"
    self.name = "Tool A"
    self.decision = "Unapproved"

  @patch("project.is_url_valid", return_value=False)
  def test_invalid_url(self, mock_url_check):
    result = process_entry(self.driver, self.base_url, self.tid, self.version, self.name, self.decision)
    expected_url = f"{self.base_url}?tid={self.tid}&tab=2"
    self.assertEqual(result["URL"], expected_url)
    self.assertEqual(result["Decision"], INVALID_LINK_DECISION)
    self.assertEqual(result["Status"], "Unapproved")
    self.assertEqual(result["Next Approved Version"], "None Found")

  @patch("project.is_url_valid", return_value=True)
  @patch("project.fetch_data", return_value=None)
  def test_fetch_data_returns_none(self, mock_fetch, mock_url_check):
    result = process_entry(self.driver, self.base_url, self.tid, self.version, self.name, self.decision)
    self.assertIsNone(result)

  @patch("project.is_url_valid", return_value=True)
  @patch("project.fetch_data")
  @patch("project.get_all_version_decisions")
  @patch("project.find_next_valid_version", return_value=("2.0", "Authorized"))
  @patch("project.check_decision_status", return_value="Unapproved")
  def test_unapproved_path_adds_next_version(
        self, mock_status, mock_next_version, mock_get_versions, mock_fetch, mock_url_check):
    mock_fetch.return_value = {
      "URL": f"{self.base_url}?tid={self.tid}&tab=2",
      "Name": self.name,
      "Tid": self.tid,
      "Version": self.version,
      "Decision": "Unapproved",
      "Decision Date": "2025-01-01"
    }

    result = process_entry(self.driver, self.base_url, self.tid, self.version, self.name, self.decision)
    self.assertEqual(result["Status"], "Unapproved")
    self.assertEqual(result["Next Approved Version"], "2.0\n Authorized")

  @patch("project.is_url_valid", return_value=True)
  @patch("project.fetch_data")
  @patch("project.check_decision_status", return_value="InCompliance")
  def test_compliant_path_skips_next_version(self, mock_status, mock_fetch, mock_url_check):
    mock_fetch.return_value = {
      "URL": f"{self.base_url}?tid={self.tid}&tab=2",
      "Name": self.name,
      "Tid": self.tid,
      "Version": self.version,
      "Decision": "Authorized",
      "Decision Date": "2025-01-01"
      }

    result = process_entry(self.driver, self.base_url, self.tid, self.version, self.name, self.decision)
    self.assertEqual(result["Status"], "InCompliance")
    self.assertNotIn("Next Approved Version", result)

# === Main Function ===
if __name__ == "__main__":
  unittest.main()
