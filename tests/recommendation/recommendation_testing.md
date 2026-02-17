# Recommendation Test Cases

This folder contains test cases for supplement recommendations - testing the system's ability to suggest appropriate supplements for conditions/symptoms.

## Usage

Place your CSV files here and run:

```bash
python tests/test_runner.py --dataset golden_dataset_recommendation --test-type recommendation
```

Or if the filename contains "recommendation" or "recommend", you can omit `--test-type`:

```bash
python tests/test_runner.py --dataset recommendation_dataset
```

## CSV Format

Each CSV file should have the following columns:
- `test_id`: Unique identifier
- `user_question`: The question being tested
- `medications`: Comma-separated medications
- `supplements`: Comma-separated supplements
- `conditions`: Comma-separated conditions
- `dietary_restrictions`: Comma-separated restrictions
- `expected_output_keywords`: Pipe-separated keywords (e.g., "recommend|safe|option")
- `expected_supplements`: Comma-separated supplement names that should be recommended
- `test_type`: Should be "recommendation"
- `description`: Brief description
