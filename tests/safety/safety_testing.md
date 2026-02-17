# Safety Test Cases

This folder contains test cases for safety checks - testing drug-supplement interactions and safety warnings.

## Usage

Place your CSV files here and run:

```bash
python tests/test_runner.py --dataset golden_dataset_safety --test-type safety
```

Or if the filename contains "safety", you can omit `--test-type`:

```bash
python tests/test_runner.py --dataset safety_dataset
```

## CSV Format

Each CSV file should have the following columns:
- `test_id`: Unique identifier
- `user_question`: The question being tested
- `medications`: Comma-separated medications
- `supplements`: Comma-separated supplements
- `conditions`: Comma-separated conditions
- `dietary_restrictions`: Comma-separated restrictions
- `expected_output_keywords`: Pipe-separated keywords (e.g., "caution|warning|interaction")
- `expected_supplements`: Comma-separated supplement names
- `test_type`: Should be "safety"
- `description`: Brief description
