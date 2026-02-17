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
    
    def __init__(self, dataset_name: str = None, test_type: str = None, golden_dataset_path: str = None):
        """
        Initialize test runner
        
        Args:
            dataset_name: Name of the dataset (e.g., "golden_dataset") - will look in appropriate folder
            test_type: Type of test (safety, recommendation, deficiency, multi_agent_tests)
                      If None, will try to infer from dataset_name or folder structure
            golden_dataset_path: Direct path to CSV file (overrides dataset_name/test_type)
        """
        self.tests_dir = Path(__file__).parent
        self.test_reports_dir = self.tests_dir / "test_reports"
        self.test_reports_dir.mkdir(exist_ok=True)
        
        # Store test type for report organization
        self.test_type = test_type
        
        # Determine dataset path
        if golden_dataset_path:
            self.golden_dataset_path = Path(golden_dataset_path)
            # Try to infer test type from path
            if not self.test_type:
                path_str = str(golden_dataset_path)
                if 'safety' in path_str.lower():
                    self.test_type = 'safety'
                elif 'recommendation' in path_str.lower():
                    self.test_type = 'recommendation'
                elif 'deficiency' in path_str.lower():
                    self.test_type = 'deficiency'
                elif 'multi_agent' in path_str.lower():
                    self.test_type = 'multi_agent_tests'
        elif dataset_name:
            # Determine test type if not provided
            if not self.test_type:
                self.test_type = self._infer_test_type(dataset_name)
            
            # Look in appropriate folder
            if self.test_type in ['safety', 'recommendation', 'deficiency', 'multi_agent_tests']:
                # Try the exact name first
                dataset_path = self.tests_dir / self.test_type / f"{dataset_name}.csv"
                
                # If not found and name doesn't include test type, try with suffix
                if not dataset_path.exists() and self.test_type not in dataset_name.lower():
                    dataset_path = self.tests_dir / self.test_type / f"{dataset_name}_{self.test_type}.csv"
                
                # If still not found, try without the suffix (backward compatibility)
                if not dataset_path.exists():
                    # Remove any existing suffix and try again
                    base_name = dataset_name.replace(f"_{self.test_type}", "").replace(f"-{self.test_type}", "")
                    dataset_path = self.tests_dir / self.test_type / f"{base_name}_{self.test_type}.csv"
            else:
                # Fallback: try all folders
                dataset_path = self._find_dataset(dataset_name)
            
            if not dataset_path.exists():
                raise FileNotFoundError(
                    f"Dataset '{dataset_name}' not found in {self.test_type if self.test_type else 'any'} folder. "
                    f"Tried: {self.tests_dir / self.test_type / f'{dataset_name}.csv'} "
                    f"and {self.tests_dir / self.test_type / f'{dataset_name}_{self.test_type}.csv' if self.test_type else ''}"
                )
            self.golden_dataset_path = dataset_path
        else:
            # Default: look for golden_dataset.csv in current directory (backward compatibility)
            default_path = self.tests_dir / "golden_dataset.csv"
            if default_path.exists():
                self.golden_dataset_path = default_path
            else:
                # Try in safety folder as default
                self.golden_dataset_path = self.tests_dir / "safety" / "golden_dataset_safety.csv"
                if not self.test_type:
                    self.test_type = 'safety'
        
        self.dataset_name = dataset_name or self.golden_dataset_path.stem
        
        # If test type still not determined, try to infer from results later
        self.test_cases = []
        self.results = []
        
        # Initialize workflow and graph (lazy initialization)
        self.graph = None
        self.workflow = None
    
    def _infer_test_type(self, dataset_name: str) -> str:
        """Try to infer test type from dataset name"""
        name_lower = dataset_name.lower()
        if 'safety' in name_lower:
            return 'safety'
        elif 'recommendation' in name_lower or 'recommend' in name_lower:
            return 'recommendation'
        elif 'deficiency' in name_lower:
            return 'deficiency'
        elif 'multi' in name_lower or 'agent' in name_lower:
            return 'multi_agent_tests'
        return None
    
    def _find_dataset(self, dataset_name: str) -> Path:
        """Search all test type folders for the dataset"""
        for test_type in ['safety', 'recommendation', 'deficiency', 'multi_agent_tests']:
            # Try exact name
            dataset_path = self.tests_dir / test_type / f"{dataset_name}.csv"
            if dataset_path.exists():
                return dataset_path
            
            # Try with test type suffix
            dataset_path = self.tests_dir / test_type / f"{dataset_name}_{test_type}.csv"
            if dataset_path.exists():
                return dataset_path
            
            # Try removing any existing suffix and adding the correct one
            base_name = dataset_name.replace(f"_{test_type}", "").replace(f"-{test_type}", "")
            if base_name != dataset_name:
                dataset_path = self.tests_dir / test_type / f"{base_name}_{test_type}.csv"
                if dataset_path.exists():
                    return dataset_path
        
        raise FileNotFoundError(f"Dataset '{dataset_name}' not found in any test type folder")
    
    def _initialize_workflow(self):
        """Initialize workflow and graph connection"""
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
        # Initialize workflow if not already done
        if self.workflow is None:
            self._initialize_workflow()
        
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
            output_path: Optional path to save report. If None, saves to test_reports/ with dataset name
            
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
            f"Dataset: {self.dataset_name}",
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
        
        # Determine test type for folder organization
        # Priority: self.test_type > most common in results > 'unknown'
        report_test_type = self.test_type
        if not report_test_type and self.results:
            # Get most common test type from results
            test_types = [r.get('test_type', 'unknown') for r in self.results]
            if test_types:
                from collections import Counter
                report_test_type = Counter(test_types).most_common(1)[0][0]
        
        # Normalize test type for folder name
        if report_test_type == 'multi_agent_tests':
            folder_name = 'multi_agent_tests'
        elif report_test_type in ['safety', 'recommendation', 'deficiency']:
            folder_name = report_test_type
        else:
            folder_name = 'unknown'
        
        # Create subfolder for test type
        type_reports_dir = self.test_reports_dir / folder_name
        type_reports_dir.mkdir(exist_ok=True)
        
        # Determine output path
        if output_path is None:
            # Default: save to test_reports/{test_type}/ with dataset name and test type
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            # Remove test type suffix from dataset name if present to avoid duplication
            base_dataset_name = self.dataset_name
            for test_type_suffix in ['_safety', '_recommendation', '_deficiency', '_multi_agent_tests']:
                if base_dataset_name.endswith(test_type_suffix):
                    base_dataset_name = base_dataset_name[:-len(test_type_suffix)]
                    break
            
            output_path = type_reports_dir / f"test_report_{folder_name}_{timestamp}.txt"
        else:
            # If custom path provided, use it but still organize if it's in test_reports
            output_path = Path(output_path)
            if str(output_path).startswith(str(self.test_reports_dir)):
                # If it's in test_reports, ensure it goes to the right subfolder
                output_path = type_reports_dir / output_path.name
        
        output_path = Path(output_path)
        
        # Save report
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report)
        
        # Also save JSON for programmatic access
        json_path = output_path.with_suffix('.json')
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump({
                'dataset_name': self.dataset_name,
                'test_type': report_test_type,
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
        default='golden_dataset',
        help='Name of the dataset (without .csv extension). Will look in appropriate test type folder. (default: golden_dataset)'
    )
    parser.add_argument(
        '--test-type',
        type=str,
        choices=['safety', 'recommendation', 'deficiency', 'multi_agent_tests'],
        default=None,
        help='Type of test (safety, recommendation, deficiency, multi_agent_tests). If not provided, will try to infer from dataset name.'
    )
    parser.add_argument(
        '--dataset-path',
        type=str,
        default=None,
        help='Direct path to CSV file (overrides --dataset and --test-type)'
    )
    parser.add_argument(
        '--output',
        type=str,
        default=None,
        help='Path to save test report (default: tests/test_reports/{dataset_name}_{timestamp}.txt)'
    )
    parser.add_argument(
        '--test-id',
        type=str,
        default=None,
        help='Run only a specific test ID'
    )
    
    args = parser.parse_args()
    
    # Initialize runner
    if args.dataset_path:
        runner = TestRunner(golden_dataset_path=args.dataset_path)
    else:
        runner = TestRunner(dataset_name=args.dataset, test_type=args.test_type)
    
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
