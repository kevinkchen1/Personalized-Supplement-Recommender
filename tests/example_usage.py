"""
Example: How to use the test runner programmatically
"""

from test_runner import TestRunner

# Example 1: Run safety tests by dataset name
print("Example 1: Running safety tests")
runner = TestRunner(dataset_name="golden_dataset", test_type="safety")
test_cases = runner.load_test_cases()
results = runner.run_all_tests()
report = runner.generate_report()  # Saves to test_reports/ automatically
print(report)

# Example 2: Run recommendation tests (test type inferred from name)
print("\n\nExample 2: Running recommendation tests")
runner2 = TestRunner(dataset_name="golden_dataset", test_type="recommendation")
test_cases2 = runner2.load_test_cases()
results2 = runner2.run_all_tests()
report2 = runner2.generate_report()
print(report2)

# Example 3: Run with direct path
print("\n\nExample 3: Running with direct path")
runner3 = TestRunner(golden_dataset_path="tests/deficiency/golden_dataset.csv")
test_cases3 = runner3.load_test_cases()
results3 = runner3.run_all_tests()
report3 = runner3.generate_report()
print(report3)

# Example 4: Run a single test
print("\n\nExample 4: Running a single test")
runner4 = TestRunner(dataset_name="golden_dataset", test_type="safety")
test_cases4 = runner4.load_test_cases()
single_result = runner4.run_test_case(test_cases4[0])
print(f"Single test result: {single_result['overall_accuracy']:.1%} accuracy")

# Example 5: Access individual results
print("\n\nExample 5: Accessing individual results")
for result in results:
    print(f"\nTest {result['test_id']}:")
    print(f"  Accuracy: {result['overall_accuracy']:.1%}")
    print(f"  Question: {result['question']}")
    if result.get('keywords_missing'):
        print(f"  Missing keywords: {', '.join(result['keywords_missing'])}")
    if result.get('supplements_missing'):
        print(f"  Missing supplements: {', '.join(result['supplements_missing'])}")
