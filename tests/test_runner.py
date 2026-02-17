"""
Test Runner for Supplement Recommender Chatbot

Loads golden dataset, runs workflow for each test case, and calculates accuracy.
"""

import os
import sys
import csv
import json
from pathlib import Path
from typing import Dict, List, Any
from dotenv import load_dotenv

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from workflow.graph_builder import build_workflow, run_workflow
from graph.graph_interface import GraphInterface

load_dotenv()


class TestRunner:
    """Runs tests against golden dataset and calculates accuracy"""
    
    def __init__(self, golden_dataset_path: str = None):
        """
        Initialize test runner
        
        Args:
            golden_dataset_path: Path to CSV file with test cases
        """
        if golden_dataset_path is None:
            golden_dataset_path = Path(__file__).parent / "golden_dataset.csv"
        
        self.golden_dataset_path = Path(golden_dataset_path)
        self.test_cases = []
        self.results = []
        
        # Initialize workflow and graph
        print("🔧 Initializing workflow and database connection...")
        try:
            neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
            neo4j_user = os.getenv("NEO4J_USER", "neo4j")
            neo4j_password = os.getenv("NEO4J_PASSWORD")
            
            if not neo4j_password:
                raise ValueError("NEO4J_PASSWORD not set in environment")
            
            self.graph = GraphInterface(neo4j_uri, neo4j_user, neo4j_password)
            self.workflow = build_workflow()
            print("✓ Initialization complete\n")
        except Exception as e:
            print(f"❌ Failed to initialize: {e}")
            raise
    
    def load_test_cases(self) -> List[Dict[str, Any]]:
        """Load test cases from CSV file"""
        print(f"📖 Loading test cases from {self.golden_dataset_path}...")
        
        test_cases = []
        with open(self.golden_dataset_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Parse medications (comma-separated)
                medications = []
                if row.get('medications'):
                    meds = [m.strip() for m in row['medications'].split(',') if m.strip()]
                    medications = meds
                
                # Parse supplements (comma-separated)
                supplements = []
                if row.get('supplements'):
                    supps = [s.strip() for s in row['supplements'].split(',') if s.strip()]
                    supplements = supps
                
                # Parse conditions (comma-separated)
                conditions = []
                if row.get('conditions'):
                    conds = [c.strip() for c in row['conditions'].split(',') if c.strip()]
                    conditions = conds
                
                # Parse dietary restrictions (comma-separated)
                dietary_restrictions = []
                if row.get('dietary_restrictions'):
                    diets = [d.strip() for d in row['dietary_restrictions'].split(',') if d.strip()]
                    dietary_restrictions = diets
                
                # Parse expected supplements (comma-separated)
                expected_supplements = []
                if row.get('expected_supplements'):
                    exp_supps = [s.strip() for s in row['expected_supplements'].split(',') if s.strip()]
                    expected_supplements = exp_supps
                
                # Parse expected keywords (pipe-separated, case-insensitive)
                expected_keywords = []
                if row.get('expected_output_keywords'):
                    keywords = [k.strip().lower() for k in row['expected_output_keywords'].split('|') if k.strip()]
                    expected_keywords = keywords
                
                test_case = {
                    'test_id': row.get('test_id', ''),
                    'user_question': row.get('user_question', ''),
                    'patient_profile': {
                        'medications': medications,
                        'supplements': supplements,
                        'conditions': conditions,
                        'dietary_restrictions': dietary_restrictions
                    },
                    'expected_keywords': expected_keywords,
                    'expected_supplements': expected_supplements,
                    'test_type': row.get('test_type', ''),
                    'description': row.get('description', '')
                }
                test_cases.append(test_case)
        
        self.test_cases = test_cases
        print(f"✓ Loaded {len(test_cases)} test cases\n")
        return test_cases
    
    def run_test_case(self, test_case: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run a single test case through the workflow
        
        Args:
            test_case: Test case dictionary
            
        Returns:
            Result dictionary with actual output and accuracy metrics
        """
        test_id = test_case['test_id']
        question = test_case['user_question']
        profile = test_case['patient_profile']
        
        print(f"🧪 Test {test_id}: {question[:60]}...")
        
        try:
            # Run workflow (verbose=False to reduce noise in test output)
            state = run_workflow(
                self.workflow,
                question,
                profile,
                graph_interface=self.graph,
                verbose=False
            )
            
            # Extract actual output
            actual_answer = state.get('final_answer', '')
            if not actual_answer:
                actual_answer = state.get('error_message', 'No output generated')
            
            # Calculate accuracy
            accuracy_metrics = self._calculate_accuracy(
                actual_answer,
                test_case['expected_keywords'],
                test_case['expected_supplements']
            )
            
            result = {
                'test_id': test_id,
                'question': question,
                'description': test_case['description'],
                'test_type': test_case['test_type'],
                'actual_answer': actual_answer,
                'expected_keywords': test_case['expected_keywords'],
                'expected_supplements': test_case['expected_supplements'],
                'keyword_accuracy': accuracy_metrics['keyword_accuracy'],
                'supplement_accuracy': accuracy_metrics['supplement_accuracy'],
                'overall_accuracy': accuracy_metrics['overall_accuracy'],
                'keywords_found': accuracy_metrics['keywords_found'],
                'keywords_missing': accuracy_metrics['keywords_missing'],
                'supplements_found': accuracy_metrics['supplements_found'],
                'supplements_missing': accuracy_metrics['supplements_missing'],
                'success': accuracy_metrics['overall_accuracy'] >= 0.5  # Threshold
            }
            
            print(f"   ✓ Accuracy: {accuracy_metrics['overall_accuracy']:.1%}")
            if accuracy_metrics['keywords_missing']:
                print(f"   ⚠ Missing keywords: {', '.join(accuracy_metrics['keywords_missing'][:3])}")
            if accuracy_metrics['supplements_missing']:
                print(f"   ⚠ Missing supplements: {', '.join(accuracy_metrics['supplements_missing'])}")
            
            return result
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
            return {
                'test_id': test_id,
                'question': question,
                'description': test_case['description'],
                'test_type': test_case['test_type'],
                'actual_answer': f"ERROR: {str(e)}",
                'expected_keywords': test_case['expected_keywords'],
                'expected_supplements': test_case['expected_supplements'],
                'keyword_accuracy': 0.0,
                'supplement_accuracy': 0.0,
                'overall_accuracy': 0.0,
                'keywords_found': [],
                'keywords_missing': test_case['expected_keywords'],
                'supplements_found': [],
                'supplements_missing': test_case['expected_supplements'],
                'success': False,
                'error': str(e)
            }
    
    def _calculate_accuracy(
        self,
        actual_answer: str,
        expected_keywords: List[str],
        expected_supplements: List[str]
    ) -> Dict[str, Any]:
        """
        Calculate accuracy metrics
        
        Args:
            actual_answer: The actual output from the chatbot
            expected_keywords: List of keywords that should appear (case-insensitive)
            expected_supplements: List of supplement names that should appear
            
        Returns:
            Dictionary with accuracy metrics
        """
        actual_lower = actual_answer.lower()
        
        # Check keywords
        keywords_found = []
        keywords_missing = []
        
        for keyword in expected_keywords:
            keyword_lower = keyword.lower()
            # Check if keyword appears (as whole word or part of word)
            if keyword_lower in actual_lower:
                keywords_found.append(keyword)
            else:
                keywords_missing.append(keyword)
        
        keyword_accuracy = len(keywords_found) / len(expected_keywords) if expected_keywords else 1.0
        
        # Check supplements (more flexible matching)
        supplements_found = []
        supplements_missing = []
        
        for supplement in expected_supplements:
            supp_lower = supplement.lower()
            # Try exact match first
            if supp_lower in actual_lower:
                supplements_found.append(supplement)
            else:
                # Try partial matches (e.g., "CoQ10" matches "Coenzyme Q10")
                # Split supplement name into words
                supp_words = supp_lower.split()
                if len(supp_words) > 1:
                    # Check if all significant words appear
                    significant_words = [w for w in supp_words if len(w) > 2]
                    if significant_words and all(w in actual_lower for w in significant_words):
                        supplements_found.append(supplement)
                    else:
                        supplements_missing.append(supplement)
                else:
                    supplements_missing.append(supplement)
        
        supplement_accuracy = len(supplements_found) / len(expected_supplements) if expected_supplements else 1.0
        
        # Overall accuracy: weighted average (keywords 60%, supplements 40%)
        # If no supplements expected, use only keywords
        if not expected_supplements:
            overall_accuracy = keyword_accuracy
        elif not expected_keywords:
            overall_accuracy = supplement_accuracy
        else:
            overall_accuracy = (keyword_accuracy * 0.6) + (supplement_accuracy * 0.4)
        
        return {
            'keyword_accuracy': keyword_accuracy,
            'supplement_accuracy': supplement_accuracy,
            'overall_accuracy': overall_accuracy,
            'keywords_found': keywords_found,
            'keywords_missing': keywords_missing,
            'supplements_found': supplements_found,
            'supplements_missing': supplements_missing
        }
    
    def run_all_tests(self) -> List[Dict[str, Any]]:
        """Run all test cases"""
        if not self.test_cases:
            self.load_test_cases()
        
        print(f"🚀 Running {len(self.test_cases)} test cases...\n")
        print("=" * 80)
        
        results = []
        for test_case in self.test_cases:
            result = self.run_test_case(test_case)
            results.append(result)
            print()  # Blank line between tests
        
        self.results = results
        return results
    
    def generate_report(self, output_path: str = None) -> str:
        """
        Generate a test report
        
        Args:
            output_path: Optional path to save report JSON
            
        Returns:
            Report string
        """
        if not self.results:
            return "No test results available. Run tests first."
        
        total_tests = len(self.results)
        successful_tests = sum(1 for r in self.results if r.get('success', False))
        failed_tests = total_tests - successful_tests
        
        # Calculate average accuracies
        avg_keyword_acc = sum(r['keyword_accuracy'] for r in self.results) / total_tests
        avg_supplement_acc = sum(r['supplement_accuracy'] for r in self.results) / total_tests
        avg_overall_acc = sum(r['overall_accuracy'] for r in self.results) / total_tests
        
        # Group by test type
        by_type = {}
        for result in self.results:
            test_type = result.get('test_type', 'unknown')
            if test_type not in by_type:
                by_type[test_type] = {'total': 0, 'successful': 0, 'accuracies': []}
            by_type[test_type]['total'] += 1
            if result.get('success'):
                by_type[test_type]['successful'] += 1
            by_type[test_type]['accuracies'].append(result['overall_accuracy'])
        
        # Build report
        report_lines = [
            "=" * 80,
            "TEST REPORT - Supplement Recommender Chatbot",
            "=" * 80,
            "",
            f"Total Tests: {total_tests}",
            f"Successful: {successful_tests} ({successful_tests/total_tests:.1%})",
            f"Failed: {failed_tests} ({failed_tests/total_tests:.1%})",
            "",
            "Average Accuracies:",
            f"  Keyword Accuracy: {avg_keyword_acc:.1%}",
            f"  Supplement Accuracy: {avg_supplement_acc:.1%}",
            f"  Overall Accuracy: {avg_overall_acc:.1%}",
            "",
            "Results by Test Type:",
        ]
        
        for test_type, stats in by_type.items():
            avg_acc = sum(stats['accuracies']) / len(stats['accuracies'])
            report_lines.append(
                f"  {test_type}: {stats['successful']}/{stats['total']} passed "
                f"(avg accuracy: {avg_acc:.1%})"
            )
        
        report_lines.extend([
            "",
            "=" * 80,
            "DETAILED RESULTS",
            "=" * 80,
            ""
        ])
        
        for result in self.results:
            status = "✓ PASS" if result.get('success') else "✗ FAIL"
            report_lines.append(
                f"{status} Test {result['test_id']}: {result['overall_accuracy']:.1%} accuracy"
            )
            report_lines.append(f"  Question: {result['question']}")
            report_lines.append(f"  Type: {result.get('test_type', 'unknown')}")
            if result.get('keywords_missing'):
                report_lines.append(f"  Missing keywords: {', '.join(result['keywords_missing'][:5])}")
            if result.get('supplements_missing'):
                report_lines.append(f"  Missing supplements: {', '.join(result['supplements_missing'])}")
            report_lines.append("")
        
        report = "\n".join(report_lines)
        
        # Save to file if requested
        if output_path:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(report)
            
            # Also save JSON for programmatic access
            json_path = Path(output_path).with_suffix('.json')
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump({
                    'summary': {
                        'total_tests': total_tests,
                        'successful': successful_tests,
                        'failed': failed_tests,
                        'avg_keyword_accuracy': avg_keyword_acc,
                        'avg_supplement_accuracy': avg_supplement_acc,
                        'avg_overall_accuracy': avg_overall_acc
                    },
                    'results': self.results
                }, f, indent=2)
            
            print(f"\n📄 Report saved to {output_path}")
            print(f"📄 JSON results saved to {json_path}")
        
        return report


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Run tests against golden dataset')
    parser.add_argument(
        '--dataset',
        type=str,
        default=None,
        help='Path to golden dataset CSV (default: tests/golden_dataset.csv)'
    )
    parser.add_argument(
        '--output',
        type=str,
        default='tests/test_report.txt',
        help='Path to save test report (default: tests/test_report.txt)'
    )
    parser.add_argument(
        '--test-id',
        type=str,
        default=None,
        help='Run only a specific test ID'
    )
    
    args = parser.parse_args()
    
    # Initialize runner
    runner = TestRunner(golden_dataset_path=args.dataset)
    runner.load_test_cases()
    
    # Run tests
    if args.test_id:
        # Run single test
        test_case = next((tc for tc in runner.test_cases if tc['test_id'] == args.test_id), None)
        if not test_case:
            print(f"❌ Test ID {args.test_id} not found")
            return
        
        result = runner.run_test_case(test_case)
        runner.results = [result]
    else:
        # Run all tests
        runner.run_all_tests()
    
    # Generate report
    report = runner.generate_report(output_path=args.output)
    print("\n" + report)


if __name__ == "__main__":
    main()
