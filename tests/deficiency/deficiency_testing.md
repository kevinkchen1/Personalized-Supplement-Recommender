# Deficiency Test Cases

This folder contains test cases for deficiency analysis - testing the system's ability to identify nutrient deficiencies based on diet, medications, or conditions.

## Usage

Place your CSV files here and run:

```bash
python tests/test_runner.py --dataset golden_dataset_deficiency --test-type deficiency
```

Or if the filename contains "deficiency", you can omit `--test-type`:

```bash
python tests/test_runner.py --dataset deficiency_dataset
```

## CSV Format

Each CSV file should have the following columns:
- `test_id`: Unique identifier
- `user_question`: The question being tested
- `medications`: Comma-separated medications
- `supplements`: Comma-separated supplements
- `conditions`: Comma-separated conditions
- `dietary_restrictions`: Comma-separated restrictions
- `expected_output_keywords`: Pipe-separated keywords (e.g., "B-12|Iron|deficiency|at risk")
- `expected_supplements`: Comma-separated supplement names (usually empty for deficiency tests)
- `test_type`: Should be "deficiency"
- `description`: Brief description
