# Testing Framework for Supplement Recommender Chatbot

This folder contains the testing framework for evaluating the chatbot's performance against a golden dataset.

## Folder Structure

```
tests/
├── safety/              # Safety check test cases
│   ├── golden_dataset_safety.csv
│   └── safety_testing.md
├── recommendation/      # Recommendation test cases
│   ├── golden_dataset_recommendation.csv
│   └── recommendation_testing.md
├── deficiency/          # Deficiency analysis test cases
│   ├── golden_dataset_deficiency.csv
│   └── deficiency_testing.md
├── multi_agent_tests/   # Tests requiring multiple agent types
│   ├── golden_dataset_multi_agent_tests.csv
│   └── multi_agent_tests_testing.md
├── test_reports/        # Generated test reports (output)
│   ├── safety/          # Safety test reports
│   ├── recommendation/  # Recommendation test reports
│   ├── deficiency/      # Deficiency test reports
│   └── multi_agent_tests/ # Multi-agent test reports
├── test_runner.py       # Main test runner script
└── testing.md          # This file
```

## Files

- **`test_runner.py`**: Main test runner script that executes tests and calculates accuracy
- **`testing.md`**: This file
- **Test datasets**: CSV files organized by test type in their respective folders
- **Test reports**: Generated reports saved in `test_reports/` folder

## Golden Dataset Format

The `golden_dataset.csv` file contains the following columns:

- `test_id`: Unique identifier for the test case
- `user_question`: The question the user asks
- `medications`: Comma-separated list of medications (e.g., "Warfarin,Digoxin")
- `supplements`: Comma-separated list of current supplements
- `conditions`: Comma-separated list of medical conditions
- `dietary_restrictions`: Comma-separated list of dietary restrictions (e.g., "Vegan,Vegetarian")
- `expected_output_keywords`: Pipe-separated keywords that should appear in the answer (e.g., "caution|warning|interaction")
- `expected_supplements`: Comma-separated list of supplement names that should be mentioned
- `test_type`: Type of test (e.g., "safety", "recommendation", "deficiency")
- `description`: Brief description of what the test validates

## Running Tests

### Run Tests by Dataset Name

The test runner now supports running tests by dataset name. It will automatically look in the appropriate folder based on the test type.

```bash
# Run safety tests
python tests/test_runner.py --dataset golden_dataset --test-type safety

# Run recommendation tests
python tests/test_runner.py --dataset golden_dataset --test-type recommendation

# Run deficiency tests
python tests/test_runner.py --dataset golden_dataset --test-type deficiency

# Run multi-agent tests
python tests/test_runner.py --dataset golden_dataset --test-type multi_agent_tests
```

If you don't specify `--test-type`, the runner will try to infer it from the dataset name (e.g., "safety_dataset" → safety folder).

### Run with Custom Dataset Path

You can also specify a direct path to a CSV file:

```bash
python tests/test_runner.py --dataset-path tests/safety/my_custom_dataset.csv
```

### Run a Specific Test

```bash
python tests/test_runner.py --dataset golden_dataset --test-type safety --test-id 1
```

### Output Location

Reports are automatically saved to `tests/test_reports/{test_type}/` with a timestamp and test type:
- `test_report_{test_type}_{timestamp}.txt` - Human-readable report
- `test_report_{test_type}_{timestamp}.json` - Machine-readable JSON results

For example:
- Safety tests → `test_reports/safety/test_report_safety_20240101_120000.txt`
- Recommendation tests → `test_reports/recommendation/test_report_recommendation_20240101_120000.txt`
- Deficiency tests → `test_reports/deficiency/test_report_deficiency_20240101_120000.txt`
- Multi-agent tests → `test_reports/multi_agent_tests/test_report_multi_agent_tests_20240101_120000.txt`

You can also specify a custom output path:

```bash
python tests/test_runner.py --dataset golden_dataset --test-type safety --output custom_report.txt
```

## Accuracy Calculation

The test runner calculates accuracy in three ways:

1. **Keyword Accuracy**: Percentage of expected keywords found in the actual output
   - Keywords are matched case-insensitively
   - Partial matches are allowed (e.g., "bleeding" matches "bleeding risk")

2. **Supplement Accuracy**: Percentage of expected supplements mentioned
   - Flexible matching (e.g., "CoQ10" matches "Coenzyme Q10")
   - Checks for all significant words in multi-word supplement names

3. **Overall Accuracy**: Weighted average
   - 60% keyword accuracy + 40% supplement accuracy
   - If no supplements expected, uses only keyword accuracy
   - If no keywords expected, uses only supplement accuracy

A test is considered **successful** if overall accuracy ≥ 50%.

## Test Report

The test report includes:

- Summary statistics (total tests, pass/fail counts, average accuracies)
- Results grouped by test type (safety, recommendation, deficiency)
- Detailed results for each test case showing:
  - Accuracy percentages
  - Missing keywords
  - Missing supplements
  - Actual output

## Adding New Test Cases

To add new test cases:

1. **Determine the test type** (safety, recommendation, deficiency, or multi_agent_tests)
2. **Navigate to the appropriate folder** (e.g., `tests/safety/`)
3. **Open or create a CSV file** in that folder (e.g., `golden_dataset.csv`)
4. **Add a new row** with:
   - A unique `test_id`
   - The `user_question`
   - Relevant profile information (medications, supplements, conditions, dietary restrictions)
   - `expected_output_keywords` (pipe-separated)
   - `expected_supplements` (comma-separated, if applicable)
   - `test_type` (safety, recommendation, deficiency, or multi_agent_tests)
   - A `description` of what the test validates

Example for safety tests (`tests/safety/golden_dataset.csv`):
```csv
16,"Can I take Vitamin D with my medications?","Metformin","","","","safe|generally safe|no interaction","","safety","Vitamin D should be safe with Metformin"
```

### Using Google Sheets

You can edit test cases in Google Sheets and download as CSV:
1. Create or edit a Google Sheet with the same column structure
2. Download as CSV
3. Place the CSV file in the appropriate test type folder
4. Run tests using the dataset name (filename without .csv extension)

## Improving Accuracy Over Time

1. **Run tests regularly** to track performance
2. **Review failed tests** to identify patterns
3. **Update the golden dataset** as you refine expected outputs
4. **Adjust accuracy thresholds** in `test_runner.py` if needed
5. **Add more test cases** to cover edge cases

## Requirements

- Python environment with all project dependencies installed
- Neo4j database running and accessible
- Environment variables set (`.env` file):
  - `NEO4J_URI`
  - `NEO4J_USER`
  - `NEO4J_PASSWORD`
  - `ANTHROPIC_API_KEY`

## Notes

- Tests make actual API calls to Claude and database queries
- Running all tests may take several minutes
- Ensure your database is populated with the knowledge graph data
- Some tests may fail if the database doesn't contain expected data
