"""
Graph Builder - LangGraph Workflow Construction

Builds the complete agentic workflow using LangGraph:
- Defines all nodes (agents)
- Defines edges (connections between agents)
- Sets up conditional routing
- Compiles the executable workflow

This is where the "map" of the workflow is created.
"""

from langgraph.graph import StateGraph, END
from typing import Optional
import os

# Import state definition
from workflow.state import ConversationState

# Import routing functions
from workflow.routing import (
    route_supervisor_decision,
    route_after_specialist,
    route_synthesis_complete,
    NodeNames
)

# Import agent functions
from agents.supervisor import supervisor_agent
from agents.safety_check_agent import safety_check_agent
from agents.deficiency_agent import deficiency_agent
from agents.recommendation_agent import recommendation_agent
from agents.synthesis_agent import synthesis_agent


def build_workflow(
    enable_safety: bool = True,
    enable_deficiency: bool = True,
    enable_recommendations: bool = True,
    max_iterations: int = 10
):
    """
    Build the complete agentic workflow
    
    Args:
        enable_safety: Whether to enable safety check agent
        enable_deficiency: Whether to enable deficiency agent
        enable_recommendations: Whether to enable recommendation agent
        max_iterations: Maximum supervisor iterations
        
    Returns:
        Compiled LangGraph workflow (CompiledGraph)
        
    Example:
        >>> workflow = build_workflow()
        >>> result = workflow.invoke(initial_state)
        >>> print(result['final_answer'])
    """
    
    # Create the graph with our state definition
    workflow = StateGraph(ConversationState)
    
    print("🏗️  Building workflow graph...")
    
    # ==================== ADD NODES ====================
    # Each node is an agent function that takes state and returns state
    
    print("   Adding supervisor node...")
    workflow.add_node(NodeNames.SUPERVISOR, supervisor_agent)
    
    if enable_safety:
        print("   Adding safety_check node...")
        workflow.add_node(NodeNames.SAFETY_CHECK, safety_check_agent)
    
    if enable_deficiency:
        print("   Adding deficiency_check node...")
        workflow.add_node(NodeNames.DEFICIENCY_CHECK, deficiency_agent)
    
    if enable_recommendations:
        print("   Adding recommendation node...")
        workflow.add_node(NodeNames.RECOMMENDATION, recommendation_agent)
    
    print("   Adding synthesis node...")
    workflow.add_node(NodeNames.SYNTHESIS, synthesis_agent)
    
    # ==================== ADD EDGES ====================
    
    # CONDITIONAL EDGE from supervisor
    # The supervisor can route to different specialists or finish
    print("   Setting up supervisor routing...")
    workflow.add_conditional_edges(
        NodeNames.SUPERVISOR,  # From supervisor
        route_supervisor_decision,  # Use this function to decide
        {
            # Map routing function output to node names
            NodeNames.SAFETY_CHECK: NodeNames.SAFETY_CHECK,
            NodeNames.DEFICIENCY_CHECK: NodeNames.DEFICIENCY_CHECK,
            NodeNames.RECOMMENDATION: NodeNames.RECOMMENDATION,
            NodeNames.SYNTHESIS: NodeNames.SYNTHESIS,
            NodeNames.SUPERVISOR: NodeNames.SUPERVISOR,  # Loop back!
            NodeNames.END: END
        }
    )
    
    # SIMPLE EDGES back to supervisor after specialists
    # After any specialist finishes, go back to supervisor
    if enable_safety:
        print("   Safety agent → Supervisor")
        workflow.add_edge(NodeNames.SAFETY_CHECK, NodeNames.SUPERVISOR)
    
    if enable_deficiency:
        print("   Deficiency agent → Supervisor")
        workflow.add_edge(NodeNames.DEFICIENCY_CHECK, NodeNames.SUPERVISOR)
    
    if enable_recommendations:
        print("   Recommendation agent → Supervisor")
        workflow.add_edge(NodeNames.RECOMMENDATION, NodeNames.SUPERVISOR)
    
    # SIMPLE EDGE from synthesis to END
    # Once synthesis is done, we're finished
    print("   Synthesis → END")
    workflow.add_edge(NodeNames.SYNTHESIS, END)
    
    # ==================== SET ENTRY POINT ====================
    # Workflow always starts at supervisor
    print("   Setting entry point: supervisor")
    workflow.set_entry_point(NodeNames.SUPERVISOR)
    
    # ==================== COMPILE ====================
    print("   Compiling workflow...")
    compiled_workflow = workflow.compile()
    
    print("✅ Workflow built successfully!\n")
    
    return compiled_workflow


def build_workflow_with_checkpoints(
    checkpointer=None,
    **kwargs
):
    """
    Build workflow with checkpoint support for persistence
    
    Checkpoints allow:
    - Saving state at each step
    - Resuming from interruptions
    - Time-travel debugging
    - Human-in-the-loop approval
    
    Args:
        checkpointer: LangGraph checkpointer (e.g., SqliteSaver)
        **kwargs: Additional arguments for build_workflow
        
    Returns:
        Compiled workflow with checkpointing
        
    Example:
        >>> from langgraph.checkpoint.sqlite import SqliteSaver
        >>> memory = SqliteSaver.from_conn_string(":memory:")
        >>> workflow = build_workflow_with_checkpoints(checkpointer=memory)
        >>> 
        >>> # Run with thread_id for persistence
        >>> result = workflow.invoke(
        ...     initial_state,
        ...     {"configurable": {"thread_id": "user-123"}}
        ... )
    """
    # Build base workflow
    workflow = build_workflow(**kwargs)
    
    # TODO: Add checkpointing
    # This requires additional LangGraph setup
    # workflow = workflow.compile(checkpointer=checkpointer)
    
    return workflow


def visualize_workflow(workflow, output_path: str = "workflow_graph.png"):
    """
    Generate a visual diagram of the workflow
    
    Args:
        workflow: Compiled workflow
        output_path: Where to save the image
        
    Example:
        >>> workflow = build_workflow()
        >>> visualize_workflow(workflow, "my_workflow.png")
    """
    try:
        from IPython.display import Image
        
        # Generate graph visualization
        graph_image = workflow.get_graph().draw_png()
        
        # Save to file
        with open(output_path, 'wb') as f:
            f.write(graph_image)
        
        print(f"✅ Workflow diagram saved to {output_path}")
        
        return Image(graph_image)
    
    except ImportError:
        print("⚠️  IPython not available, cannot generate visualization")
        return None
    except Exception as e:
        print(f"❌ Error generating visualization: {e}")
        return None


def get_workflow_info(workflow) -> dict:
    """
    Get information about the workflow structure
    
    Args:
        workflow: Compiled workflow
        
    Returns:
        Dict with workflow info
    """
    graph = workflow.get_graph()
    
    info = {
        'nodes': list(graph.nodes.keys()),
        'edges': [],
        'entry_point': None,
        'end_nodes': []
    }
    
    # Get edges
    for node, edges in graph.nodes.items():
        for edge in edges:
            info['edges'].append(f"{node} → {edge}")
    
    # TODO: Get entry point and end nodes from graph
    
    return info


# ==================== EXAMPLE WORKFLOWS ====================

def build_simple_safety_workflow():
    """
    Build a minimal workflow with just safety checking
    
    Returns:
        Compiled workflow
    """
    return build_workflow(
        enable_safety=True,
        enable_deficiency=False,
        enable_recommendations=False
    )


def build_comprehensive_workflow():
    """
    Build a full workflow with all agents enabled
    
    Returns:
        Compiled workflow
    """
    return build_workflow(
        enable_safety=True,
        enable_deficiency=True,
        enable_recommendations=True,
        max_iterations=10
    )


# ==================== EXECUTION HELPERS ====================

def run_workflow(
    workflow,
    user_question: str,
    patient_profile: dict,
    verbose: bool = True
) -> dict:
    """
    Run the workflow with a question and profile
    
    Args:
        workflow: Compiled workflow
        user_question: User's question
        patient_profile: Patient health profile
        verbose: Whether to print progress
        
    Returns:
        Final state dict
        
    Example:
        >>> workflow = build_workflow()
        >>> result = run_workflow(
        ...     workflow,
        ...     "Is Fish Oil safe?",
        ...     {"medications": [...]}
        ... )
        >>> print(result['final_answer'])
    """
    from workflow.state import create_initial_state
    
    # Create initial state
    initial_state = create_initial_state(user_question, patient_profile)
    
    if verbose:
        print("🚀 Starting workflow execution...")
        print(f"   Question: {user_question}")
        print()
    
    # Run workflow
    final_state = workflow.invoke(initial_state)
    
    if verbose:
        print("\n✅ Workflow complete!")
        print(f"   Iterations: {final_state.get('iterations', 0)}")
        print(f"   Confidence: {final_state.get('confidence_level', 0):.2f}")
        print()
    
    return final_state


def stream_workflow(
    workflow,
    user_question: str,
    patient_profile: dict
):
    """
    Stream workflow execution (see intermediate steps)
    
    Args:
        workflow: Compiled workflow
        user_question: User's question
        patient_profile: Patient health profile
        
    Yields:
        State updates as they happen
        
    Example:
        >>> workflow = build_workflow()
        >>> for state in stream_workflow(workflow, question, profile):
        ...     print(f"Node: {state['node']}")
        ...     print(f"Decision: {state['supervisor_decision']}")
    """
    from workflow.state import create_initial_state
    
    initial_state = create_initial_state(user_question, patient_profile)
    
    # Stream execution
    for chunk in workflow.stream(initial_state):
        yield chunk


# ==================== TESTING ====================

if __name__ == "__main__":
    print("="*60)
    print("Building Workflow")
    print("="*60 + "\n")
    
    # Build workflow
    workflow = build_workflow()
    
    print("\n" + "="*60)
    print("Workflow Info")
    print("="*60 + "\n")
    
    # Get info
    info = get_workflow_info(workflow)
    print(f"Nodes: {info['nodes']}")
    print(f"Edges: {len(info['edges'])}")
    for edge in info['edges']:
        print(f"  {edge}")
    
    print("\n" + "="*60)
    print("Testing Execution")
    print("="*60 + "\n")
    
    # Test with simple question
    test_profile = {
        'medications': [
            {'drug_id': 'DB00682', 'drug_name': 'Warfarin'}
        ],
        'supplements': [],
        'conditions': ['Atrial Fibrillation'],
        'dietary_restrictions': []
    }
    
    try:
        result = run_workflow(
            workflow,
            "Is Fish Oil safe with my medications?",
            test_profile,
            verbose=True
        )
        
        if result.get('final_answer'):
            print("Final Answer:")
            print(result['final_answer'])
        
    except Exception as e:
        print(f"❌ Error during execution: {e}")
        print("   (This is expected if agents aren't fully implemented yet)")
    
    print("\n" + "="*60)
    print("Visualization")
    print("="*60 + "\n")
    
    # Try to visualize
    visualize_workflow(workflow, "/mnt/user-data/outputs/workflow_graph.png")
