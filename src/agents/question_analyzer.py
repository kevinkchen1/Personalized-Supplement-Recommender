"""
Question Analyzer - Rule-Based Analysis

Replaces LLM-based supervisor question analysis with pure rule-based logic.
Determines what needs to be checked based on what entities exist in the graph.

No LLM calls - purely rule-based decision making.
"""

from typing import Dict, Any, List


def analyze_question_requirements(state: Dict[str, Any]) -> Dict[str, bool]:
    """
    Analyze the question to determine what needs to be checked.
    
    Rule-based logic:
    - If medications exist (normalized or in profile) → needs_safety_check = True
    - If dietary restrictions exist → needs_deficiency_check = True
    - If conditions/symptoms mentioned → needs_recommendations = True
    
    Can detect multiple needs simultaneously (e.g., statin question needs all 3).
    
    Args:
        state: Current conversation state
    
    Returns:
        {
            'needs_safety_check': bool,
            'needs_deficiency_check': bool,
            'needs_recommendations': bool,
            'reasoning': str
        }
    """
    needs = {
        'needs_safety_check': False,
        'needs_deficiency_check': False,
        'needs_recommendations': False,
        'reasoning': ''
    }
    
    reasoning_parts = []
    
    # Check for medications (safety check needed)
    has_medications = _has_medications(state)
    if has_medications:
        needs['needs_safety_check'] = True
        reasoning_parts.append("medications detected")
    
    # Check for dietary restrictions (deficiency check needed)
    has_dietary_restrictions = _has_dietary_restrictions(state)
    if has_dietary_restrictions:
        needs['needs_deficiency_check'] = True
        reasoning_parts.append("dietary restrictions detected")
    
    # Check for conditions/symptoms (recommendations needed)
    has_conditions = _has_conditions_or_symptoms(state)
    if has_conditions:
        needs['needs_recommendations'] = True
        reasoning_parts.append("conditions/symptoms detected")
    
    # Also check question text for keywords that indicate needs
    question_lower = state.get('user_question', '').lower()
    
    # Safety check keywords
    safety_keywords = [
        'safe', 'interaction', 'dangerous', 'risk', 'harmful',
        'compatible', 'conflict', 'side effect'
    ]
    if any(keyword in question_lower for keyword in safety_keywords):
        needs['needs_safety_check'] = True
        if 'safety' not in reasoning_parts:
            reasoning_parts.append("safety keywords in question")
    
    # Deficiency check keywords
    deficiency_keywords = [
        'deficiency', 'deficient', 'nutrient', 'vitamin', 'mineral',
        'diet', 'dietary', 'nutrition', 'lack', 'missing'
    ]
    if any(keyword in question_lower for keyword in deficiency_keywords):
        needs['needs_deficiency_check'] = True
        if 'deficiency' not in reasoning_parts:
            reasoning_parts.append("deficiency keywords in question")
    
    # Recommendation keywords
    recommendation_keywords = [
        'recommend', 'suggest', 'should i take', 'what supplement',
        'for', 'help with', 'treat', 'relief', 'benefit'
    ]
    if any(keyword in question_lower for keyword in recommendation_keywords):
        needs['needs_recommendations'] = True
        if 'recommendations' not in reasoning_parts:
            reasoning_parts.append("recommendation keywords in question")
    
    # Build reasoning string
    if reasoning_parts:
        needs['reasoning'] = "Analysis: " + ", ".join(reasoning_parts)
    else:
        needs['reasoning'] = "Analysis: No specific requirements detected"
    
    return needs


def _has_medications(state: Dict[str, Any]) -> bool:
    """Check if medications exist in state."""
    # Check normalized medications
    normalized_meds = state.get('normalized_medications', [])
    if normalized_meds:
        # Check if any have valid drug_id
        for med in normalized_meds:
            if isinstance(med, dict) and med.get('drug_id'):
                return True
    
    # Check patient profile medications
    profile = state.get('patient_profile', {})
    profile_meds = profile.get('medications', [])
    if profile_meds:
        for med in profile_meds:
            if isinstance(med, dict):
                if med.get('drug_id') or med.get('drug_name'):
                    return True
            elif med:  # Non-empty string
                return True
    
    # Check extracted entities
    extracted = state.get('extracted_entities', {})
    if extracted and extracted.get('medications'):
        return True
    
    return False


def _has_dietary_restrictions(state: Dict[str, Any]) -> bool:
    """Check if dietary restrictions exist in state."""
    # Check patient profile
    profile = state.get('patient_profile', {})
    restrictions = profile.get('dietary_restrictions', []) or profile.get('diet', [])
    if restrictions:
        return True
    
    # Check extracted entities
    extracted = state.get('extracted_entities', {})
    if extracted and extracted.get('dietary_restrictions'):
        return True
    
    # Check question for restriction keywords
    question = state.get('user_question', '').lower()
    restriction_keywords = [
        'vegan', 'vegetarian', 'keto', 'paleo', 'gluten-free',
        'dairy-free', 'diet', 'dietary'
    ]
    if any(keyword in question for keyword in restriction_keywords):
        return True
    
    return False


def _has_conditions_or_symptoms(state: Dict[str, Any]) -> bool:
    """Check if conditions or symptoms are mentioned."""
    # Check patient profile
    profile = state.get('patient_profile', {})
    conditions = profile.get('conditions', [])
    if conditions:
        return True
    
    # Check extracted entities
    extracted = state.get('extracted_entities', {})
    if extracted and extracted.get('conditions'):
        return True
    
    # Check question for condition/symptom keywords
    question = state.get('user_question', '').lower()
    condition_keywords = [
        'pain', 'ache', 'inflammation', 'joint', 'heart', 'cardiac',
        'diabetes', 'hypertension', 'anxiety', 'depression', 'sleep',
        'energy', 'fatigue', 'immune', 'bone', 'muscle'
    ]
    if any(keyword in question for keyword in condition_keywords):
        return True
    
    return False


def question_analyzer(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main entry point for question analyzer (LangGraph node function).
    
    Analyzes the question and determines what checks are needed.
    Updates state with analysis results.
    
    Args:
        state: Current conversation state
    
    Returns:
        Updated state with analysis results
    """
    print("📊 QUESTION ANALYZER: Analyzing requirements...")
    
    # Analyze requirements
    needs = analyze_question_requirements(state)
    
    # Update state
    state['question_analysis'] = needs
    state['needs_safety_check'] = needs['needs_safety_check']
    state['needs_deficiency_check'] = needs['needs_deficiency_check']
    state['needs_recommendations'] = needs['needs_recommendations']
    
    print(f"   {needs['reasoning']}")
    print(f"   Safety: {needs['needs_safety_check']}, "
          f"Deficiency: {needs['needs_deficiency_check']}, "
          f"Recommendations: {needs['needs_recommendations']}")
    
    return state

