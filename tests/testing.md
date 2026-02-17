# Testing Framework for Supplement Recommender Chatbot

This folder contains the testing framework for evaluating the chatbot's performance against a golden dataset.

## Files

- **`golden_dataset.csv`**: Contains test cases with user profiles, questions, and expected outputs
- **`test_runner.py`**: Main test runner script that executes tests and calculates accuracy
- **`testing.md`**: This file

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

### Run All Tests

```bash
cd /path/to/Personalized-Supplement-Recommender
python tests/test_runner.py
```

This will:
1. Load all test cases from `golden_dataset.csv`
2. Run each test case through the workflow
3. Calculate accuracy metrics
4. Generate a report saved to `tests/test_report.txt` and `tests/test_report.json`

### Run a Specific Test

```bash
python tests/test_runner.py --test-id 1
```

### Custom Dataset or Output Path

```bash
python tests/test_runner.py --dataset path/to/custom_dataset.csv --output path/to/report.txt
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

1. Open `golden_dataset.csv`
2. Add a new row with:
   - A unique `test_id`
   - The `user_question`
   - Relevant profile information (medications, supplements, conditions, dietary restrictions)
   - `expected_output_keywords` (pipe-separated)
   - `expected_supplements` (comma-separated, if applicable)
   - `test_type` (safety, recommendation, deficiency, or general)
   - A `description` of what the test validates

Example:
```csv
16,"Can I take Vitamin D with my medications?","Metformin","","","","safe|generally safe|no interaction","","safety","Vitamin D should be safe with Metformin"
```

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
