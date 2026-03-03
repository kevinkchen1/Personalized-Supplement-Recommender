"""
Test Runner — Safety Tests

Loads golden_dataset_safety.csv, runs the workflow for each test case,
calculates accuracy, and generates a report with safety-specific debug fields:
  - Patient profile
  - Generated Cypher queries (per supplement)
  - Execution status and errors (per supplement)
  - Interactions found from safety_results
  - Final answer from synthesis

Reports are saved to the same folder as this file:
  tests/safety/test_report_safety_{timestamp}.txt
  tests/safety/test_report_safety_{timestamp}.json
"""

import os
import sys
import csv
import json
from pathlib import Path
from typing import Dict, List, Any
from dotenv import load_dotenv

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))          # enables 'from src.x import ...'
sys.path.insert(0, str(project_root / "src"))  # enables 'from workflow.x import ...'

from workflow.graph_builder import build_workflow
from workflow.state import create_initial_state

load_dotenv()

# ── Semantic similarity ──
# Model is loaded once at class instantiation and reused across all test cases.
# all-MiniLM-L6-v2: lightweight, fast, strong semantic similarity performance.
# Install: pip install sentence-transformers
try:
    from sentence_transformers import SentenceTransformer
    from sklearn.metrics.pairwise import cosine_similarity
    import numpy as np
    SEMANTIC_AVAILABLE = True
except ImportError:
    SEMANTIC_AVAILABLE = False
    print("⚠️  sentence-transformers not installed. Run: pip install sentence-transformers")


class SafetyTestRunner:
    """Runs safety tests against golden dataset and calculates accuracy"""

    def __init__(self, dataset_name: str = None, golden_dataset_path: str = None):
        """
        Initialize test runner.

        Args:
            dataset_name: Name of the dataset file without .csv extension.
                          Looks in the same folder as this script.
            golden_dataset_path: Direct path to CSV file (overrides dataset_name).
        """
        # Reports save to the same folder as this script (tests/safety/)
        self.tests_dir = Path(__file__).parent
        self.test_type = "safety"

        # Determine dataset path
        if golden_dataset_path:
            self.golden_dataset_path = Path(golden_dataset_path)
        elif dataset_name:
            self.golden_dataset_path = self.tests_dir / f"{dataset_name}.csv"
        else:
            self.golden_dataset_path = self.tests_dir / "golden_dataset_safety.csv"

        if not self.golden_dataset_path.exists():
            raise FileNotFoundError(
                f"Dataset not found: {self.golden_dataset_path}"
            )

        self.dataset_name = dataset_name or self.golden_dataset_path.stem
        self.test_cases = []
        self.results = []

        # Lazy initialization
        self.workflow = None

        # Semantic similarity model — loaded once, reused across all test cases
        self.embedding_model = None
        self.SIMILARITY_THRESHOLD = 0.6  # keyword is "found" if max sentence score >= this

    def _initialize_workflow(self):
        """Initialize workflow. Neo4j connection is handled automatically by connections.py on import."""
        print("🔧 Initializing workflow...")
        try:
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
                medications = [m.strip() for m in row.get('medications', '').split(',') if m.strip()]
                supplements = [s.strip() for s in row.get('supplements', '').split(',') if s.strip()]
                conditions = [c.strip() for c in row.get('conditions', '').split(',') if c.strip()]
                dietary_restrictions = [d.strip() for d in row.get('dietary_restrictions', '').split(',') if d.strip()]
                expected_supplements = [s.strip() for s in row.get('expected_supplements', '').split(',') if s.strip()]
                expected_keywords = [k.strip().lower() for k in row.get('expected_output_keywords', '').split('|') if k.strip()]

                test_case = {
                    'test_id': row.get('test_id', ''),
                    'user_question': row.get('user_question', ''),
                    'patient_profile': {
                        'medications': medications,
                        'supplements': supplements,
                        'conditions': conditions,
                        'dietary_restrictions': dietary_restrictions,
                    },
                    'expected_keywords': expected_keywords,
                    'expected_supplements': expected_supplements,
                    'test_type': row.get('test_type', ''),
                    'description': row.get('description', ''),
                }
                test_cases.append(test_case)

        self.test_cases = test_cases
        print(f"✓ Loaded {len(test_cases)} test cases\n")
        return test_cases

    def run_test_case(self, test_case: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run a single test case through the workflow.

        Captures standard accuracy fields plus safety-specific state fields:
          - generated_safety_queries (cypher, executed, error per supplement)
          - safety_results.interactions
          - final_answer
        """
        if self.workflow is None:
            self._initialize_workflow()

        test_id = test_case['test_id']
        question = test_case['user_question']
        profile = test_case['patient_profile']

        print(f"🧪 Test {test_id}: {question[:60]}...")

        try:
            initial_state = create_initial_state(question, profile)
            state = self.workflow.invoke(initial_state)

            # --- Standard output extraction ---
            actual_answer = state.get('final_answer', '')
            if not actual_answer:
                actual_answer = state.get('error_message', 'No output generated')

            # --- Safety-specific state extraction ---
            generated_safety_queries = state.get('generated_safety_queries', [])
            safety_interactions = (
                (state.get('safety_results') or {}).get('interactions', [])
                )

            # --- Accuracy calculation (unchanged logic) ---
            accuracy_metrics = self._calculate_accuracy(
                actual_answer,
                test_case['expected_keywords'],
                test_case['expected_supplements']
            )

            result = {
                # Standard fields
                'test_id': test_id,
                'question': question,
                'description': test_case['description'],
                'test_type': test_case['test_type'],
                'patient_profile': profile,
                'expected_keywords': test_case['expected_keywords'],
                'expected_supplements': test_case['expected_supplements'],
                'keyword_accuracy': accuracy_metrics['keyword_accuracy'],
                'supplement_accuracy': accuracy_metrics['supplement_accuracy'],
                'overall_accuracy': accuracy_metrics['overall_accuracy'],
                'keywords_found': accuracy_metrics['keywords_found'],
                'keywords_missing': accuracy_metrics['keywords_missing'],
                'keyword_scores': accuracy_metrics['keyword_scores'],
                'supplements_found': accuracy_metrics['supplements_found'],
                'supplements_missing': accuracy_metrics['supplements_missing'],
                'success': accuracy_metrics['overall_accuracy'] >= 0.5,
                # Safety-specific fields
                'generated_safety_queries': generated_safety_queries,
                'safety_interactions': safety_interactions,
                'final_answer': actual_answer,
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
                'patient_profile': profile,
                'expected_keywords': test_case['expected_keywords'],
                'expected_supplements': test_case['expected_supplements'],
                'keyword_accuracy': 0.0,
                'supplement_accuracy': 0.0,
                'overall_accuracy': 0.0,
                'keywords_found': [],
                'keywords_missing': test_case['expected_keywords'],
                'keyword_scores': {},
                'supplements_found': [],
                'supplements_missing': test_case['expected_supplements'],
                'success': False,
                'error': str(e),
                # Safety-specific fields (empty on error)
                'generated_safety_queries': [],
                'safety_interactions': [],
                'final_answer': f"ERROR: {str(e)}",
            }

    def _load_embedding_model(self):
        """Load the sentence embedding model once, reuse across all tests."""
        if self.embedding_model is None:
            if not SEMANTIC_AVAILABLE:
                raise RuntimeError(
                    "sentence-transformers is not installed. "
                    "Run: pip install sentence-transformers"
                )
            print("🔄 Loading embedding model (all-MiniLM-L6-v2)...")
            self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
            print("✓ Embedding model loaded\n")
        return self.embedding_model

    def _semantic_keyword_score(
        self,
        keyword: str,
        answer_sentences: List[str],
        answer_text: str,
        model: Any,
    ) -> float:
        """
        Compute the semantic similarity score for one keyword against the answer.

        Strategy (in order):
        1. Exact substring match → score 1.0 immediately
        2. Sliding word window over each sentence → max cosine similarity
        across all windows across all sentences.

        Window size is set to keyword_length + 4 words to give just enough
        context without diluting the match with unrelated content.

        Args:
            keyword: Expected keyword or phrase (e.g. "cannot check")
            answer_sentences: Answer split into individual sentences
            answer_text: Full answer text for exact substring check
            model: Loaded SentenceTransformer model

        Returns:
            Float 0.0–1.0
        """
        if not answer_sentences:
            return 0.0

        # ── Step 1: Exact substring match ──
        if keyword.lower() in answer_text.lower():
            return 1.0

        # ── Step 2: Sliding word window ──
        keyword_words = keyword.split()
        window_size = len(keyword_words) + 10  # keyword length + small context buffer

        windows = []
        for sentence in answer_sentences:
            words = sentence.split()
            if len(words) <= window_size:
                # Sentence is shorter than window — use it whole
                windows.append(sentence)
            else:
                # Slide window across sentence
                for i in range(len(words) - window_size + 1):
                    window = " ".join(words[i: i + window_size])
                    windows.append(window)

        if not windows:
            return 0.0

        # Embed keyword and all windows in one batch
        all_texts = [keyword] + windows
        embeddings = model.encode(all_texts, convert_to_numpy=True)

        keyword_embedding = embeddings[0].reshape(1, -1)
        window_embeddings = embeddings[1:]

        similarities = cosine_similarity(keyword_embedding, window_embeddings)[0]
        return float(np.max(similarities))
    
    def _calculate_accuracy(
        self,
        actual_answer: str,
        expected_keywords: List[str],
        expected_supplements: List[str]
    ) -> Dict[str, Any]:
        """
        Calculate accuracy using semantic similarity (sentence embeddings).

        For each expected keyword:
          - Split the answer into sentences
          - Embed the keyword and each sentence
          - Score = max cosine similarity across all sentences
          - Found if score >= SIMILARITY_THRESHOLD

        Supplement matching retains flexible substring logic since supplement
        names are proper nouns that should appear verbatim in the answer.
        """
        # ── Split answer into sentences for per-sentence comparison ──
        import re
        # Split on sentence-ending punctuation followed by whitespace or end
        raw_sentences = re.split(r'(?<=[.!?])\s+', actual_answer.strip())
        # Filter out empty strings and very short fragments
        answer_sentences = [s.strip() for s in raw_sentences if len(s.strip()) > 10]

        # ── Keyword scoring via semantic similarity ──
        keywords_found = []
        keywords_missing = []
        keyword_scores = {}  # keyword -> similarity score (for report transparency)

        if expected_keywords:
            model = self._load_embedding_model()
            for keyword in expected_keywords:
                score = self._semantic_keyword_score(keyword, answer_sentences, actual_answer, model)
                keyword_scores[keyword] = round(score, 3)
                if score >= self.SIMILARITY_THRESHOLD:
                    keywords_found.append(keyword)
                else:
                    keywords_missing.append(keyword)

        keyword_accuracy = len(keywords_found) / len(expected_keywords) if expected_keywords else 1.0

        # ── Supplement matching — flexible substring (unchanged) ──
        # Supplement names are proper nouns; they should appear verbatim in the answer.
        actual_lower = actual_answer.lower()
        supplements_found = []
        supplements_missing = []

        for supplement in expected_supplements:
            supp_lower = supplement.lower()
            if supp_lower in actual_lower:
                supplements_found.append(supplement)
            else:
                supp_words = supp_lower.split()
                if len(supp_words) > 1:
                    significant_words = [w for w in supp_words if len(w) > 2]
                    if significant_words and all(w in actual_lower for w in significant_words):
                        supplements_found.append(supplement)
                    else:
                        supplements_missing.append(supplement)
                else:
                    supplements_missing.append(supplement)

        supplement_accuracy = len(supplements_found) / len(expected_supplements) if expected_supplements else 1.0

        # ── Overall accuracy (same weighting as before) ──
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
            'keyword_scores': keyword_scores,
            'supplements_found': supplements_found,
            'supplements_missing': supplements_missing,
        }

    def run_all_tests(self) -> List[Dict[str, Any]]:
        """Run all test cases"""
        if not self.test_cases:
            self.load_test_cases()

        print(f"🚀 Running {len(self.test_cases)} safety test cases...\n")
        print("=" * 80)

        results = []
        for test_case in self.test_cases:
            result = self.run_test_case(test_case)
            results.append(result)
            print()

        self.results = results
        return results

    def generate_report(self, output_path: str = None) -> str:
        """
        Generate a test report.

        Structure:
          1. Summary statistics (unchanged from original)
          2. Detailed test results — one block per test, including:
               - User question + patient profile
               - Safety queries (per supplement: cypher, executed, error)
               - Interactions found
               - Final answer
        """
        if not self.results:
            return "No test results available. Run tests first."

        total_tests = len(self.results)
        successful_tests = sum(1 for r in self.results if r.get('success', False))
        failed_tests = total_tests - successful_tests

        avg_keyword_acc = sum(r['keyword_accuracy'] for r in self.results) / total_tests
        avg_supplement_acc = sum(r['supplement_accuracy'] for r in self.results) / total_tests
        avg_overall_acc = sum(r['overall_accuracy'] for r in self.results) / total_tests

        # ── Section 1: Summary (unchanged) ──
        report_lines = [
            "=" * 80,
            "TEST REPORT — Safety Tests",
            "=" * 80,
            f"Dataset: {self.dataset_name}",
            "",
            f"Total Tests:  {total_tests}",
            f"Successful:   {successful_tests} ({successful_tests / total_tests:.1%})",
            f"Failed:       {failed_tests} ({failed_tests / total_tests:.1%})",
            "",
            "Average Accuracies:",
            f"  Keyword Accuracy:     {avg_keyword_acc:.1%}",
            f"  Supplement Accuracy:  {avg_supplement_acc:.1%}",
            f"  Overall Accuracy:     {avg_overall_acc:.1%}",
            "",
        ]

        # ── Section 2: Detailed Test Results ──
        report_lines += [
            "=" * 80,
            "DETAILED TEST RESULTS",
            "=" * 80,
            "",
        ]

        for result in self.results:
            status = "✓ PASS" if result.get('success') else "✗ FAIL"
            profile = result.get('patient_profile', {})

            report_lines += [
                f"{status}  Test {result['test_id']} — {result['overall_accuracy']:.1%} accuracy",
                "-" * 60,
            ]

            # User question
            report_lines += [
                f"  Question:   {result['question']}",
                f"  Type:       {result.get('test_type', 'unknown')}",
                f"  Desc:       {result.get('description', '')}",
                "",
            ]

            # Patient profile
            report_lines += [
                "  PATIENT PROFILE:",
                f"    Medications:          {', '.join(profile.get('medications', [])) or 'None'}",
                f"    Supplements:          {', '.join(profile.get('supplements', [])) or 'None'}",
                f"    Conditions:           {', '.join(profile.get('conditions', [])) or 'None'}",
                f"    Dietary Restrictions: {', '.join(profile.get('dietary_restrictions', [])) or 'None'}",
                "",
            ]

            # Accuracy detail
            keyword_scores = result.get('keyword_scores', {})
            report_lines += [
                "  ACCURACY:",
                f"    Keyword:    {result['keyword_accuracy']:.1%}  "
                f"(found: {', '.join(result['keywords_found']) or 'none'})",
            ]
            if keyword_scores:
                report_lines.append("    Semantic scores per keyword:")
                for kw, score in keyword_scores.items():
                    status_icon = "✓" if score >= self.SIMILARITY_THRESHOLD else "✗"
                    report_lines.append(
                        f"      {status_icon} '{kw}': {score:.3f}"
                        f"  (threshold: {self.SIMILARITY_THRESHOLD})"
                    )
            if result.get('keywords_missing'):
                report_lines.append(
                    f"    Missing keywords:    {', '.join(result['keywords_missing'])}"
                )
            if result.get('supplements_missing'):
                report_lines.append(
                    f"    Missing supplements: {', '.join(result['supplements_missing'])}"
                )
            report_lines.append("")

            # Safety queries — one block per supplement
            safety_queries = result.get('generated_safety_queries', [])
            if safety_queries:
                report_lines.append("  SAFETY QUERIES:")
                for entry in safety_queries:
                    supplement = entry.get('supplement', 'Unknown')
                    executed = entry.get('executed', False)
                    error = entry.get('error', None)
                    cypher = entry.get('cypher', '')

                    report_lines += [
                        f"    Supplement: {supplement}",
                        f"      Executed: {executed}",
                        f"      Error:    {error if error else 'None'}",
                        f"      Cypher:",
                    ]
                    # Indent each line of the Cypher for readability
                    if cypher:
                        for line in cypher.strip().splitlines():
                            report_lines.append(f"        {line}")
                    else:
                        report_lines.append("        (no query generated)")
                    report_lines.append("")
            else:
                report_lines += ["  SAFETY QUERIES: None", ""]

            # Interactions found
            interactions = result.get('safety_interactions', [])
            if interactions:
                report_lines.append("  INTERACTIONS FOUND:")
                for ix in interactions:
                    supplement = ix.get('supplement', '?')
                    target = ix.get('target', '?')
                    pathway = ix.get('pathway', '?')
                    severity = ix.get('severity', '?')
                    description = ix.get('description', '')
                    detail = ix.get('detail', '')
                    report_lines.append(
                        f"    [{severity}] {supplement} ↔ {target} | "
                        f"Pathway: {pathway}"
                    )
                    if description:
                        report_lines.append(f"      Description: {description}")
                    if detail:
                        report_lines.append(f"      Detail:      {detail}")
                report_lines.append("")
            else:
                report_lines += ["  INTERACTIONS FOUND: None", ""]

            # Final answer
            report_lines += [
                "  FINAL ANSWER:",
            ]
            final_answer = result.get('final_answer', '')
            for line in final_answer.strip().splitlines():
                report_lines.append(f"    {line}")
            report_lines += ["", ""]

        report = "\n".join(report_lines)

        # ── Save reports ──
        if output_path is None:
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            folder_name = f"test_report_safety_{timestamp}"

            # If a folder with this timestamp already exists, add a numeric suffix
            reports_dir = self.tests_dir / "reports"
            reports_dir.mkdir(exist_ok=True)
            run_folder = reports_dir / folder_name
            if run_folder.exists():
                suffix = 1
                while (reports_dir / f"{folder_name}_{suffix}").exists():
                    suffix += 1
                run_folder = reports_dir / f"{folder_name}_{suffix}"

            run_folder.mkdir(parents=True)
            output_path = run_folder / "report.txt"
        else:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(report)

        json_path = output_path.with_name("report.json")
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump({
                'dataset_name': self.dataset_name,
                'test_type': self.test_type,
                'summary': {
                    'total_tests': total_tests,
                    'successful': successful_tests,
                    'failed': failed_tests,
                    'avg_keyword_accuracy': avg_keyword_acc,
                    'avg_supplement_accuracy': avg_supplement_acc,
                    'avg_overall_accuracy': avg_overall_acc,
                },
                'results': self.results,
            }, f, indent=2)

        print(f"\n📄 Report saved to {output_path}")
        print(f"📄 JSON saved to   {json_path}")

        return report


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='Run safety tests against golden dataset')
    parser.add_argument(
        '--dataset',
        type=str,
        default='golden_dataset_safety',
        help='Name of the dataset without .csv extension (default: golden_dataset_safety)'
    )
    parser.add_argument(
        '--dataset-path',
        type=str,
        default=None,
        help='Direct path to CSV file (overrides --dataset)'
    )
    parser.add_argument(
        '--output',
        type=str,
        default=None,
        help='Path to save report (default: tests/safety/test_report_safety_{timestamp}.txt)'
    )
    parser.add_argument(
        '--test-id',
        type=str,
        default=None,
        help='Run only a specific test ID'
    )

    args = parser.parse_args()

    if args.dataset_path:
        runner = SafetyTestRunner(golden_dataset_path=args.dataset_path)
    else:
        runner = SafetyTestRunner(dataset_name=args.dataset)

    runner.load_test_cases()

    if args.test_id:
        test_case = next((tc for tc in runner.test_cases if tc['test_id'] == args.test_id), None)
        if not test_case:
            print(f"❌ Test ID {args.test_id} not found")
            return
        result = runner.run_test_case(test_case)
        runner.results = [result]
    else:
        runner.run_all_tests()

    report = runner.generate_report(output_path=args.output)
    print("\n" + report)


if __name__ == "__main__":
    main()