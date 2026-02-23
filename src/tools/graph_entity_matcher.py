"""
Graph Entity Matcher - Graph-First Entity Extraction

Replaces LLM-based entity extraction with direct graph queries.
Uses fuzzy Cypher queries to find entities across:
- Drug names
- Brand names (248K available)
- Synonyms (52K available)
- Supplement names

This leverages the rich knowledge graph instead of relying on LLM calls.
"""

from typing import Dict, List, Optional, Any


def match_entities_in_graph(
    user_input: str,
    graph_interface,
    entity_types: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Match user input to entities in the knowledge graph using fuzzy Cypher queries.
    
    Searches across multiple entity types simultaneously:
    - Drugs (by name)
    - Brand names
    - Synonyms
    - Supplements
    
    Args:
        user_input: User's input text (could be medication, supplement, condition, etc.)
        graph_interface: Neo4j GraphInterface instance
        entity_types: Optional list of types to search ['drug', 'supplement', 'all']
                     Default: 'all' (searches everything)
    
    Returns:
        {
            'matched_entities': [
                {
                    'entity_type': 'drug' | 'supplement' | 'brand' | 'synonym',
                    'entity_id': 'DB00682',
                    'entity_name': 'Warfarin',
                    'match_type': 'exact' | 'brand' | 'synonym' | 'partial',
                    'confidence': 'HIGH' | 'MEDIUM' | 'LOW',
                    'original_input': user_input
                }
            ],
            'best_match': {...},  # Top match if found
            'confidence': 'HIGH' | 'MEDIUM' | 'LOW' | 'NOT_FOUND'
        }
    """
    if entity_types is None:
        entity_types = ['all']
    
    matched_entities = []
    user_input_lower = user_input.lower().strip()
    
    # Search for drugs (exact match first)
    if 'all' in entity_types or 'drug' in entity_types:
        drug_matches = _match_drugs(user_input_lower, graph_interface)
        matched_entities.extend(drug_matches)
    
    # Search for supplements
    if 'all' in entity_types or 'supplement' in entity_types:
        supplement_matches = _match_supplements(user_input_lower, graph_interface)
        matched_entities.extend(supplement_matches)
    
    # Search for brand names
    if 'all' in entity_types or 'brand' in entity_types:
        brand_matches = _match_brand_names(user_input_lower, graph_interface)
        matched_entities.extend(brand_matches)
    
    # Search for synonyms
    if 'all' in entity_types or 'synonym' in entity_types:
        synonym_matches = _match_synonyms(user_input_lower, graph_interface)
        matched_entities.extend(synonym_matches)
    
    # Determine best match
    if not matched_entities:
        return {
            'matched_entities': [],
            'best_match': None,
            'confidence': 'NOT_FOUND',
            'original_input': user_input
        }
    
    # Sort by confidence: HIGH > MEDIUM > LOW
    # Within same confidence, prefer exact matches
    confidence_order = {'HIGH': 0, 'MEDIUM': 1, 'LOW': 2}
    match_type_order = {'exact': 0, 'brand': 1, 'synonym': 2, 'partial': 3}
    
    matched_entities.sort(key=lambda x: (
        confidence_order.get(x.get('confidence', 'LOW'), 2),
        match_type_order.get(x.get('match_type', 'partial'), 3)
    ))
    
    best_match = matched_entities[0]
    
    return {
        'matched_entities': matched_entities,
        'best_match': best_match,
        'confidence': best_match.get('confidence', 'LOW'),
        'original_input': user_input
    }


def _match_drugs(user_input: str, graph_interface) -> List[Dict[str, Any]]:
    """Match drugs by exact name."""
    query = """
    MATCH (d:Drug)
    WHERE toLower(d.drug_name) = $input
       OR toLower(d.drug_name) CONTAINS $input
    RETURN d.drug_id as entity_id, 
           d.drug_name as entity_name,
           'drug' as entity_type
    ORDER BY 
        CASE WHEN toLower(d.drug_name) = $input THEN 0 ELSE 1 END,
        d.drug_name
    LIMIT 5
    """
    
    results = graph_interface.execute_query(query, {"input": user_input})
    matches = []
    
    for result in results:
        is_exact = result['entity_name'].lower() == user_input
        matches.append({
            'entity_type': 'drug',
            'entity_id': result['entity_id'],
            'entity_name': result['entity_name'],
            'match_type': 'exact' if is_exact else 'partial',
            'confidence': 'HIGH' if is_exact else 'MEDIUM',
            'original_input': user_input
        })
    
    return matches


def _match_supplements(user_input: str, graph_interface) -> List[Dict[str, Any]]:
    """Match supplements by name."""
    query = """
    MATCH (s:Supplement)
    WHERE toLower(s.supplement_name) = $input
       OR toLower(s.supplement_name) CONTAINS $input
       OR ANY(word IN split(s.supplement_name, ' ') 
              WHERE toLower(word) = $input)
    RETURN s.supplement_id as entity_id,
           s.supplement_name as entity_name,
           'supplement' as entity_type
    ORDER BY
        CASE WHEN toLower(s.supplement_name) = $input THEN 0 ELSE 1 END,
        s.supplement_name
    LIMIT 5
    """
    
    results = graph_interface.execute_query(query, {"input": user_input})
    matches = []
    
    for result in results:
        is_exact = result['entity_name'].lower() == user_input
        matches.append({
            'entity_type': 'supplement',
            'entity_id': result['entity_id'],
            'entity_name': result['entity_name'],
            'match_type': 'exact' if is_exact else 'partial',
            'confidence': 'HIGH' if is_exact else 'MEDIUM',
            'original_input': user_input
        })
    
    return matches


def _match_brand_names(user_input: str, graph_interface) -> List[Dict[str, Any]]:
    """Match brand names and return associated drugs."""
    query = """
    MATCH (b:BrandName)-[:CONTAINS_DRUG]->(d:Drug)
    WHERE toLower(b.brand_name) CONTAINS $input
    RETURN d.drug_id as entity_id,
           d.drug_name as entity_name,
           b.brand_name as brand_name,
           'drug' as entity_type
    ORDER BY 
        CASE WHEN toLower(b.brand_name) = $input THEN 0 ELSE 1 END,
        b.brand_name
    LIMIT 5
    """
    
    results = graph_interface.execute_query(query, {"input": user_input})
    matches = []
    
    for result in results:
        is_exact = result.get('brand_name', '').lower() == user_input
        matches.append({
            'entity_type': 'drug',  # Brand names map to drugs
            'entity_id': result['entity_id'],
            'entity_name': result['entity_name'],
            'brand_name': result.get('brand_name'),
            'match_type': 'brand',
            'confidence': 'HIGH' if is_exact else 'MEDIUM',
            'original_input': user_input
        })
    
    return matches


def _match_synonyms(user_input: str, graph_interface) -> List[Dict[str, Any]]:
    """Match synonyms and return associated drugs."""
    query = """
    MATCH (d:Drug)-[:KNOWN_AS]->(s:Synonym)
    WHERE toLower(s.synonym) CONTAINS $input
    RETURN d.drug_id as entity_id,
           d.drug_name as entity_name,
           s.synonym as synonym,
           'drug' as entity_type
    ORDER BY
        CASE WHEN toLower(s.synonym) = $input THEN 0 ELSE 1 END,
        s.synonym
    LIMIT 5
    """
    
    results = graph_interface.execute_query(query, {"input": user_input})
    matches = []
    
    for result in results:
        is_exact = result.get('synonym', '').lower() == user_input
        matches.append({
            'entity_type': 'drug',  # Synonyms map to drugs
            'entity_id': result['entity_id'],
            'entity_name': result['entity_name'],
            'synonym': result.get('synonym'),
            'match_type': 'synonym',
            'confidence': 'HIGH' if is_exact else 'MEDIUM',
            'original_input': user_input
        })
    
    return matches


def extract_entities_from_question(
    question: str,
    graph_interface,
    patient_profile: Optional[Dict[str, Any]] = None
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Extract entities from a natural language question using graph matching.
    
    This replaces the LLM-based extract_entities_from_text() function.
    
    Strategy:
    1. Try to match known entities from patient profile first
    2. For question text, extract potential entity names (simple keyword extraction)
    3. Match each potential entity against the graph
    4. Return categorized entities
    
    Args:
        question: User's natural language question
        graph_interface: Neo4j GraphInterface instance
        patient_profile: Optional patient profile with known medications/supplements
    
    Returns:
        {
            'medications': [{'entity_id': 'DB00682', 'entity_name': 'Warfarin', ...}],
            'supplements': [{'entity_id': 'S07', 'entity_name': 'Fish Oil', ...}],
            'conditions': [],  # Conditions are not in graph, keep empty for now
            'dietary_restrictions': []  # Not in graph, keep empty
        }
    """
    # Start with entities from patient profile if available
    medications = []
    supplements = []
    
    if patient_profile:
        # Extract medications from profile
        profile_meds = patient_profile.get('medications', [])
        for med in profile_meds:
            if isinstance(med, dict):
                med_name = med.get('drug_name') or med.get('matched_drug') or med.get('user_input', '')
            else:
                med_name = str(med)
            
            if med_name:
                match_result = match_entities_in_graph(med_name, graph_interface, ['drug', 'brand', 'synonym'])
                if match_result['best_match']:
                    medications.append(match_result['best_match'])
        
        # Extract supplements from profile
        profile_supps = patient_profile.get('supplements', [])
        for supp in profile_supps:
            if isinstance(supp, dict):
                supp_name = supp.get('supplement_name') or supp.get('matched_supplement') or supp.get('user_input', '')
            else:
                supp_name = str(supp)
            
            if supp_name:
                match_result = match_entities_in_graph(supp_name, graph_interface, ['supplement'])
                if match_result['best_match']:
                    supplements.append(match_result['best_match'])
    
    # Extract potential entities from question text
    # Simple approach: look for common medication/supplement keywords
    # This is a basic implementation - could be enhanced with better NLP
    question_lower = question.lower()
    
    # Common supplement keywords
    supplement_keywords = [
        'fish oil', 'vitamin d', 'vitamin c', 'vitamin b', 'coq10', 'coenzyme q10',
        'omega-3', 'omega 3', 'magnesium', 'calcium', 'iron', 'zinc',
        'ginkgo', 'st john', 'st. john', 'echinacea', 'garlic', 'turmeric',
        'glucosamine', 'chondroitin', 'probiotic', 'melatonin'
    ]
    
    # Check for supplement mentions
    for keyword in supplement_keywords:
        if keyword in question_lower:
            # Try to match it
            match_result = match_entities_in_graph(keyword, graph_interface, ['supplement'])
            if match_result['best_match']:
                # Avoid duplicates
                if not any(s.get('entity_id') == match_result['best_match'].get('entity_id') 
                          for s in supplements):
                    supplements.append(match_result['best_match'])
    
    # For medications, we rely more on patient profile
    # But we can try to extract common medication mentions
    medication_keywords = [
        'warfarin', 'aspirin', 'metformin', 'atorvastatin', 'lisinopril',
        'statin', 'blood thinner', 'anticoagulant'
    ]
    
    for keyword in medication_keywords:
        if keyword in question_lower:
            match_result = match_entities_in_graph(keyword, graph_interface, ['drug', 'brand', 'synonym'])
            if match_result['best_match']:
                if not any(m.get('entity_id') == match_result['best_match'].get('entity_id')
                          for m in medications):
                    medications.append(match_result['best_match'])
    
    return {
        'medications': medications,
        'supplements': supplements,
        'conditions': [],  # Not in graph
        'dietary_restrictions': []  # Not in graph, but can be extracted from profile
    }

