"""
Routing - Workflow Traffic Controller

Maps supervisor decisions to node names.
No intelligence here — pure string-to-node-name mapping.

Current phase: No routing needed (linear pipeline only).
Supervisor routing will be activated in Phase 2.
"""

from typing import Any, Dict


# ==================== NODE NAMES ====================

class NodeNames:
    """
    Constants for all node names in the workflow.
    Used in graph_builder.py and routing functions.
    """
    # Phase 1: Pre-processing pipeline
    ENTITY_EXTRACTOR = "entity_extractor"
    ENTITY_NORMALIZER = "entity_normalizer"

    # Phase 2: Dynamic routing loop
    SUPERVISOR = "supervisor"
    SAFETY_CHECK = "safety_check"
    DEFICIENCY_CHECK = "deficiency_check"
    RECOMMENDATION = "recommendation"

    # Phase 3: Final output
    SYNTHESIS = "synthesis"

    # LangGraph END sentinel
    END = "END"


# ==================== SUPERVISOR ROUTING ====================
# Activated in Phase 2 when supervisor is added.

def route_supervisor_decision(state: Dict[str, Any]) -> str:
    """
    Route based on supervisor's decision string.

    Reads state['supervisor_decision'] and maps it to a node name.
    Called by LangGraph's conditional edge from the supervisor node.

    Decision strings must match exactly what supervisor.py writes
    to state['supervisor_decision'].

    Args:
        state: Current ConversationState

    Returns:
        Node name string to route to next
    """
    decision = state.get('supervisor_decision', '')

    route_map = {
        'check_safety':       NodeNames.SAFETY_CHECK,
        'check_deficiency':   NodeNames.DEFICIENCY_CHECK,
        'get_recommendations': NodeNames.RECOMMENDATION,
        'synthesize':         NodeNames.SYNTHESIS,
        'loop_back':          NodeNames.SUPERVISOR,
    }

    next_node = route_map.get(decision, NodeNames.END)
    print(f"🚦 ROUTING: '{decision}' → {next_node}")
    return next_node