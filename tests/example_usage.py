"""
Example: How to use the test runner programmatically
"""

from test_runner import TestRunner

# Initialize the test runner
runner = TestRunner()

# Load test cases
test_cases = runner.load_test_cases()

# Run all tests
results = runner.run_all_tests()

# Generate and print report
report = runner.generate_report(output_path="tests/test_report.txt")
print(report)

# Access individual results
for result in results:
    print(f"\nTest {result['test_id']}:")
    print(f"  Accuracy: {result['overall_accuracy']:.1%}")
    print(f"  Question: {result['question']}")
    if result.get('keywords_missing'):
        print(f"  Missing keywords: {', '.join(result['keywords_missing'])}")
    if result.get('supplements_missing'):
        print(f"  Missing supplements: {', '.join(result['supplements_missing'])}")

# Or run a single test
single_result = runner.run_test_case(test_cases[0])
print(f"\nSingle test result: {single_result['overall_accuracy']:.1%} accuracy")
