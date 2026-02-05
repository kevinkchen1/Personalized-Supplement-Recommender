"""
Routing Logic - Traffic Controller

Routes between nodes based on supervisor decisions and state.
This is the "traffic controller" that determines which node to visit next.

Key Concept:
- Routing functions read state and return a node name (string)
- LangGraph uses the node name to determine where to go
- No intelligence here - just simple mapping based on state
"""

from typing import Dict, Any, Literal


# ==================== NODE NAMES ====================
# Define all possible node names as constants

class NodeNames:
    """Constants for all node names in the workflow"""
    SUPERVISOR = "supervisor"
    SAFETY_CHECK = "safety_check"
    DEFICIENCY_CHECK = "deficiency_check"
    RECOMMENDATION = "recommendation"
    SYNTHESIS = "synthesis"
    END = "END"


# ==================== ROUTING FUNCTIONS ====================

def route_supervisor_decision(state: Dict[str, Any]) -> str:
    """
    Route based on supervisor's decision
    
    This is the main routing function that determines what happens
    after the supervisor analyzes the situation.
    
    Args:
        state: Current conversation state
        
    Returns:
        Node name to visit next (string)
        
    Routing Logic:
        - "check_safety" → safety_check node
        - "check_deficiency" → deficiency_check node
        - "check_recommendations" → recommendation node
        - "finish" → synthesis node
        - "loop_back" → supervisor node (loop!)
        - default → END
    """
    decision = state.get('supervisor_decision', '')
    
    # Map supervisor decisions to node names
    # NOTE: Must match the exact strings supervisor._make_decision() returns
    route_map = {
        # Safety
        'check_safety': NodeNames.SAFETY_CHECK,
        # Deficiency
        'check_deficiency': NodeNames.DEFICIENCY_CHECK,
        # Recommendations (supervisor uses 'get_recommendations')
        'get_recommendations': NodeNames.RECOMMENDATION,
        'check_recommendations': NodeNames.RECOMMENDATION,  # alias
        # Synthesis (supervisor uses 'synthesize')
        'synthesize': NodeNames.SYNTHESIS,
        'finish': NodeNames.SYNTHESIS,  # alias
        # Loop back (supervisor uses 'need_more_evidence' or 'clarify')
        'need_more_evidence': NodeNames.SUPERVISOR,
        'clarify': NodeNames.SUPERVISOR,
        'loop_back': NodeNames.SUPERVISOR,  # alias
    }
    
    # Get the route, default to END if unknown
    next_node = route_map.get(decision, NodeNames.END)
    
    # Debug logging
    print(f"🚦 ROUTING: '{decision}' → {next_node}")
    
    return next_node


def route_after_specialist(state: Dict[str, Any]) -> str:
    """
    Route after a specialist agent finishes
    
    After safety, deficiency, or recommendation agents finish,
    always go back to supervisor to decide what's next.
    
    Args:
        state: Current conversation state
        
    Returns:
        Always returns 'supervisor' (go back to supervisor)
    """
    print(f"🚦 ROUTING: Specialist done → back to supervisor")
    return NodeNames.SUPERVISOR


def route_synthesis_complete(state: Dict[str, Any]) -> str:
    """
    Route after synthesis is complete
    
    Once synthesis creates the final answer, we're done!
    
    Args:
        state: Current conversation state
        
    Returns:
        Always returns 'END'
    """
    print(f"🚦 ROUTING: Synthesis complete → END")
    return NodeNames.END


# ==================== CONDITIONAL ROUTING WITH CHECKS ====================

def route_with_safety_check(state: Dict[str, Any]) -> str:
    """
    Enhanced routing with safety checks
    
    Includes additional logic to prevent issues:
    - Max iterations check
    - Error detection
    - Fallback to synthesis if needed
    
    Args:
        state: Current conversation state
        
    Returns:
        Node name to visit next
    """
    # Check for error state
    if state.get('error_message'):
        print("🚦 ROUTING: Error detected → synthesis")
        return NodeNames.SYNTHESIS
    
    # Check max iterations
    if state.get('iterations', 0) >= 10:
        print("🚦 ROUTING: Max iterations reached → synthesis")
        return NodeNames.SYNTHESIS
    
    # Otherwise use normal routing
    return route_supervisor_decision(state)


def route_based_on_confidence(state: Dict[str, Any]) -> str:
    """
    Route based on confidence level
    
    If confidence is too low, might need more investigation.
    
    Args:
        state: Current conversation state
        
    Returns:
        Node name to visit next
    """
    confidence = state.get('confidence_level', 0.0)
    iterations = state.get('iterations', 0)
    decision = state.get('supervisor_decision', '')
    
    # If confidence is very low and we haven't tried much, loop back
    if confidence < 0.5 and iterations < 5:
        print(f"🚦 ROUTING: Low confidence ({confidence:.2f}) → loop back to supervisor")
        return NodeNames.SUPERVISOR
    
    # If we've tried enough times, move on to synthesis
    if iterations >= 5:
        print(f"🚦 ROUTING: Max investigation attempts → synthesis")
        return NodeNames.SYNTHESIS
    
    # Otherwise follow supervisor's decision
    return route_supervisor_decision(state)


# ==================== TYPED ROUTING (For Better Type Safety) ====================

def route_supervisor_typed(
    state: Dict[str, Any]
) -> Literal["safety_check", "deficiency_check", "recommendation", "synthesis", "supervisor", "END"]:
    """
    Typed version of supervisor routing for better IDE support
    
    Args:
        state: Current conversation state
        
    Returns:
        Literal type for better type checking
    """
    return route_supervisor_decision(state)


# ==================== DEBUGGING HELPERS ====================

def get_routing_summary(state: Dict[str, Any]) -> str:
    """
    Get a summary of current routing state
    
    Args:
        state: Current conversation state
        
    Returns:
        Summary string for debugging
    """
    decision = state.get('supervisor_decision', 'None')
    iterations = state.get('iterations', 0)
    confidence = state.get('confidence_level', 0.0)
    
    summary = f"""
Routing State:
--------------
Supervisor Decision: {decision}
Iterations: {iterations}/10
Confidence: {confidence:.2f}

What's Been Done:
  Safety: {'✓' if state.get('safety_checked') else '✗'}
  Deficiency: {'✓' if state.get('deficiency_checked') else '✗'}
  Recommendations: {'✓' if state.get('recommendations_checked') else '✗'}

Next Node: {route_supervisor_decision(state)}
"""
    return summary


def trace_routing_path(states: list[Dict[str, Any]]) -> list[str]:
    """
    Trace the routing path through multiple states
    
    Useful for debugging to see the complete path taken.
    
    Args:
        states: List of states from workflow execution
        
    Returns:
        List of node names visited
    """
    path = []
    for state in states:
        decision = state.get('supervisor_decision', '')
        next_node = route_supervisor_decision(state)
        path.append(f"{decision} → {next_node}")
    
    return path


# ==================== ROUTING RULES DOCUMENTATION ====================

ROUTING_RULES = """
Routing Rules:
==============

1. START → supervisor
   - Workflow always begins at supervisor

2. supervisor → [conditional]
   - check_safety → safety_check
   - check_deficiency → deficiency_check
   - check_recommendations → recommendation
   - finish → synthesis
   - loop_back → supervisor (creates loop!)

3. safety_check → supervisor
   - Always returns to supervisor after check

4. deficiency_check → supervisor
   - Always returns to supervisor after check

5. recommendation → supervisor
   - Always returns to supervisor after check

6. synthesis → END
   - Final node, ends workflow

Loop Prevention:
----------------
- Max iterations: 10
- If iterations >= 10, force route to synthesis
- Confidence threshold can also trigger early synthesis

Example Flow:
-------------
START 
  → supervisor (decision: check_safety)
  → safety_check
  → supervisor (decision: check_deficiency)
  → deficiency_check
  → supervisor (decision: finish)
  → synthesis
  → END
"""


# ==================== TESTING ====================

if __name__ == "__main__":
    print(ROUTING_RULES)
    print("\n" + "="*50 + "\n")
    
    # Test routing with different decisions
    test_cases = [
        {'supervisor_decision': 'check_safety', 'iterations': 1},
        {'supervisor_decision': 'check_deficiency', 'iterations': 2},
        {'supervisor_decision': 'finish', 'iterations': 3},
        {'supervisor_decision': 'loop_back', 'iterations': 4},
        {'supervisor_decision': 'unknown', 'iterations': 5},
    ]
    
    for state in test_cases:
        decision = state['supervisor_decision']
        result = route_supervisor_decision(state)
        print(f"Decision: '{decision}' → Routes to: '{result}'")
    
    print("\n" + "="*50 + "\n")
    
    # Test max iterations routing
    test_state = {
        'supervisor_decision': 'check_safety',
        'iterations': 10,
        'confidence_level': 0.8
    }
    
    print("Testing max iterations:")
    print(f"Iterations: {test_state['iterations']}")
    result = route_with_safety_check(test_state)
    print(f"Routes to: {result}")
    
    print("\n" + "="*50 + "\n")
    
    # Test confidence-based routing
    test_state = {
        'supervisor_decision': 'check_deficiency',
        'iterations': 2,
        'confidence_level': 0.4
    }
    
    print("Testing low confidence routing:")
    print(f"Confidence: {test_state['confidence_level']}")
    print(f"Iterations: {test_state['iterations']}")
    result = route_based_on_confidence(test_state)
    print(f"Routes to: {result}")
