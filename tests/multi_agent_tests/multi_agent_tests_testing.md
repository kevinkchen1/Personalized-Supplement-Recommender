# Multi-Agent Test Cases

This folder contains test cases that require multiple agent types to work together - for example, tests that need both safety checks AND recommendations.

## Usage

Place your CSV files here and run:

```bash
python tests/test_runner.py --dataset golden_dataset_multi_agent_tests --test-type multi_agent_tests
```

Or if the filename contains "multi" or "agent", you can omit `--test-type`:

```bash
python tests/test_runner.py --dataset multi_agent_dataset
```

## CSV Format

Each CSV file should have the following columns:
- `test_id`: Unique identifier
- `user_question`: The question being tested
- `medications`: Comma-separated medications
- `supplements`: Comma-separated supplements
- `conditions`: Comma-separated conditions
- `dietary_restrictions`: Comma-separated restrictions
- `expected_output_keywords`: Pipe-separated keywords
- `expected_supplements`: Comma-separated supplement names
- `test_type`: Should be "multi_agent"
- `description`: Brief description
