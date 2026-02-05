"""
Query Executor Tool - Safe Query Execution

Executes Cypher queries on Neo4j database:
- Handles errors gracefully with retry logic for transient failures
- Validates and logs query results for debugging
- Provides convenience wrappers that pair with QueryGenerator

Role: Database runner for agents

Usage:
    from tools.query_executor import QueryExecutor
    from tools.query_generator import QueryGenerator

    executor = QueryExecutor(graph_interface)
    gen = QueryGenerator()

    # Option A: generate + execute separately
    q = gen.generate_query('comprehensive_safety', {
        'supplement_name': 'Fish Oil',
        'medication_names': ['Warfarin'],
    })
    result = executor.execute(q['query'], q['parameters'])

    # Option B: pass generator output directly
    result = executor.execute_query_dict(q)

    # Option C: use the all-in-one convenience function
    from tools.query_executor import run_safety_check
    results = run_safety_check(graph_interface, 'Fish Oil', ['Warfarin'])
"""

from typing import Dict, Any, List, Optional
import time


class QueryExecutor:
    """
    Safely executes Cypher queries on Neo4j.

    Wraps GraphInterface.execute_query() with:
    - Retry logic for transient connection errors
    - Standardised result format {success, data, count, error, execution_time}
    - Query history for debugging / Streamlit display
    """

    def __init__(self, graph_interface):
        """
        Args:
            graph_interface: A GraphInterface instance (from graph.graph_interface)
        """
        self.graph = graph_interface
        self.query_history: List[Dict] = []

    # ------------------------------------------------------------------
    # Core execution
    # ------------------------------------------------------------------

    def execute(
        self,
        query: str,
        parameters: Optional[Dict] = None,
        retry_count: int = 3,
    ) -> Dict[str, Any]:
        """
        Execute a single Cypher query with error handling and retries.

        Args:
            query: Cypher query string
            parameters: Query parameters (safe against injection)
            retry_count: Max retries for transient failures

        Returns:
            {
                'success': bool,
                'data': List[Dict],   # rows returned
                'count': int,
                'error': str | None,
                'execution_time': float,  # seconds
                'query': str,             # for debugging
                'parameters': dict,       # for debugging
            }
        """
        start_time = time.time()

        if parameters is None:
            parameters = {}

        self._log_query(query, parameters)

        for attempt in range(retry_count):
            try:
                # GraphInterface.execute_query already returns List[Dict]
                raw_results = self.graph.execute_query(query, parameters)

                # Defensive: ensure we always have a list of dicts
                processed = self._process_results(raw_results)

                elapsed = time.time() - start_time

                result = {
                    'success': True,
                    'data': processed,
                    'count': len(processed),
                    'error': None,
                    'execution_time': elapsed,
                    'query': query,
                    'parameters': parameters,
                }
                self._update_history_success(result)
                return result

            except Exception as e:
                error_type = type(e).__name__
                error_msg = str(e)

                if self._is_transient(error_type) and attempt < retry_count - 1:
                    wait = 0.5 * (attempt + 1)
                    print(f"⚠️  Transient error ({error_type}), retrying in {wait:.1f}s "
                          f"({attempt + 1}/{retry_count})...")
                    time.sleep(wait)
                    continue

                elapsed = time.time() - start_time
                result = {
                    'success': False,
                    'data': [],
                    'count': 0,
                    'error': f"{error_type}: {error_msg}",
                    'execution_time': elapsed,
                    'query': query,
                    'parameters': parameters,
                }
                self._update_history_failure(result)
                return result

        # Should never reach here
        return {
            'success': False,
            'data': [],
            'count': 0,
            'error': 'Max retries exceeded',
            'execution_time': time.time() - start_time,
            'query': query,
            'parameters': parameters,
        }

    # ------------------------------------------------------------------
    # Convenience wrappers
    # ------------------------------------------------------------------

    def execute_query_dict(self, query_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a query dict produced by QueryGenerator.generate_query().

        Args:
            query_dict: {
                'query': str,
                'parameters': dict,
                'explanation': str,
                ...
            }

        Returns:
            Standard result dict (same as execute()), plus 'explanation'.
        """
        query = query_dict.get('query')
        parameters = query_dict.get('parameters', {})
        explanation = query_dict.get('explanation', '')

        if not query:
            return {
                'success': False,
                'data': [],
                'count': 0,
                'error': query_dict.get('error', 'No query provided'),
                'execution_time': 0,
                'explanation': explanation,
                'query': None,
                'parameters': parameters,
            }

        result = self.execute(query, parameters)
        result['explanation'] = explanation
        result['query_type'] = query_dict.get('query_type', '')
        return result

    def execute_multiple(
        self,
        queries: List[Dict[str, Any]],
        stop_on_error: bool = False,
        verbose: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Execute a list of query dicts from QueryGenerator in sequence.

        Args:
            queries: List of query dicts (each with 'query', 'parameters', 'explanation')
            stop_on_error: If True, stop executing after first failure
            verbose: Print progress

        Returns:
            List of result dicts (same order as input queries)
        """
        results = []

        for i, query_dict in enumerate(queries, 1):
            explanation = query_dict.get('explanation', f'Query {i}')

            if verbose:
                print(f"📊 [{i}/{len(queries)}] {explanation}")

            result = self.execute_query_dict(query_dict)

            if verbose:
                if result['success']:
                    print(f"   ✅ {result['count']} results ({result['execution_time']:.3f}s)")
                else:
                    print(f"   ❌ {result['error']}")

            results.append(result)

            if stop_on_error and not result['success']:
                print("   ⛔ Stopping due to error")
                break

        return results

    def execute_with_fallback(
        self,
        primary: Dict[str, Any],
        fallback: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Try primary query; if it fails or returns 0 results, try fallback.

        Args:
            primary: Primary query dict
            fallback: Fallback query dict (optional)

        Returns:
            Result dict, with 'from_fallback' key if fallback was used
        """
        result = self.execute_query_dict(primary)

        # Success with data → return
        if result['success'] and result['count'] > 0:
            result['from_fallback'] = False
            return result

        # No fallback → return whatever we got
        if not fallback or not fallback.get('query'):
            result['from_fallback'] = False
            return result

        # Try fallback
        reason = "query failed" if not result['success'] else "0 results"
        print(f"⚠️  Primary {reason}, trying fallback...")
        fallback_result = self.execute_query_dict(fallback)
        fallback_result['from_fallback'] = True
        return fallback_result

    # ------------------------------------------------------------------
    # Result aggregation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def merge_results(results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Merge multiple execution results into one combined result.

        Useful after execute_multiple() to get a single flat list of rows.

        Args:
            results: List of result dicts from execute_multiple()

        Returns:
            {
                'success': bool,          # True if ANY query succeeded
                'data': List[Dict],       # combined rows from all queries
                'count': int,
                'errors': List[str],      # any errors encountered
                'total_execution_time': float,
                'queries_run': int,
                'queries_succeeded': int,
                'by_query_type': Dict     # data grouped by query_type
            }
        """
        all_data = []
        errors = []
        total_time = 0
        succeeded = 0
        by_type: Dict[str, List] = {}

        for r in results:
            total_time += r.get('execution_time', 0)
            if r['success']:
                succeeded += 1
                all_data.extend(r['data'])
                qt = r.get('query_type', 'unknown')
                by_type.setdefault(qt, []).extend(r['data'])
            if r.get('error'):
                errors.append(r['error'])

        return {
            'success': succeeded > 0,
            'data': all_data,
            'count': len(all_data),
            'errors': errors,
            'total_execution_time': total_time,
            'queries_run': len(results),
            'queries_succeeded': succeeded,
            'by_query_type': by_type,
        }

    # ------------------------------------------------------------------
    # Query history (for Streamlit debug panel)
    # ------------------------------------------------------------------

    def get_query_history(self, limit: int = 10) -> List[Dict]:
        """Get the most recent queries (for UI display)."""
        return self.query_history[-limit:]

    def get_last_query(self) -> Optional[Dict]:
        """Get the single most recent query."""
        return self.query_history[-1] if self.query_history else None

    def clear_history(self):
        """Clear query history."""
        self.query_history = []

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _process_results(self, raw_results: Any) -> List[Dict]:
        """
        Ensure results are a clean List[Dict].

        GraphInterface.execute_query() already does record.data(),
        so this is mostly a safety net.
        """
        if raw_results is None:
            return []

        if isinstance(raw_results, list):
            # Already List[Dict] from GraphInterface — pass through
            return raw_results

        # Fallback: try to convert iterator of records
        processed = []
        try:
            for record in raw_results:
                if hasattr(record, 'data'):
                    processed.append(record.data())
                elif isinstance(record, dict):
                    processed.append(record)
                else:
                    processed.append(dict(record))
        except Exception as e:
            print(f"⚠️  Error processing results: {e}")
            return []

        return processed

    @staticmethod
    def _is_transient(error_type: str) -> bool:
        """Check if an error is transient and worth retrying."""
        return error_type in {
            'TransientError',
            'ServiceUnavailable',
            'SessionExpired',
            'ConnectionError',
            'TimeoutError',
            'BrokenPipeError',
        }

    def _log_query(self, query: str, parameters: Dict):
        """Record query in history."""
        self.query_history.append({
            'query': query,
            'parameters': parameters,
            'timestamp': time.time(),
            'status': 'pending',
        })
        # Cap at 100 entries
        if len(self.query_history) > 100:
            self.query_history = self.query_history[-100:]

    def _update_history_success(self, result: Dict):
        """Mark the last history entry as succeeded."""
        if self.query_history:
            self.query_history[-1]['status'] = 'success'
            self.query_history[-1]['count'] = result['count']
            self.query_history[-1]['execution_time'] = result['execution_time']

    def _update_history_failure(self, result: Dict):
        """Mark the last history entry as failed."""
        if self.query_history:
            self.query_history[-1]['status'] = 'failed'
            self.query_history[-1]['error'] = result['error']
            self.query_history[-1]['execution_time'] = result['execution_time']
        print(f"❌ Query failed: {result['error']}")
        print(f"   Query: {result['query'][:120]}...")


# ======================================================================
# Convenience functions for agents
# ======================================================================

def run_safety_check(
    graph_interface,
    supplement_name: str,
    medication_names: List[str],
    verbose: bool = True,
) -> Dict[str, Any]:
    """
    One-call safety check: generate queries + execute + merge results.

    This is the easiest way for an agent to run a full safety check.

    Args:
        graph_interface: Neo4j GraphInterface instance
        supplement_name: e.g. "Fish Oil"
        medication_names: e.g. ["Warfarin", "Aspirin"]
        verbose: Print progress

    Returns:
        Merged result dict with all interaction data across all pathways.
        Key fields:
            'success': bool
            'data': List[Dict]  — all interactions found
            'count': int
            'by_query_type': Dict  — interactions grouped by pathway
    """
    from tools.query_generator import generate_safety_queries

    executor = QueryExecutor(graph_interface)
    queries = generate_safety_queries(supplement_name, medication_names)

    if verbose:
        print(f"\n🔬 Safety check: {supplement_name} vs {medication_names}")
        print(f"   Running {len(queries)} queries...\n")

    results = executor.execute_multiple(queries, verbose=verbose)
    merged = QueryExecutor.merge_results(results)

    if verbose:
        print(f"\n{'='*50}")
        print(f"   Total interactions found: {merged['count']}")
        print(f"   Queries: {merged['queries_succeeded']}/{merged['queries_run']} succeeded")
        print(f"   Time: {merged['total_execution_time']:.3f}s")
        if merged['errors']:
            print(f"   Errors: {merged['errors']}")
        print(f"{'='*50}\n")

    return merged


def run_comprehensive_safety(
    graph_interface,
    supplement_name: str,
    medication_names: List[str],
    verbose: bool = True,
) -> Dict[str, Any]:
    """
    Run the single comprehensive UNION query (all 4 pathways at once).

    More efficient than run_safety_check() (1 query vs 4), but less
    granular in error reporting.

    Args:
        graph_interface: Neo4j GraphInterface instance
        supplement_name: e.g. "Fish Oil"
        medication_names: e.g. ["Warfarin", "Aspirin"]

    Returns:
        Standard result dict from execute().
        Each row in 'data' has a 'pathway' column identifying
        which safety pathway found it.
    """
    from tools.query_generator import generate_comprehensive_safety_query

    executor = QueryExecutor(graph_interface)
    query_dict = generate_comprehensive_safety_query(supplement_name, medication_names)

    if verbose:
        print(f"\n🔬 Comprehensive safety: {supplement_name} vs {medication_names}")

    result = executor.execute_query_dict(query_dict)

    if verbose:
        if result['success']:
            print(f"   ✅ Found {result['count']} interactions")
            # Group by pathway for summary
            pathways: Dict[str, int] = {}
            for row in result['data']:
                p = row.get('pathway', 'unknown')
                pathways[p] = pathways.get(p, 0) + 1
            for p, n in pathways.items():
                print(f"      {p}: {n}")
        else:
            print(f"   ❌ {result['error']}")

    return result


def run_supplement_info(
    graph_interface,
    supplement_name: str,
) -> Dict[str, Any]:
    """
    Get full info about a supplement (ingredients, treats, side effects, etc.)

    Args:
        graph_interface: Neo4j GraphInterface instance
        supplement_name: e.g. "Fish Oil"

    Returns:
        Standard result dict. 'data' will have 0 or 1 rows with
        collected lists of ingredients, symptoms, etc.
    """
    from tools.query_generator import generate_supplement_info_query

    executor = QueryExecutor(graph_interface)
    query_dict = generate_supplement_info_query(supplement_name)
    return executor.execute_query_dict(query_dict)


# ======================================================================
# Quick self-test (requires live database)
# ======================================================================

if __name__ == "__main__":
    import os

    print("=" * 60)
    print("QUERY EXECUTOR - SELF TEST")
    print("=" * 60)

    # Try to connect
    try:
        from graph.graph_interface import GraphInterface

        graph = GraphInterface(
            uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            user=os.getenv("NEO4J_USER", "neo4j"),
            password=os.getenv("NEO4J_PASSWORD", ""),
        )
        print("✅ Connected to Neo4j\n")
    except Exception as e:
        print(f"❌ Cannot connect to Neo4j: {e}")
        print("   Set NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD env vars")
        exit(1)

    executor = QueryExecutor(graph)

    # Test 1: Simple query
    print("--- Test 1: Simple supplement lookup ---")
    r = executor.execute(
        "MATCH (s:Supplement) RETURN s.supplement_name AS name LIMIT 5"
    )
    if r['success']:
        print(f"   ✅ Found {r['count']} supplements:")
        for row in r['data']:
            print(f"      - {row['name']}")
    else:
        print(f"   ❌ {r['error']}")

    # Test 2: Parameterised query
    print("\n--- Test 2: Parameterised medication lookup ---")
    r = executor.execute(
        "MATCH (m:Medication) WHERE toLower(m.medication_name) CONTAINS toLower($name) "
        "RETURN m.medication_name AS name LIMIT 5",
        {'name': 'war'},
    )
    if r['success']:
        print(f"   ✅ Found {r['count']} medications matching 'war':")
        for row in r['data']:
            print(f"      - {row['name']}")
    else:
        print(f"   ❌ {r['error']}")

    # Test 3: QueryGenerator integration
    print("\n--- Test 3: QueryGenerator → Executor integration ---")
    from tools.query_generator import QueryGenerator

    gen = QueryGenerator()
    q = gen.generate_query('find_supplement', {'name': 'Fish'})
    r = executor.execute_query_dict(q)
    print(f"   Explanation: {r.get('explanation')}")
    print(f"   Success: {r['success']}, Count: {r['count']}")

    # Test 4: Full safety check
    print("\n--- Test 4: Full safety check ---")
    safety = run_safety_check(graph, 'Fish Oil', ['Warfarin'])
    print(f"   Interactions found: {safety['count']}")

    # Test 5: Comprehensive safety (single UNION)
    print("\n--- Test 5: Comprehensive safety (UNION) ---")
    comp = run_comprehensive_safety(graph, 'Red Yeast Rice', ['Lipitor'])
    print(f"   Interactions found: {comp['count']}")

    # Test 6: Query history
    print("\n--- Test 6: Query history ---")
    history = executor.get_query_history(limit=3)
    print(f"   Last {len(history)} queries:")
    for h in history:
        status = h.get('status', '?')
        t = h.get('execution_time', 0)
        print(f"      [{status}] {h['query'][:60]}... ({t:.3f}s)")

    print("\n✅ All executor tests complete!")
    graph.close()
