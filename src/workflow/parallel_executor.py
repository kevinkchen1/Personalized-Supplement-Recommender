"""
Parallel Executor - Run Multiple Agents in Parallel

Executes safety, deficiency, and recommendation agents in parallel
for complex queries that require multiple check types.
"""

from typing import Dict, Any, List
from concurrent.futures import ThreadPoolExecutor, as_completed
import copy


def execute_agents_in_parallel(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute required agents in parallel based on question analysis.
    
    Args:
        state: Current conversation state with question_analysis
    
    Returns:
        Updated state with results from all executed agents
    """
    print("\n" + "=" * 60)
    print("⚡ PARALLEL EXECUTOR: Running agents in parallel...")
    print("=" * 60)
    
    # Get requirements from question analysis
    needs_safety = state.get('needs_safety_check', False)
    needs_deficiency = state.get('needs_deficiency_check', False)
    needs_recommendations = state.get('needs_recommendations', False)
    
    # Collect tasks to run
    tasks = []
    
    if needs_safety:
        tasks.append(('safety', _run_safety_agent))
    
    if needs_deficiency:
        tasks.append(('deficiency', _run_deficiency_agent))
    
    if needs_recommendations:
        tasks.append(('recommendations', _run_recommendation_agent))
    
    if not tasks:
        print("   ⚠️  No agents to run")
        return state
    
    print(f"   Running {len(tasks)} agent(s) in parallel...")
    
    # Execute tasks in parallel
    results = {}
    
    with ThreadPoolExecutor(max_workers=len(tasks)) as executor:
        # Submit all tasks
        future_to_task = {
            executor.submit(task_func, state): task_name
            for task_name, task_func in tasks
        }
        
        # Collect results as they complete
        for future in as_completed(future_to_task):
            task_name = future_to_task[future]
            try:
                result = future.result()
                results[task_name] = result
                print(f"   ✓ {task_name} agent completed")
            except Exception as e:
                print(f"   ✗ {task_name} agent failed: {e}")
                results[task_name] = {'error': str(e)}
    
    # Merge results into state
    if 'safety' in results:
        safety_result = results['safety']
        if 'error' not in safety_result:
            state['safety_checked'] = True
            state['safety_results'] = safety_result.get('safety_results')
            if 'evidence_chain' in safety_result:
                state.setdefault('evidence_chain', []).extend(safety_result['evidence_chain'])
            if 'query_history' in safety_result:
                state.setdefault('query_history', []).extend(safety_result['query_history'])
    
    if 'deficiency' in results:
        deficiency_result = results['deficiency']
        if 'error' not in deficiency_result:
            state['deficiency_checked'] = True
            state['deficiency_results'] = deficiency_result.get('deficiency_results')
            if 'evidence_chain' in deficiency_result:
                state.setdefault('evidence_chain', []).extend(deficiency_result['evidence_chain'])
            if 'query_history' in deficiency_result:
                state.setdefault('query_history', []).extend(deficiency_result['query_history'])
    
    if 'recommendations' in results:
        rec_result = results['recommendations']
        if 'error' not in rec_result:
            state['recommendations_checked'] = True
            state['recommendation_results'] = rec_result.get('recommendation_results')
            if 'evidence_chain' in rec_result:
                state.setdefault('evidence_chain', []).extend(rec_result['evidence_chain'])
            if 'query_history' in rec_result:
                state.setdefault('query_history', []).extend(rec_result['query_history'])
    
    print("=" * 60 + "\n")
    
    return state


def _run_safety_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    """Run safety check agent."""
    from agents.safety_check_agent import SafetyCheckAgent
    
    graph_interface = state.get('graph_interface')
    if not graph_interface:
        return {'error': 'No graph_interface available'}
    
    try:
        agent = SafetyCheckAgent(graph_interface)
        # Create a copy of state for thread safety
        state_copy = copy.deepcopy(state)
        result_state = agent.run(state_copy)
        
        return {
            'safety_results': result_state.get('safety_results'),
            'evidence_chain': result_state.get('evidence_chain', []),
            'query_history': result_state.get('query_history', [])
        }
    except Exception as e:
        return {'error': str(e)}


def _run_deficiency_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    """Run deficiency check agent."""
    from agents.deficiency_agent import DietaryDeficiencyAgent
    
    graph_interface = state.get('graph_interface')
    if not graph_interface:
        return {'error': 'No graph_interface available'}
    
    try:
        agent = DietaryDeficiencyAgent(graph_interface)
        # Create a copy of state for thread safety
        state_copy = copy.deepcopy(state)
        result_state = agent.run(state_copy)
        
        return {
            'deficiency_results': result_state.get('deficiency_results'),
            'evidence_chain': result_state.get('evidence_chain', []),
            'query_history': result_state.get('query_history', [])
        }
    except Exception as e:
        return {'error': str(e)}


def _run_recommendation_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    """Run recommendation agent."""
    from agents.recommendation_agent import RecommendationAgent
    
    graph_interface = state.get('graph_interface')
    if not graph_interface:
        return {'error': 'No graph_interface available'}
    
    try:
        agent = RecommendationAgent(graph_interface)
        # Create a copy of state for thread safety
        state_copy = copy.deepcopy(state)
        result_state = agent.run(state_copy)
        
        return {
            'recommendation_results': result_state.get('recommendation_results'),
            'evidence_chain': result_state.get('evidence_chain', []),
            'query_history': result_state.get('query_history', [])
        }
    except Exception as e:
        return {'error': str(e)}


def parallel_executor(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main entry point for parallel executor (LangGraph node function).
    
    Args:
        state: Current conversation state
    
    Returns:
        Updated state with results from parallel agent execution
    """
    return execute_agents_in_parallel(state)

