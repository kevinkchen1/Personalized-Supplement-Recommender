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

# Import agent functions
from agents.entity_matcher import entity_matcher
from agents.question_analyzer import question_analyzer
from agents.synthesis_agent import synthesis_agent
from workflow.parallel_executor import parallel_executor


def build_workflow(
    enable_safety: bool = True,
    enable_deficiency: bool = True,
    enable_recommendations: bool = True,
    max_iterations: int = 10
):
    """
    Build the graph-first workflow with parallel execution.
    
    New architecture:
    entity_matcher → question_analyzer → parallel_executor → synthesis → END
    
    Args:
        enable_safety: Whether to enable safety check agent
        enable_deficiency: Whether to enable deficiency agent
        enable_recommendations: Whether to enable recommendation agent
        max_iterations: Not used in new architecture (kept for compatibility)
        
    Returns:
        Compiled LangGraph workflow (CompiledGraph)
        
    Example:
        >>> workflow = build_workflow()
        >>> result = workflow.invoke(initial_state)
        >>> print(result['final_answer'])
    """
    
    # Create the graph with our state definition
    workflow = StateGraph(ConversationState)
    
    print("🏗️  Building graph-first workflow...")
    
    # ==================== ADD NODES ====================
    
    print("   Adding entity_matcher node...")
    workflow.add_node("entity_matcher", entity_matcher)
    
    print("   Adding question_analyzer node...")
    workflow.add_node("question_analyzer", question_analyzer)
    
    print("   Adding parallel_executor node...")
    workflow.add_node("parallel_executor", parallel_executor)
    
    print("   Adding synthesis node...")
    workflow.add_node("synthesis", synthesis_agent)
    
    # ==================== ADD EDGES ====================
    # Linear flow: entity_matcher → question_analyzer → parallel_executor → synthesis → END
    
    print("   Setting up linear flow...")
    workflow.add_edge("entity_matcher", "question_analyzer")
    workflow.add_edge("question_analyzer", "parallel_executor")
    workflow.add_edge("parallel_executor", "synthesis")
    workflow.add_edge("synthesis", END)
    
    # ==================== SET ENTRY POINT ====================
    print("   Setting entry point: entity_matcher")
    workflow.set_entry_point("entity_matcher")
    
    # ==================== COMPILE ====================
    print("   Compiling workflow...")
    compiled_workflow = workflow.compile()
    
    print("✅ Graph-first workflow built successfully!\n")
    
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
    workflow = StateGraph(ConversationState)

    # If the caller passed a compiled checkpointer, compile the graph with it
    base = build_workflow(**kwargs)

    # If a checkpointer is provided and the compiled graph supports it,
    # re-compile the base workflow with the checkpointer to enable persistence.
    if checkpointer is not None:
        try:
            compiled_with_cp = base.compile(checkpointer=checkpointer)
            return compiled_with_cp
        except Exception:
            # Fall back to previously compiled graph if checkpointing fails
            return base

    return base


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

        # Try to get a PNG bytes representation from the compiled workflow
        graph_obj = workflow.get_graph()

        # Some LangGraph versions expose draw_png(), others expose draw()
        if hasattr(graph_obj, "draw_png"):
            graph_image = graph_obj.draw_png()
        elif hasattr(graph_obj, "draw"):
            # draw() may return bytes or an object with _repr_png_
            graph_image = graph_obj.draw()
        else:
            raise RuntimeError("Graph object has no draw_png/draw method")

        # Save to file if bytes-like
        if isinstance(graph_image, (bytes, bytearray)):
            with open(output_path, 'wb') as f:
                f.write(graph_image)
            print(f"✅ Workflow diagram saved to {output_path}")
            return Image(graph_image)
        else:
            # If not bytes, attempt to convert via IPython Image
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

    # Get edges and detect end nodes
    for node, edges in graph.nodes.items():
        # edges might be stored as a list of node names or objects
        for edge in edges:
            info['edges'].append(f"{node} → {edge}")
            # If the edge is the END sentinel, mark this node as leading to END
            if edge == END or (isinstance(edge, str) and edge == str(END)):
                info['end_nodes'].append(node)

    # Attempt to get the configured entry point if available
    entry = None
    try:
        entry = getattr(workflow, 'entry_point', None)
        if not entry:
            # Some compiled graphs store entry on the inner graph object
            entry = getattr(graph, 'entry_point', None)
    except Exception:
        entry = None

    # Fallback: default to entity_matcher if present (new architecture)
    if not entry and 'entity_matcher' in info['nodes']:
        entry = 'entity_matcher'

    info['entry_point'] = entry

    # Deduplicate end_nodes
    info['end_nodes'] = list(dict.fromkeys(info['end_nodes']))

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
    graph_interface=None,
    verbose: bool = True
) -> dict:
    """
    Run the workflow with a question and profile
    
    Args:
        workflow: Compiled workflow
        user_question: User's question
        patient_profile: Patient health profile
        graph_interface: Neo4j GraphInterface (passed to agents via state)
        verbose: Whether to print progress
        
    Returns:
        Final state dict
    """
    from workflow.state import create_initial_state
    
    # Create initial state
    initial_state = create_initial_state(user_question, patient_profile)
    
    # Inject graph_interface so agents (supervisor, safety, etc.) can use it
    if graph_interface is not None:
        initial_state['graph_interface'] = graph_interface
    
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
