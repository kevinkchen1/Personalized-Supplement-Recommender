"""
Query Executor Tool - Safe Query Execution

Executes Cypher queries on Neo4j database:
- Handles errors gracefully
- Validates query results
- Provides retry logic for transient failures
- Logs query performance

Role: Database executor for agents
"""

from typing import Dict, Any, List, Optional
import time


class QueryExecutor:
    """
    Safely executes Cypher queries on Neo4j
    """
    
    def __init__(self, graph_interface):
        """
        Initialize executor with database connection
        
        Args:
            graph_interface: Neo4j GraphInterface instance
        """
        self.graph = graph_interface
        self.query_history = []  # Track queries for debugging
    
    
    def execute(
        self, 
        query: str, 
        parameters: Optional[Dict] = None,
        retry_count: int = 3
    ) -> Dict[str, Any]:
        """
        Execute a Cypher query with error handling
        
        Args:
            query: Cypher query string
            parameters: Query parameters
            retry_count: Number of retries for transient failures
            
        Returns:
            Dict with:
                - success: bool
                - data: List of result records (if success)
                - count: Number of results
                - error: Error message (if failure)
                - execution_time: Query duration in seconds
                
        Example:
            >>> executor = QueryExecutor(graph_interface)
            >>> result = executor.execute(
            ...     "MATCH (s:Supplement {supplement_id: $id}) RETURN s",
            ...     {"id": "S07"}
            ... )
            >>> if result['success']:
            ...     print(f"Found {result['count']} results")
        """
        start_time = time.time()
        
        if parameters is None:
            parameters = {}
        
        # Log the query
        self._log_query(query, parameters)
        
        # Execute with retry logic
        for attempt in range(retry_count):
            try:
                # Execute query
                raw_results = self.graph.execute_query(query, parameters)
                
                # Process results
                processed_results = self._process_results(raw_results)
                
                execution_time = time.time() - start_time
                
                result = {
                    'success': True,
                    'data': processed_results,
                    'count': len(processed_results),
                    'error': None,
                    'execution_time': execution_time
                }
                
                # Log success
                self._log_success(result)
                
                return result
            
            except Exception as e:
                error_type = type(e).__name__
                error_msg = str(e)
                
                # Check if it's a transient error worth retrying
                if self._is_transient_error(error_type) and attempt < retry_count - 1:
                    print(f"⚠️  Transient error, retrying ({attempt + 1}/{retry_count})...")
                    time.sleep(0.5 * (attempt + 1))  # Exponential backoff
                    continue
                
                # Permanent error or out of retries
                execution_time = time.time() - start_time
                
                result = {
                    'success': False,
                    'data': [],
                    'count': 0,
                    'error': f"{error_type}: {error_msg}",
                    'execution_time': execution_time
                }
                
                # Log failure
                self._log_failure(result, query)
                
                return result
        
        # Should never reach here, but just in case
        return {
            'success': False,
            'data': [],
            'count': 0,
            'error': 'Max retries exceeded',
            'execution_time': time.time() - start_time
        }
    
    
    def execute_multiple(
        self, 
        queries: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Execute multiple queries in sequence
        
        Args:
            queries: List of query dicts from QueryGenerator
                    Each dict has 'query' and 'parameters'
                    
        Returns:
            List of result dicts
            
        Example:
            >>> queries = [
            ...     {'query': query1, 'parameters': params1},
            ...     {'query': query2, 'parameters': params2}
            ... ]
            >>> results = executor.execute_multiple(queries)
            >>> all_data = [r['data'] for r in results if r['success']]
        """
        results = []
        
        for query_dict in queries:
            query = query_dict.get('query')
            parameters = query_dict.get('parameters', {})
            explanation = query_dict.get('explanation', '')
            
            if not query:
                results.append({
                    'success': False,
                    'error': 'No query provided',
                    'data': [],
                    'count': 0
                })
                continue
            
            print(f"📊 Executing: {explanation}")
            result = self.execute(query, parameters)
            
            if result['success']:
                print(f"   ✓ Success: {result['count']} results in {result['execution_time']:.3f}s")
            else:
                print(f"   ✗ Failed: {result['error']}")
            
            results.append(result)
        
        return results
    
    
    def execute_with_fallback(
        self,
        primary_query: Dict[str, Any],
        fallback_query: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute a query with a fallback option if it fails
        
        Args:
            primary_query: Main query to try first
            fallback_query: Alternative query if primary fails
            
        Returns:
            Result dict
        """
        # Try primary query
        result = self.execute(
            primary_query['query'],
            primary_query.get('parameters', {})
        )
        
        # If successful or no fallback, return result
        if result['success'] or not fallback_query:
            return result
        
        # Try fallback
        print("⚠️  Primary query failed, trying fallback...")
        fallback_result = self.execute(
            fallback_query['query'],
            fallback_query.get('parameters', {})
        )
        
        # Mark that this is from fallback
        fallback_result['from_fallback'] = True
        
        return fallback_result
    
    
    def _process_results(self, raw_results: Any) -> List[Dict]:
        """
        Process raw Neo4j results into clean dicts
        
        Args:
            raw_results: Raw results from Neo4j driver
            
        Returns:
            List of dict records
        """
        # TODO: Adjust based on your GraphInterface's return format
        
        # If already a list of dicts, return as-is
        if isinstance(raw_results, list):
            return raw_results
        
        # If it's a Neo4j result object, convert to dicts
        processed = []
        try:
            for record in raw_results:
                # Convert Neo4j Record to dict
                if hasattr(record, 'data'):
                    processed.append(record.data())
                elif hasattr(record, 'items'):
                    processed.append(dict(record.items()))
                else:
                    processed.append(dict(record))
        except Exception as e:
            print(f"⚠️  Error processing results: {e}")
            # Try to return raw results if processing fails
            return [raw_results] if raw_results else []
        
        return processed
    
    
    def _is_transient_error(self, error_type: str) -> bool:
        """
        Check if error is transient and worth retrying
        
        Args:
            error_type: Type of exception
            
        Returns:
            True if transient, False otherwise
        """
        transient_errors = [
            'TransientError',
            'ServiceUnavailable',
            'SessionExpired',
            'ConnectionError',
            'TimeoutError'
        ]
        
        return error_type in transient_errors
    
    
    def _log_query(self, query: str, parameters: Dict):
        """
        Log query for debugging
        
        Args:
            query: Cypher query
            parameters: Query parameters
        """
        self.query_history.append({
            'query': query,
            'parameters': parameters,
            'timestamp': time.time()
        })
        
        # Keep only last 100 queries
        if len(self.query_history) > 100:
            self.query_history.pop(0)
    
    
    def _log_success(self, result: Dict):
        """Log successful query execution"""
        # TODO: Implement proper logging
        pass
    
    
    def _log_failure(self, result: Dict, query: str):
        """Log failed query execution"""
        # TODO: Implement proper logging
        print(f"❌ Query failed: {result['error']}")
        print(f"   Query: {query[:100]}...")
    
    
    def get_query_history(self, limit: int = 10) -> List[Dict]:
        """
        Get recent query history for debugging
        
        Args:
            limit: Number of recent queries to return
            
        Returns:
            List of recent queries
        """
        return self.query_history[-limit:]
    
    
    def clear_history(self):
        """Clear query history"""
        self.query_history = []


class BatchQueryExecutor(QueryExecutor):
    """
    Extended executor for batch operations
    """
    
    def execute_batch(
        self,
        queries: List[Dict[str, Any]],
        parallel: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Execute multiple queries, optionally in parallel
        
        Args:
            queries: List of query dicts
            parallel: If True, execute in parallel (requires async setup)
            
        Returns:
            List of results
        """
        if parallel:
            # TODO: Implement parallel execution with asyncio
            print("⚠️  Parallel execution not yet implemented, using sequential")
        
        return self.execute_multiple(queries)


# Helper functions for agents
def execute_safety_checks(
    graph_interface,
    supplement_id: str,
    drug_ids: List[str]
) -> Dict[str, List]:
    """
    Execute all safety check queries and aggregate results
    
    Args:
        graph_interface: Neo4j connection
        supplement_id: Supplement to check
        drug_ids: Medications to check against
        
    Returns:
        Dict with:
            - direct_interactions: List of direct interactions
            - similar_effects: List of effect overlaps
            - metabolism_conflicts: List of metabolism issues
            - all_issues: Combined list
    """
    from tools.query_generator import generate_safety_queries
    
    executor = QueryExecutor(graph_interface)
    
    # Generate queries
    queries = generate_safety_queries(supplement_id, drug_ids)
    
    # Execute all queries
    results = executor.execute_multiple(queries)
    
    # Aggregate results
    aggregated = {
        'direct_interactions': results[0]['data'] if results[0]['success'] else [],
        'similar_effects': results[1]['data'] if results[1]['success'] else [],
        'metabolism_conflicts': results[2]['data'] if results[2]['success'] else [],
        'all_issues': []
    }
    
    # Combine all issues
    for result in results:
        if result['success']:
            aggregated['all_issues'].extend(result['data'])
    
    return aggregated


def execute_deficiency_checks(
    graph_interface,
    dietary_restrictions: List[str],
    drug_ids: List[str]
) -> Dict[str, Any]:
    """
    Execute all deficiency check queries and aggregate results
    
    Args:
        graph_interface: Neo4j connection
        dietary_restrictions: List of diet restrictions
        drug_ids: List of medications
        
    Returns:
        Dict with deficiency information
    """
    from tools.query_generator import generate_deficiency_queries
    
    executor = QueryExecutor(graph_interface)
    
    # Generate queries
    queries = generate_deficiency_queries(dietary_restrictions, drug_ids)
    
    # Execute all queries
    results = executor.execute_multiple(queries)
    
    # Aggregate by nutrient
    nutrients_at_risk = {}
    
    for result in results:
        if result['success']:
            for record in result['data']:
                nutrient = record.get('nutrient')
                if nutrient not in nutrients_at_risk:
                    nutrients_at_risk[nutrient] = {
                        'sources': [],
                        'rdi': record.get('rdi'),
                        'symptoms': record.get('symptoms')
                    }
                
                source = record.get('source')
                if source == 'diet':
                    nutrients_at_risk[nutrient]['sources'].append(
                        f"Diet: {record.get('diet')}"
                    )
                else:
                    nutrients_at_risk[nutrient]['sources'].append(
                        f"Medication: {record.get('medication')}"
                    )
    
    return nutrients_at_risk


if __name__ == "__main__":
    # Quick test (requires actual database connection)
    from graph.graph_interface import GraphInterface
    import os
    
    # Initialize
    graph = GraphInterface(
        uri=os.getenv("NEO4J_URI"),
        user=os.getenv("NEO4J_USER"),
        password=os.getenv("NEO4J_PASSWORD")
    )
    
    executor = QueryExecutor(graph)
    
    # Test simple query
    test_query = """
    MATCH (s:Supplement)
    RETURN s.supplement_name as name
    LIMIT 5
    """
    
    result = executor.execute(test_query)
    
    if result['success']:
        print(f"✓ Found {result['count']} supplements")
        for record in result['data']:
            print(f"  - {record['name']}")
    else:
        print(f"✗ Query failed: {result['error']}")
