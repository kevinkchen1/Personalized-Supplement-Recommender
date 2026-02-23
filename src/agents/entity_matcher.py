"""
Entity Matcher - Graph-Based Entity Extraction and Normalization

Uses graph queries to extract and normalize entities from user input.
Replaces LLM-based entity extraction.
"""

from typing import Dict, Any


def entity_matcher(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract and normalize entities using graph queries.
    
    This replaces the supervisor's entity extraction logic.
    Uses graph_entity_matcher instead of LLM calls.
    
    Args:
        state: Current conversation state
    
    Returns:
        Updated state with extracted and normalized entities
    """
    print("\n" + "=" * 60)
    print("🔍 ENTITY MATCHER: Extracting entities from graph...")
    print("=" * 60)
    
    graph_interface = state.get('graph_interface')
    if not graph_interface:
        print("   ⚠️  No graph_interface available")
        state['entities_extracted'] = False
        return state
    
    from tools.graph_entity_matcher import extract_entities_from_question
    
    # Extract entities using graph matching
    question = state.get('user_question', '')
    patient_profile = state.get('patient_profile', {})
    
    print(f"   Question: {question[:100]}...")
    
    extracted = extract_entities_from_question(question, graph_interface, patient_profile)
    
    # Normalize medications
    normalized_medications = []
    for med_match in extracted.get('medications', []):
        if med_match.get('entity_id'):
            normalized_medications.append({
                'user_input': med_match.get('original_input', ''),
                'matched_drug': med_match.get('entity_name', ''),
                'drug_id': med_match.get('entity_id', ''),
                'confidence': med_match.get('confidence', 'MEDIUM'),
                'match_type': med_match.get('match_type', 'partial')
            })
    
    # Normalize supplements
    normalized_supplements = []
    for supp_match in extracted.get('supplements', []):
        if supp_match.get('entity_id'):
            normalized_supplements.append({
                'user_input': supp_match.get('original_input', ''),
                'matched_supplement': supp_match.get('entity_name', ''),
                'supplement_id': supp_match.get('entity_id', ''),
                'confidence': supp_match.get('confidence', 'MEDIUM'),
                'match_type': supp_match.get('match_type', 'partial')
            })
    
    # Also check patient profile for additional entities
    if patient_profile:
        from tools.entity_normalizer import (
            normalize_medication_to_database,
            normalize_supplement_to_database
        )
        
        # Normalize medications from profile
        profile_meds = patient_profile.get('medications', [])
        for med in profile_meds:
            if isinstance(med, str):
                result = normalize_medication_to_database(med, graph_interface)
                if result.get('drug_id'):
                    # Avoid duplicates
                    if not any(m.get('drug_id') == result['drug_id'] 
                              for m in normalized_medications):
                        normalized_medications.append(result)
        
        # Normalize supplements from profile
        profile_supps = patient_profile.get('supplements', [])
        for supp in profile_supps:
            if isinstance(supp, str):
                result = normalize_supplement_to_database(supp, graph_interface)
                if result.get('supplement_id'):
                    # Avoid duplicates
                    if not any(s.get('supplement_id') == result['supplement_id']
                              for s in normalized_supplements):
                        normalized_supplements.append(result)
    
    # Update state
    state['entities_extracted'] = True
    state['extracted_entities'] = extracted
    state['normalized_medications'] = normalized_medications
    state['normalized_supplements'] = normalized_supplements
    state['entities_normalized'] = True
    
    print(f"   Found {len(normalized_medications)} medication(s)")
    print(f"   Found {len(normalized_supplements)} supplement(s)")
    print("=" * 60 + "\n")
    
    return state

