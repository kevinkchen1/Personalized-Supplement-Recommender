"""
Entity Normalizer - Phase 2

Maps user input (with typos/abbreviations) to database IDs.

Strategy:
1. Try exact match
2. Try brand names / partial match
3. Try synonyms
4. Try typo correction + abbreviation expansion (LLM fallback)
5. Return NOT_FOUND

Functions:
- normalize_medication_to_database(): Map medications to Drug nodes
- normalize_supplement_to_database(): Map supplements to Supplement nodes
- correct_patient_profile_data(): Simple typo correction (no DB context)
"""

import os
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()


def correct_patient_profile_data(input_name: str) -> str:
    """
    Simple typo correction and abbreviation expansion.
    No database context - just fixes obvious typos and expands common abbreviations.
    
    This simpler approach is more reliable and makes fewer mistakes.
    
    Handles:
    - Typos: "metforman" → "metformin", "lipiter" → "Lipitor"
    - Abbreviations: "B12" → "Vitamin B-12", "CoQ10" → "Coenzyme Q10"
    - Generic terms: "blood thinner" → "blood thinner" (unchanged)
    
    Args:
        input_name: User's input (may contain typos or abbreviations)
        
    Returns:
        Corrected/expanded name
        
    Examples:
        >>> correct_patient_profile_data("metforman")
        "metformin"
        >>> correct_patient_profile_data("B12")
        "Vitamin B-12"
        >>> correct_patient_profile_data("blood thinner")
        "blood thinner"
    """
    client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    
    prompt = f"""
You are a medical spell-checker that corrects typos and expands abbreviations.

Input: "{input_name}"

Rules:
1. If it's spelled correctly, return it unchanged
2. If it's a typo, return the corrected name
3. If it's an abbreviation, expand it to standard medical format
4. If it's a generic term (like "blood thinner", "pain reliever"), return it unchanged
5. Return ONLY the corrected name (no explanation, no quotes, no preamble)

Common typo corrections:
- "metforman" → "metformin"
- "lipiter" → "Lipitor"
- "advl" → "Advil"
- "atorvastattin" → "Atorvastatin"

Common supplement abbreviations (use hyphens for B vitamins):
- "B12" → "Vitamin B-12"
- "B6" → "Vitamin B-6"
- "B1" → "Vitamin B-1"
- "D3" → "Vitamin D3"
- "D" → "Vitamin D"
- "C" → "Vitamin C"
- "E" → "Vitamin E"
- "K" → "Vitamin K"
- "Omega-3" → "Omega-3 Fatty Acids"
- "Omega 3" → "Omega-3 Fatty Acids"
- "CoQ10" → "Coenzyme Q10"
- "fish oil" → "Fish oil"

Generic terms (return unchanged):
- "blood thinner" → "blood thinner"
- "pain reliever" → "pain reliever"
- "antibiotic" → "antibiotic"
- "statin" → "statin"

Corrected name:"""
    
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=50,
        temperature=0,
        messages=[{"role": "user", "content": prompt}]
    )
    
    # Clean response
    corrected = response.content[0].text.strip().strip('"').strip("'")
    return corrected


def normalize_medication_to_database(medication_name: str, graph_interface) -> dict:
    """
    Map user's medication name to database drug ID.
    
    Strategy (in order):
    1. Exact match on drug name
    2. Check brand names table
    3. Check synonyms table
    4. LLM typo correction + abbreviation expansion (FALLBACK)
    5. Return NOT_FOUND
    
    Args:
        medication_name: User's input medication name
        graph_interface: Neo4j database connection
        
    Returns:
        {
            "user_input": "Advil",
            "matched_drug": "Ibuprofen",
            "drug_id": "DB00328",
            "confidence": "HIGH",
            "match_type": "brand_name"
        }
        
        OR for multiple matches:
        {
            "user_input": "Advil",
            "matches": [{...}, {...}],
            "confidence": "AMBIGUOUS",
            "match_type": "multiple_brand_names",
            "needs_clarification": True
        }
        
        OR for not found:
        {
            "user_input": "blood thinner",
            "matched_drug": None,
            "drug_id": None,
            "confidence": "NOT_FOUND",
            "match_type": "none"
        }
    """
    
    # Step 1: Exact match on drug name
    query_exact = """
    MATCH (d:Drug)
    WHERE toLower(d.drug_name) = toLower($medication_name)
    RETURN d.drug_id as drug_id, d.drug_name as drug_name
    LIMIT 1
    """
    
    results = graph_interface.execute_query(query_exact, {"medication_name": medication_name})
    if results:
        return {
            "user_input": medication_name,
            "matched_drug": results[0]["drug_name"],
            "drug_id": results[0]["drug_id"],
            "confidence": "HIGH",
            "match_type": "exact_drug_name"
        }
    
    # Step 2: Check brand names
    query_brand = """
    MATCH (b:BrandName)-[:CONTAINS_DRUG]->(d:Drug)
    WHERE toLower(b.brand_name) CONTAINS toLower($medication_name)
    RETURN d.drug_id as drug_id, d.drug_name as drug_name, b.brand_name as brand_name
    LIMIT 5
    """
    
    results = graph_interface.execute_query(query_brand, {"medication_name": medication_name})
    if results:
        if len(results) == 1:
            return {
                "user_input": medication_name,
                "matched_drug": results[0]["drug_name"],
                "drug_id": results[0]["drug_id"],
                "brand_name": results[0]["brand_name"],
                "confidence": "HIGH",
                "match_type": "brand_name"
            }
        else:
            # Multiple matches - return all for disambiguation
            return {
                "user_input": medication_name,
                "matches": results,
                "confidence": "AMBIGUOUS",
                "match_type": "multiple_brand_names",
                "needs_clarification": True
            }
    
    # Step 3: Check synonyms
    query_synonym = """
    MATCH (d:Drug)-[:KNOWN_AS]->(s:Synonym)
    WHERE toLower(s.synonym) CONTAINS toLower($medication_name)
    RETURN d.drug_id as drug_id, d.drug_name as drug_name, s.synonym as synonym
    LIMIT 5
    """
    
    results = graph_interface.execute_query(query_synonym, {"medication_name": medication_name})
    if results:
        if len(results) == 1:
            return {
                "user_input": medication_name,
                "matched_drug": results[0]["drug_name"],
                "drug_id": results[0]["drug_id"],
                "synonym": results[0]["synonym"],
                "confidence": "HIGH",
                "match_type": "synonym"
            }
        else:
            return {
                "user_input": medication_name,
                "matches": results,
                "confidence": "AMBIGUOUS",
                "match_type": "multiple_synonyms",
                "needs_clarification": True
            }
    
    # Step 4: NOT FOUND - Try typo correction + abbreviation expansion
    print(f"      🔄 '{medication_name}' not found in database, trying typo correction...")
    corrected = correct_patient_profile_data(medication_name)
    
    # Check if typo was actually corrected or abbreviation expanded
    if corrected.lower() != medication_name.lower():
        print(f"      ✏️  Corrected/expanded: '{medication_name}' → '{corrected}'")
        print(f"      🔍 Retrying database lookup with corrected name...")
        # Recursive call with corrected name (will try steps 1-3 again)
        result = normalize_medication_to_database(corrected, graph_interface)
        # Add note about typo correction
        if result.get('confidence') != 'NOT_FOUND':
            result['typo_corrected_from'] = medication_name
        return result
    
    # Step 5: Still not found - give up
    return {
        "user_input": medication_name,
        "matched_drug": None,
        "drug_id": None,
        "confidence": "NOT_FOUND",
        "match_type": "none"
    }


def normalize_supplement_to_database(supplement_name: str, graph_interface) -> dict:
    """
    Map user's supplement name to database supplement ID.
    Enhanced with better partial matching for abbreviations.
    
    Strategy (in order):
    1. Exact match on supplement name
    2. Enhanced partial match (handles "B12" → "Vitamin B-12")
    3. LLM typo correction + abbreviation expansion
    4. Return NOT_FOUND
    
    Args:
        supplement_name: User's input supplement name
        graph_interface: Neo4j database connection
        
    Returns:
        Similar structure to normalize_medication_to_database()
    """
    
    # Step 1: Exact match on supplement name
    query_exact = """
    MATCH (s:Supplement)
    WHERE toLower(s.supplement_name) = toLower($supplement_name)
    RETURN s.supplement_id as supplement_id, s.supplement_name as supplement_name
    LIMIT 1
    """
    
    results = graph_interface.execute_query(query_exact, {"supplement_name": supplement_name})
    if results:
        return {
            "user_input": supplement_name,
            "matched_supplement": results[0]["supplement_name"],
            "supplement_id": results[0]["supplement_id"],
            "confidence": "HIGH",
            "match_type": "exact_supplement_name"
        }
    
    # Step 2: Enhanced partial match (handles abbreviations)
    # Checks if supplement_name CONTAINS user input OR if user input is a WORD in supplement_name
    # Example: "B12" matches "Vitamin B-12" because B-12 is a word in the name
    query_partial = """
    MATCH (s:Supplement)
    WHERE toLower(s.supplement_name) CONTAINS toLower($supplement_name)
       OR ANY(word IN split(s.supplement_name, ' ') WHERE toLower(word) = toLower($supplement_name))
    RETURN s.supplement_id as supplement_id, s.supplement_name as supplement_name
    LIMIT 5
    """
    
    results = graph_interface.execute_query(query_partial, {"supplement_name": supplement_name})
    if results:
        if len(results) == 1:
            return {
                "user_input": supplement_name,
                "matched_supplement": results[0]["supplement_name"],
                "supplement_id": results[0]["supplement_id"],
                "confidence": "HIGH",
                "match_type": "partial_match"
            }
        else:
            return {
                "user_input": supplement_name,
                "matches": results,
                "confidence": "AMBIGUOUS",
                "match_type": "multiple_supplements",
                "needs_clarification": True
            }
    
    # Step 3: Try typo correction + abbreviation expansion
    print(f"      🔄 '{supplement_name}' not found, trying typo correction/abbreviation expansion...")
    corrected = correct_patient_profile_data(supplement_name)
    
    if corrected.lower() != supplement_name.lower():
        print(f"      ✏️  Corrected/expanded: '{supplement_name}' → '{corrected}'")
        result = normalize_supplement_to_database(corrected, graph_interface)
        if result.get('confidence') != 'NOT_FOUND':
            result['typo_corrected_from'] = supplement_name
        return result
    
    # Step 4: Not found
    return {
        "user_input": supplement_name,
        "matched_supplement": None,
        "supplement_id": None,
        "confidence": "NOT_FOUND",
        "match_type": "none"
    }
