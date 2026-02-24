"""
Graph Builder - LangGraph Workflow Construction

Builds the agentic workflow using LangGraph.
Defines nodes, edges, and entry point.

Current phase: entity_extractor → entity_normalizer only.
Supervisor, specialists, and synthesis nodes are commented out
and will be uncommented as each phase is built.
"""

from langgraph.graph import StateGraph, END

from src.workflow.state import ConversationState, InputState
from src.workflow.routing import NodeNames, route_supervisor_decision
from src.agents.entity_extractor import entity_extractor
from src.agents.entity_normalizer import entity_normalizer

# ── Uncomment as each phase is built ──
# from agents.supervisor import supervisor_agent
# from agents.synthesis_agent import synthesis_agent
# from specialists.safety_check import safety_check
# from specialists.deficiency_check import deficiency_check
# from specialists.recommendation import recommendation


def build_workflow():
    """
    Build and compile the LangGraph workflow.

    Current phase wires only:
        entity_extractor → entity_normalizer → END

    Future phases will add:
        → supervisor → [safety_check | deficiency_check | recommendation] → synthesis → END

    Returns:
        Compiled LangGraph workflow
    """
    print("🏗️  Building workflow graph...")

    workflow = StateGraph(ConversationState, input=InputState)

    # ==================== PHASE 1: PRE-PROCESSING NODES ====================

    print(f"   Adding node: {NodeNames.ENTITY_EXTRACTOR}")
    workflow.add_node(NodeNames.ENTITY_EXTRACTOR, entity_extractor)

    print(f"   Adding node: {NodeNames.ENTITY_NORMALIZER}")
    workflow.add_node(NodeNames.ENTITY_NORMALIZER, entity_normalizer)

    # ==================== PHASE 2: DYNAMIC LOOP NODES ====================
    # Uncomment when supervisor + specialists are ready

    # print(f"   Adding node: {NodeNames.SUPERVISOR}")
    # workflow.add_node(NodeNames.SUPERVISOR, supervisor_agent)

    # print(f"   Adding node: {NodeNames.SAFETY_CHECK}")
    # workflow.add_node(NodeNames.SAFETY_CHECK, safety_check)

    # print(f"   Adding node: {NodeNames.DEFICIENCY_CHECK}")
    # workflow.add_node(NodeNames.DEFICIENCY_CHECK, deficiency_check)

    # print(f"   Adding node: {NodeNames.RECOMMENDATION}")
    # workflow.add_node(NodeNames.RECOMMENDATION, recommendation)

    # ==================== PHASE 3: SYNTHESIS NODE ====================
    # Uncomment when synthesis agent is ready

    # print(f"   Adding node: {NodeNames.SYNTHESIS}")
    # workflow.add_node(NodeNames.SYNTHESIS, synthesis_agent)

    # ==================== EDGES: PHASE 1 ====================

    print(f"   Edge: {NodeNames.ENTITY_EXTRACTOR} → {NodeNames.ENTITY_NORMALIZER}")
    workflow.add_edge(NodeNames.ENTITY_EXTRACTOR, NodeNames.ENTITY_NORMALIZER)

    # Phase 1 ends at entity_normalizer for now
    print(f"   Edge: {NodeNames.ENTITY_NORMALIZER} → END")
    workflow.add_edge(NodeNames.ENTITY_NORMALIZER, END)

    # ==================== EDGES: PHASE 2 ====================
    # Uncomment when supervisor + specialists are ready

    # Linear handoff from pre-processing to dynamic loop
    # workflow.add_edge(NodeNames.ENTITY_NORMALIZER, NodeNames.SUPERVISOR)

    # Conditional routing from supervisor
    # workflow.add_conditional_edges(
    #     NodeNames.SUPERVISOR,
    #     route_supervisor_decision,
    #     {
    #         NodeNames.SAFETY_CHECK: NodeNames.SAFETY_CHECK,
    #         NodeNames.DEFICIENCY_CHECK: NodeNames.DEFICIENCY_CHECK,
    #         NodeNames.RECOMMENDATION: NodeNames.RECOMMENDATION,
    #         NodeNames.SYNTHESIS: NodeNames.SYNTHESIS,
    #         NodeNames.SUPERVISOR: NodeNames.SUPERVISOR,  # loop back
    #         NodeNames.END: END
    #     }
    # )

    # Specialists always return to supervisor
    # workflow.add_edge(NodeNames.SAFETY_CHECK, NodeNames.SUPERVISOR)
    # workflow.add_edge(NodeNames.DEFICIENCY_CHECK, NodeNames.SUPERVISOR)
    # workflow.add_edge(NodeNames.RECOMMENDATION, NodeNames.SUPERVISOR)

    # ==================== EDGES: PHASE 3 ====================
    # Uncomment when synthesis is ready

    # workflow.add_edge(NodeNames.SYNTHESIS, END)

    # ==================== ENTRY POINT ====================

    print(f"   Entry point: {NodeNames.ENTITY_EXTRACTOR}")
    workflow.set_entry_point(NodeNames.ENTITY_EXTRACTOR)

    # ==================== COMPILE ====================

    print("   Compiling workflow...")
    compiled = workflow.compile()

    print("✅ Workflow built successfully!\n")
    return compiled