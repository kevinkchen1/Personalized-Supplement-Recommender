# """
# State Definition - Conversation State

# Defines the shared state that flows between all agents in the workflow.
# All agents read from and write to this state.

# Current phase: Entity Extraction + Normalization only.
# Supervisor, specialist, and synthesis fields are defined but
# will be populated in later phases.
# """

# from typing import TypedDict, List, Dict, Any, Optional, Annotated
# from langgraph.graph import add_messages


# class InputState(TypedDict):
#     """
#     The only fields the user provides at the start.
#     LangGraph Studio shows only these two fields as inputs.
#     """
#     user_question: str
#     patient_profile: Dict[str, Any]


# # Default patient profile template shown in LangGraph Studio input
# DEFAULT_PATIENT_PROFILE = {
#     "medications": "",
#     "supplements": "",
#     "conditions": [],
#     "dietary_restrictions": []
# }


# class ConversationState(TypedDict):
#     """
#     Shared state passed between all nodes in the workflow.
#     LangGraph automatically manages state updates and passing.
#     """

#     # ==================== USER INPUTS ====================

#     user_question: str
#     """The user's original question"""

#     patient_profile: Dict[str, Any]
#     """
#     Raw patient profile from sidebar form:
#     {
#         'medications': 'Warfarin, Metformin',       # comma-separated string
#         'supplements': 'Fish Oil, Vitamin D',        # comma-separated string
#         'conditions': ['Diabetes'],                  # list
#         'dietary_restrictions': ['Vegan']            # list
#     }
#     """

#     # ==================== ENTITY EXTRACTION ====================

#     entities_extracted: bool
#     """Flag: entities have been extracted from question + profile"""

#     extracted_entities: Optional[Dict[str, List[str]]]
#     """
#     Raw entities pulled from user question (natural language):
#     {
#         'medications': ['Warfarin'],
#         'supplements': ['Fish Oil'],
#         'conditions': ['heart health'],
#         'dietary_restrictions': ['vegan']
#     }
#     """

#     # ==================== ENTITY NORMALIZATION ====================

#     entities_normalized: bool
#     """Flag: extracted entities have been mapped to database IDs"""

#     normalized_medications: Optional[List[Dict[str, Any]]]
#     """
#     Medications mapped to database entries:
#     [
#         {
#             'user_input': 'Warfarin',
#             'matched_drug': 'Warfarin',
#             'drug_id': 'DB00682',
#             'confidence': 'HIGH',
#             'match_type': 'exact_drug_name'
#         }
#     ]
#     """

#     normalized_supplements: Optional[List[Dict[str, Any]]]
#     """
#     Supplements mapped to database entries:
#     [
#         {
#             'user_input': 'Fish Oil',
#             'matched_supplement': 'Fish oil',
#             'supplement_id': 'S07',
#             'confidence': 'HIGH',
#             'match_type': 'exact_supplement_name'
#         }
#     ]
#     """

#     normalized_dietary_restrictions: Optional[List[str]]
#     """
#     Dietary restrictions — simple strings, no DB mapping needed.
#     Example: ['Vegan', 'Gluten-free']
#     """

#     # Clean deduplicated lists for downstream agents to consume
#     medications_list: List[str]
#     """
#     Final clean medication names after deduplication.
#     Example: ['Warfarin', 'Metformin']
#     """

#     supplements_list: List[str]
#     """
#     Final clean supplement names after deduplication.
#     Example: ['Fish Oil', 'Vitamin D']
#     """

#     dietary_restrictions_list: List[str]
#     """
#     Final clean dietary restriction names.
#     Example: ['Vegan', 'Gluten-free']
#     """

#     conditions_list: List[str]
#     """
#     Final clean condition names extracted from question + profile.
#     Example: ['heart health', 'diabetes']
#     """

#     # ==================== SUPERVISOR CONTROL ====================
#     # Populated in supervisor phase

#     supervisor_decision: str
#     """
#     Supervisor's routing decision:
#     'check_safety' | 'check_deficiency' | 'get_recommendations' | 'synthesize'
#     """

#     iterations: int
#     """Number of supervisor calls — prevents infinite loops"""

#     confidence_level: float
#     """Overall confidence score (0.0 to 1.0)"""

#     # ==================== SPECIALIST RESULTS ====================
#     # Populated by specialist tools

#     safety_checked: bool
#     safety_results: Optional[Dict[str, Any]]

#     deficiency_checked: bool
#     deficiency_results: Optional[Dict[str, Any]]

#     recommendations_checked: bool
#     recommendation_results: Optional[Dict[str, Any]]

#     # ==================== EVIDENCE & LOGGING ====================

#     evidence_chain: List[str]
#     """
#     Human-readable reasoning steps for transparency.
#     Each agent appends its findings.
#     Example: ['Extracted: Fish Oil, Warfarin', 'Safety: 2 interactions found']
#     """

#     query_history: List[Dict]
#     """
#     All database queries executed, for debugging.
#     Example: [{'query_type': 'normalize_medication', 'success': True, 'result_count': 1}]
#     """

#     # ==================== FINAL OUTPUT ====================

#     final_answer: Optional[str]
#     """Synthesized personalized answer returned to user"""

#     error_message: Optional[str]
#     """Error message if something goes wrong"""

#     # ==================== MESSAGES ====================

#     messages: Annotated[List[Dict], add_messages]
#     """
#     Chat message history. LangGraph appends automatically via add_messages.
#     Format: [{'role': 'user', 'content': '...'}, ...]
#     """


# # ==================== INITIAL STATE ====================

# def create_initial_state(
#     user_question: str,
#     patient_profile: Dict[str, Any],
# ) -> ConversationState:
#     """
#     Create a fresh state for a new conversation.

#     Args:
#         user_question: The user's question
#         patient_profile: Raw profile from sidebar

#     Returns:
#         ConversationState with all defaults set
#     """
#     return ConversationState(
#         # User inputs
#         user_question=user_question,
#         patient_profile=patient_profile,

#         # Entity extraction
#         entities_extracted=False,
#         extracted_entities=None,

#         # Entity normalization
#         entities_normalized=False,
#         normalized_medications=None,
#         normalized_supplements=None,
#         normalized_dietary_restrictions=None,

#         # Clean lists for agents
#         medications_list=[],
#         supplements_list=[],
#         dietary_restrictions_list=[],
#         conditions_list=[],

#         # Supervisor control
#         supervisor_decision="",
#         iterations=0,
#         confidence_level=0.0,

#         # Specialist results
#         safety_checked=False,
#         safety_results=None,
#         deficiency_checked=False,
#         deficiency_results=None,
#         recommendations_checked=False,
#         recommendation_results=None,

#         # Evidence & logging
#         evidence_chain=[],
#         query_history=[],

#         # Final output
#         final_answer=None,
#         error_message=None,

#         # Messages
#         messages=[{"role": "user", "content": user_question}],
#     )


# # ==================== HELPER FUNCTIONS ====================

# def get_state_summary(state: ConversationState) -> str:
#     """Human-readable summary of current state — useful for debugging."""
#     return f"""
# State Summary
# -------------
# Question   : {state['user_question']}
# Iterations : {state.get('iterations', 0)}
# Confidence : {state.get('confidence_level', 0):.2f}

# Pipeline Progress:
#   Entities Extracted  : {'✓' if state.get('entities_extracted') else '✗'}
#   Entities Normalized : {'✓' if state.get('entities_normalized') else '✗'}
#   Safety Checked      : {'✓' if state.get('safety_checked') else '✗'}
#   Deficiency Checked  : {'✓' if state.get('deficiency_checked') else '✗'}
#   Recommendations     : {'✓' if state.get('recommendations_checked') else '✗'}

# Clean Lists:
#   Medications          : {state.get('medications_list', [])}
#   Supplements          : {state.get('supplements_list', [])}
#   Dietary Restrictions : {state.get('dietary_restrictions_list', [])}
#   Conditions           : {state.get('conditions_list', [])}

# Supervisor Decision : {state.get('supervisor_decision', 'None')}
# Evidence Steps      : {len(state.get('evidence_chain', []))}
# Queries Made        : {len(state.get('query_history', []))}
# Final Answer        : {'Generated' if state.get('final_answer') else 'Not yet'}
# """

"""
State Definition - Conversation State

Defines the shared state that flows between all agents in the workflow.
All agents read from and write to this state.

Current phase: Entity Extraction + Normalization only.
Supervisor, specialist, and synthesis fields are defined but
will be populated in later phases.
"""

from typing import TypedDict, List, Dict, Any, Optional, Annotated
from langgraph.graph import add_messages


class InputState(TypedDict):
    """
    The only fields the user provides at the start.
    LangGraph Studio shows only these two fields as inputs.
    """
    user_question: str
    patient_profile: Dict[str, Any]


# Default patient profile template shown in LangGraph Studio input
DEFAULT_PATIENT_PROFILE = {
    "medications": "",
    "supplements": "",
    "conditions": [],
    "dietary_restrictions": []
}


class ConversationState(TypedDict):
    """
    Shared state passed between all nodes in the workflow.
    LangGraph automatically manages state updates and passing.
    """

    # ==================== USER INPUTS ====================

    user_question: str
    """The user's original question"""

    patient_profile: Dict[str, Any]
    """
    Raw patient profile from sidebar form:
    {
        'medications': 'Warfarin, Metformin',       # comma-separated string
        'supplements': 'Fish Oil, Vitamin D',        # comma-separated string
        'conditions': ['Diabetes'],                  # list
        'dietary_restrictions': ['Vegan']            # list
    }
    """

    # ==================== ENTITY EXTRACTION ====================

    entities_extracted: bool
    """Flag: entities have been extracted from question + profile"""

    extracted_entities: Optional[Dict[str, List[str]]]
    """
    Raw entities pulled from user question (natural language):
    {
        'medications': ['Warfarin'],
        'supplements': ['Fish Oil'],
        'conditions': ['heart health'],
        'dietary_restrictions': ['vegan']
    }
    """

    # ==================== ENTITY NORMALIZATION ====================

    entities_normalized: bool
    """Flag: extracted entities have been mapped to database IDs"""

    normalized_medications: Optional[List[Dict[str, Any]]]
    """
    Medications mapped to database entries:
    [
        {
            'user_input': 'Warfarin',
            'matched_drug': 'Warfarin',
            'drug_id': 'DB00682',
            'confidence': 'HIGH',
            'match_type': 'exact_drug_name'
        }
    ]
    """

    normalized_supplements: Optional[List[Dict[str, Any]]]
    """
    Supplements mapped to database entries:
    [
        {
            'user_input': 'Fish Oil',
            'matched_supplement': 'Fish oil',
            'supplement_id': 'S07',
            'confidence': 'HIGH',
            'match_type': 'exact_supplement_name'
        }
    ]
    """

    normalized_dietary_restrictions: Optional[List[Dict[str, Any]]]
    """
    Dietary restrictions mapped to database entries where possible:
    [{'user_input': 'Vegan', 'matched_name': 'Vegan', 'db_id': 'DR01', 'confidence': 'HIGH'}]
    Falls back to PASS_THROUGH with db_id: None if not found in DB.
    """

    # Clean deduplicated lists for downstream agents to consume
    medications_list: List[str]
    """
    Final clean medication names after deduplication.
    Example: ['Warfarin', 'Metformin']
    """

    supplements_list: List[str]
    """
    Final clean supplement names after deduplication.
    Example: ['Fish Oil', 'Vitamin D']
    """

    dietary_restrictions_list: List[str]
    """
    Final clean dietary restriction names.
    Example: ['Vegan', 'Gluten-free']
    """

    conditions_list: List[str]
    """
    Final clean condition names extracted from question + profile.
    Example: ['heart health', 'diabetes']
    """

    # ==================== SUPERVISOR CONTROL ====================
    # Populated in supervisor phase

    supervisor_decision: str
    """
    Supervisor's routing decision:
    'check_safety' | 'check_deficiency' | 'get_recommendations' | 'synthesize'
    """

    iterations: int
    """Number of supervisor calls — prevents infinite loops"""

    confidence_level: float
    """Overall confidence score (0.0 to 1.0)"""

    # ==================== SPECIALIST RESULTS ====================
    # Populated by specialist tools

    safety_checked: bool
    safety_results: Optional[Dict[str, Any]]

    deficiency_checked: bool
    deficiency_results: Optional[Dict[str, Any]]

    recommendations_checked: bool
    recommendation_results: Optional[Dict[str, Any]]

    # ==================== EVIDENCE & LOGGING ====================

    evidence_chain: List[str]
    """
    Human-readable reasoning steps for transparency.
    Each agent appends its findings.
    Example: ['Extracted: Fish Oil, Warfarin', 'Safety: 2 interactions found']
    """

    query_history: List[Dict]
    """
    All database queries executed, for debugging.
    Example: [{'query_type': 'normalize_medication', 'success': True, 'result_count': 1}]
    """

    # ==================== FINAL OUTPUT ====================

    final_answer: Optional[str]
    """Synthesized personalized answer returned to user"""

    error_message: Optional[str]
    """Error message if something goes wrong"""

    # ==================== MESSAGES ====================

    messages: Annotated[List[Dict], add_messages]
    """
    Chat message history. LangGraph appends automatically via add_messages.
    Format: [{'role': 'user', 'content': '...'}, ...]
    """


# ==================== INITIAL STATE ====================

def create_initial_state(
    user_question: str,
    patient_profile: Dict[str, Any],
) -> ConversationState:
    """
    Create a fresh state for a new conversation.

    Args:
        user_question: The user's question
        patient_profile: Raw profile from sidebar

    Returns:
        ConversationState with all defaults set
    """
    return ConversationState(
        # User inputs
        user_question=user_question,
        patient_profile=patient_profile,

        # Entity extraction
        entities_extracted=False,
        extracted_entities=None,

        # Entity normalization
        entities_normalized=False,
        normalized_medications=None,
        normalized_supplements=None,
        normalized_dietary_restrictions=None,

        # Clean lists for agents
        medications_list=[],
        supplements_list=[],
        dietary_restrictions_list=[],
        conditions_list=[],

        # Supervisor control
        supervisor_decision="",
        iterations=0,
        confidence_level=0.0,

        # Specialist results
        safety_checked=False,
        safety_results=None,
        deficiency_checked=False,
        deficiency_results=None,
        recommendations_checked=False,
        recommendation_results=None,

        # Evidence & logging
        evidence_chain=[],
        query_history=[],

        # Final output
        final_answer=None,
        error_message=None,

        # Messages
        messages=[{"role": "user", "content": user_question}],
    )


# ==================== HELPER FUNCTIONS ====================

def get_state_summary(state: ConversationState) -> str:
    """Human-readable summary of current state — useful for debugging."""
    return f"""
State Summary
-------------
Question   : {state['user_question']}
Iterations : {state.get('iterations', 0)}
Confidence : {state.get('confidence_level', 0):.2f}

Pipeline Progress:
  Entities Extracted  : {'✓' if state.get('entities_extracted') else '✗'}
  Entities Normalized : {'✓' if state.get('entities_normalized') else '✗'}
  Safety Checked      : {'✓' if state.get('safety_checked') else '✗'}
  Deficiency Checked  : {'✓' if state.get('deficiency_checked') else '✗'}
  Recommendations     : {'✓' if state.get('recommendations_checked') else '✗'}

Clean Lists:
  Medications          : {state.get('medications_list', [])}
  Supplements          : {state.get('supplements_list', [])}
  Dietary Restrictions : {state.get('dietary_restrictions_list', [])}
  Conditions           : {state.get('conditions_list', [])}

Supervisor Decision : {state.get('supervisor_decision', 'None')}
Evidence Steps      : {len(state.get('evidence_chain', []))}
Queries Made        : {len(state.get('query_history', []))}
Final Answer        : {'Generated' if state.get('final_answer') else 'Not yet'}
"""