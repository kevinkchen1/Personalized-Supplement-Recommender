"""
State Definition - Conversation State

Defines the shared state that flows between all agents in the workflow.
This is the "memory" that all agents can read from and write to.

The state contains:
- User inputs (question, profile)
- Progress tracking (what's been done)
- Results from each agent
- Control flow (supervisor decisions)
- Metadata (confidence, iterations)
"""

from typing import TypedDict, List, Dict, Any, Optional, Annotated
from langgraph.graph import add_messages


class ConversationState(TypedDict):
    """
    The complete state of a conversation.
    
    This state is passed between all agents and updated as the workflow progresses.
    LangGraph automatically manages state updates and passing.
    """
    
    # ==================== USER INPUTS ====================
    
    user_question: str
    """The user's original question"""
    
    patient_profile: Dict[str, Any]
    """
    Patient's health profile (already normalized from sidebar):
    {
        'medications': [
            {'drug_id': 'DB00682', 'drug_name': 'Warfarin', ...}
        ],
        'supplements': [
            {'supplement_id': 'S07', 'supplement_name': 'Fish oil', ...}
        ],
        'conditions': ['Atrial Fibrillation'],
        'dietary_restrictions': ['Vegan']
    }
    """
    
    # ==================== ENTITY EXTRACTION ====================
    
    entities_extracted: bool
    """Flag: Have entities been extracted from the question?"""
    
    extracted_entities: Optional[Dict[str, List[str]]]
    """
    Entities extracted from user question:
    {
        'medications': ['Aspirin'],
        'supplements': ['Fish Oil'],
        'conditions': [],
        'dietary_restrictions': []
    }
    """
    
    entities_normalized: bool
    """Flag: Have extracted entities been normalized to database IDs?"""
    
    normalized_entities: Optional[Dict[str, List[Dict]]]
    """
    Normalized entities with database IDs:
    {
        'medications': [
            {'user_input': 'Aspirin', 'drug_id': 'DB00945', ...}
        ],
        'supplements': [
            {'user_input': 'Fish Oil', 'supplement_id': 'S07', ...}
        ],
        'conditions': [...],
        'dietary_restrictions': [...]
    }
    """
    
    # ==================== AGENT CHECKS ====================
    
    safety_checked: bool
    """Flag: Has safety check been performed?"""
    
    safety_results: Optional[Dict[str, Any]]
    """
    Results from safety_check_agent:
    {
        'safe': True/False,
        'interactions': [...],
        'confidence': 0.85,
        'supplement_checked': 'Fish oil',
        'verdict': 'SAFE' or 'CAUTION ADVISED'
    }
    """
    
    deficiency_checked: bool
    """Flag: Has deficiency check been performed?"""
    
    deficiency_results: Optional[Dict[str, Any]]
    """
    Results from deficiency_agent:
    {
        'at_risk': ['Vitamin B-12', 'Iron'],
        'risk_levels': {'Vitamin B-12': 'HIGH', 'Iron': 'MEDIUM'},
        'deficiency_details': {...},
        'sources': ['Diet: Vegan', 'Medication: Metformin']
    }
    """
    
    recommendations_checked: bool
    """Flag: Have recommendations been generated?"""
    
    recommendation_results: Optional[Dict[str, Any]]
    """
    Results from recommendation_agent:
    {
        'condition': 'Joint Pain',
        'recommendations': [
            {'supplement': 'Glucosamine', 'evidence': 'HIGH', ...}
        ],
        'filtered_count': 3  # How many were filtered due to interactions
    }
    """
    
    # ==================== SUPERVISOR CONTROL ====================
    
    supervisor_decision: str
    """
    Supervisor's decision for what to do next:
    - 'check_safety': Call safety agent
    - 'check_deficiency': Call deficiency agent
    - 'check_recommendations': Call recommendation agent
    - 'finish': Go to synthesis
    - 'loop_back': Supervisor needs to reconsider
    """
    
    iterations: int
    """Number of times supervisor has been called (prevent infinite loops)"""
    
    confidence_level: float
    """Overall confidence in the answer (0.0 to 1.0)"""
    
    # ==================== MESSAGES (for chat history) ====================
    
    messages: Annotated[List[Dict], add_messages]
    """
    Chat message history (LangGraph special field).
    Use add_messages to automatically append to this list.
    
    Format:
    [
        {'role': 'user', 'content': 'Is Fish Oil safe?'},
        {'role': 'assistant', 'content': 'Let me check...'},
        ...
    ]
    """
    
    # ==================== EVIDENCE & LOGGING ====================
    
    evidence_chain: List[str]
    """
    Track reasoning steps for transparency:
    [
        'Extracted: Fish Oil, Warfarin',
        'Checked: Direct interactions → None found',
        'Checked: Similar effects → Both increase bleeding risk',
        'Verdict: CAUTION (confidence: 0.75)'
    ]
    """
    
    query_history: List[Dict]
    """
    Track all database queries made:
    [
        {'query_type': 'direct_interaction', 'result_count': 0, ...}
    ]
    """
    
    # ==================== FINAL OUTPUT ====================
    
    final_answer: Optional[str]
    """The synthesized, personalized answer to return to user"""
    
    error_message: Optional[str]
    """Any error message if something goes wrong"""


# ==================== DEFAULT STATE ====================

def create_initial_state(
    user_question: str,
    patient_profile: Dict[str, Any]
) -> ConversationState:
    """
    Create initial state for a new conversation
    
    Args:
        user_question: The user's question
        patient_profile: The patient's health profile
        
    Returns:
        ConversationState with default values
    """
    return ConversationState(
        # Inputs
        user_question=user_question,
        patient_profile=patient_profile,
        
        # Entity extraction
        entities_extracted=False,
        extracted_entities=None,
        entities_normalized=False,
        normalized_entities=None,
        
        # Agent checks
        safety_checked=False,
        safety_results=None,
        deficiency_checked=False,
        deficiency_results=None,
        recommendations_checked=False,
        recommendation_results=None,
        
        # Supervisor control
        supervisor_decision="",
        iterations=0,
        confidence_level=0.0,
        
        # Messages
        messages=[
            {"role": "user", "content": user_question}
        ],
        
        # Evidence & logging
        evidence_chain=[],
        query_history=[],
        
        # Final output
        final_answer=None,
        error_message=None
    )


# ==================== STATE HELPER FUNCTIONS ====================

def add_evidence(state: ConversationState, evidence: str) -> ConversationState:
    """
    Add an evidence step to the chain
    
    Args:
        state: Current state
        evidence: Evidence string to add
        
    Returns:
        Updated state
    """
    if state.get('evidence_chain') is None:
        state['evidence_chain'] = []
    
    state['evidence_chain'].append(evidence)
    return state


def update_confidence(
    state: ConversationState,
    new_confidence: float
) -> ConversationState:
    """
    Update the confidence level
    
    Args:
        state: Current state
        new_confidence: New confidence value (0.0-1.0)
        
    Returns:
        Updated state
    """
    # Take the minimum of current and new confidence
    # (conservative approach - if any check has low confidence, overall is low)
    current = state.get('confidence_level', 1.0)
    state['confidence_level'] = min(current, new_confidence)
    
    return state


def log_query(
    state: ConversationState,
    query_type: str,
    result_count: int,
    success: bool
) -> ConversationState:
    """
    Log a database query
    
    Args:
        state: Current state
        query_type: Type of query
        result_count: Number of results
        success: Whether query succeeded
        
    Returns:
        Updated state
    """
    if state.get('query_history') is None:
        state['query_history'] = []
    
    state['query_history'].append({
        'query_type': query_type,
        'result_count': result_count,
        'success': success
    })
    
    return state


def is_max_iterations_reached(state: ConversationState, max_iter: int = 10) -> bool:
    """
    Check if max iterations reached
    
    Args:
        state: Current state
        max_iter: Maximum allowed iterations
        
    Returns:
        True if max reached
    """
    return state.get('iterations', 0) >= max_iter


def get_state_summary(state: ConversationState) -> str:
    """
    Get a human-readable summary of the current state
    
    Args:
        state: Current state
        
    Returns:
        Summary string
    """
    summary = f"""
State Summary:
--------------
Question: {state['user_question']}
Iterations: {state.get('iterations', 0)}
Confidence: {state.get('confidence_level', 0):.2f}

Progress:
  Entities Extracted: {'✓' if state.get('entities_extracted') else '✗'}
  Entities Normalized: {'✓' if state.get('entities_normalized') else '✗'}
  Safety Checked: {'✓' if state.get('safety_checked') else '✗'}
  Deficiency Checked: {'✓' if state.get('deficiency_checked') else '✗'}
  Recommendations: {'✓' if state.get('recommendations_checked') else '✗'}

Supervisor Decision: {state.get('supervisor_decision', 'None')}
Evidence Steps: {len(state.get('evidence_chain', []))}
Queries Made: {len(state.get('query_history', []))}
"""
    
    if state.get('final_answer'):
        summary += f"\nFinal Answer: Generated ({len(state['final_answer'])} chars)"
    
    return summary


# ==================== TESTING ====================

if __name__ == "__main__":
    # Test state creation
    test_state = create_initial_state(
        user_question="Is Fish Oil safe with my medications?",
        patient_profile={
            'medications': [
                {'drug_id': 'DB00682', 'drug_name': 'Warfarin'}
            ],
            'supplements': [],
            'conditions': ['Atrial Fibrillation'],
            'dietary_restrictions': []
        }
    )
    
    print("Initial State Created:")
    print(get_state_summary(test_state))
    
    # Simulate some updates
    test_state['entities_extracted'] = True
    test_state['safety_checked'] = True
    test_state['confidence_level'] = 0.85
    test_state['iterations'] = 2
    
    test_state = add_evidence(test_state, "Checked direct interactions: None found")
    test_state = add_evidence(test_state, "Checked similar effects: Both affect bleeding")
    
    print("\n\nAfter Updates:")
    print(get_state_summary(test_state))
