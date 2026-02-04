"""
Patient Profile Entity Extraction - Isolated Testing
Test entity extraction and database normalization separately before integration
"""

import os
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

# ============================================================================
# PHASE 1: ENTITY EXTRACTION (LLM ONLY)
# ============================================================================

def extract_entities_from_text(user_input: str) -> dict:
    """
    Use LLM to extract medications, supplements, conditions from natural language.
    
    USE CASE: Chat questions (unstructured text)
    Example: "I take Advil and want to add Fish Oil"
    
    Returns:
        {
            "medications": [...],
            "supplements": [...],
            "conditions": [...],
            "dietary_restrictions": [...]
        }
    """
    client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    
    prompt = f"""
You are a medical entity extraction system. Extract structured information from user input.

User input: "{user_input}"

Extract:
1. Medications (including brand names, generics, misspellings)
2. Supplements (vitamins, minerals, herbs)
3. Health conditions
4. Dietary restrictions (vegan, vegetarian, keto, etc.)

Return ONLY valid JSON (no markdown, no preamble):
{{
    "medications": ["medication1", "medication2"],
    "supplements": ["supplement1"],
    "conditions": ["condition1"],
    "dietary_restrictions": ["restriction1"]
}}

If nothing found for a category, return empty array [].
"""
    
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1000,
        temperature=0,
        messages=[{"role": "user", "content": prompt}]
    )
    
    import json
    return json.loads(response.content[0].text)


def correct_patient_profile_data(input_name: str) -> str:
    """
    Simple typo correction and abbreviation expansion.
    No database context - just fixes obvious typos and expands common abbreviations.
    
    This simpler approach is more reliable and makes fewer mistakes.
    
    Handles:
    - Typos: "metforman" → "metformin"
    - Abbreviations: "B12" → "Vitamin B-12"
    - Generic terms: "blood thinner" → "blood thinner" (unchanged)
    
    Returns: Corrected/expanded name
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


def process_patient_profile(profile_data: dict, graph_interface) -> dict:
    """
    Process STRUCTURED patient profile from sidebar (Method 1).
    No LLM extraction needed - user already categorized.
    
    USE CASE: Patient profile sidebar
    Input: {
        'medications': 'metforman, lipiter, advl',
        'supplements': 'fish ol, vitmin D',
        'conditions': ['Diabetes'],
        'dietary_restrictions': ['Vegan']
    }
    
    Returns: Normalized entities with drug IDs
    """
    
    # Step 1: Simple parsing (split by commas)
    medications_text = profile_data.get('medications', '')
    medications_raw = [m.strip() for m in medications_text.split(',') if m.strip()]
    
    supplements_text = profile_data.get('supplements', '')
    supplements_raw = [s.strip() for s in supplements_text.split(',') if s.strip()]
    
    # Step 2: Normalize medications (includes typo correction fallback)
    normalized_medications = []
    for med in medications_raw:
        result = normalize_medication_to_database(med, graph_interface)
        normalized_medications.append(result)
    
    # Step 3: Normalize supplements (same process)
    normalized_supplements = []
    for supp in supplements_raw:
        result = normalize_supplement_to_database(supp, graph_interface)
        normalized_supplements.append(result)
    
    # Step 4: Get conditions and dietary restrictions (already structured from dropdowns)
    conditions = profile_data.get('conditions', [])
    dietary_restrictions = profile_data.get('dietary_restrictions', [])
    
    return {
        'medications': normalized_medications,
        'supplements': normalized_supplements,
        'conditions': conditions,
        'dietary_restrictions': dietary_restrictions
    }


# ============================================================================
# PHASE 2: DATABASE NORMALIZATION
# ============================================================================

def normalize_medication_to_database(medication_name: str, graph_interface) -> dict:
    """
    Map user's medication name to database drug ID.
    
    Strategy (in order):
    1. Exact match on drug name
    2. Check brand names table
    3. Check synonyms table
    4. LLM typo correction + abbreviation expansion (FALLBACK)
    5. Return NOT_FOUND
    
    Returns:
        {
            "user_input": "Advil",
            "matched_drug": "Ibuprofen",
            "drug_id": "DB00328",
            "confidence": "HIGH",
            "match_type": "brand_name"
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
        # If multiple matches, need disambiguation (Phase 3)
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
    2. Enhanced partial match (handles "B12" → "Vitamin B12")
    3. LLM typo correction + abbreviation expansion
    4. Return NOT_FOUND
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
    # Checks if supplement_name CONTAINS user input OR if user input matches any WORD in supplement_name
    # Example: "B12" matches "Vitamin B12" because B12 is a word in the name
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


# ============================================================================
# TEST CASES
# ============================================================================

def run_tests():
    """Run test cases for entity extraction"""
    
    print("=" * 80)
    print("PHASE 1A: CHAT QUESTION ENTITY EXTRACTION TESTS")
    print("=" * 80)
    
    test_inputs = [
        "I take Advil for headaches",
        "I'm on metforman and lipiter",
        "I take fish oil and vitamin D",
        "I'm vegan and take B12 supplements",
        "I have diabetes and high blood pressure. I take metformin and lisinopril.",
    ]
    
    for user_input in test_inputs:
        print(f"\nInput: {user_input}")
        extracted = extract_entities_from_text(user_input)
        print(f"Extracted: {extracted}")
        print("-" * 80)
    
    print("\n" + "=" * 80)
    print("PHASE 1B: PATIENT PROFILE PARSING TESTS (No LLM)")
    print("=" * 80)
    print("\nNOTE: This tests simple comma-separated parsing.")
    print("      Typo correction happens in Phase 2 normalization.\n")
    
    profile_test_cases = [
        {
            "description": "Profile with typos",
            "profile": {
                "medications": "metforman, lipiter, advl",
                "supplements": "fish ol, vitmin D",
                "conditions": ["Diabetes", "High Blood Pressure"],
                "dietary_restrictions": ["Vegan"]
            }
        },
        {
            "description": "Profile with correct spelling",
            "profile": {
                "medications": "Warfarin, Metformin, Atorvastatin",
                "supplements": "Fish Oil, Vitamin D, CoQ10",
                "conditions": ["Atrial Fibrillation"],
                "dietary_restrictions": ["Vegetarian"]
            }
        }
    ]
    
    for test_case in profile_test_cases:
        print(f"\nTest: {test_case['description']}")
        print(f"Input Medications: {test_case['profile']['medications']}")
        print(f"Input Supplements: {test_case['profile']['supplements']}")
        
        # Simple parsing (no LLM)
        medications_raw = [m.strip() for m in test_case['profile']['medications'].split(',') if m.strip()]
        supplements_raw = [s.strip() for s in test_case['profile']['supplements'].split(',') if s.strip()]
        
        print(f"Parsed Medications: {medications_raw}")
        print(f"Parsed Supplements: {supplements_raw}")
        print(f"Conditions: {test_case['profile']['conditions']}")
        print(f"Dietary Restrictions: {test_case['profile']['dietary_restrictions']}")
        print("-" * 80)
    
    print("\n" + "=" * 80)
    print("PHASE 2: DATABASE NORMALIZATION TESTS")
    print("=" * 80)
    print("\nNOTE: This requires Neo4j connection. Run separately with:")
    print("  from graph_interface import GraphInterface")
    print("  graph = GraphInterface(uri, user, password)")
    print("  result = normalize_medication_to_database('Advil', graph)")


if __name__ == "__main__":
    # Test Phase 1 (no DB needed)
    run_tests()
    
    # Test Phase 2 (needs DB connection)
    # Uncomment when ready to test with database:
    import sys
    from pathlib import Path

    # Add the agents directory to Python path
    sys.path.append(str(Path(__file__).parent.parent / 'graph'))
    from graph_interface import GraphInterface
    import os
    
    print("\n" + "="*80)
    print("PHASE 2: DATABASE NORMALIZATION TESTS")
    print("="*80)
    
    graph = GraphInterface(
        uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        user=os.getenv("NEO4J_USER", "neo4j"),
        password=os.getenv("NEO4J_PASSWORD")
    )
    
    # ========================================================================
    # TEST SUITE 1: Chat Questions (Phase 1 Extraction → Phase 2 Normalization)
    # ========================================================================
    
    print("\n" + "="*80)
    print("TEST SUITE 1: CHAT QUESTIONS (Complete Pipeline)")
    print("="*80)
    
    chat_test_cases = [
        {
            "description": "Brand names",
            "input": "I take Advil for headaches"
        },
        {
            "description": "Typos that get corrected",
            "input": "I'm on metforman and lipiter"
        },
        {
            "description": "Generic drug class term",
            "input": "I take a blood thinner"
        },
        {
            "description": "Multiple brand name products",
            "input": "I use Tylenol when needed"
        },
        {
            "description": "Combination drugs",
            "input": "I take Tylenol Cold & Flu"
        }
    ]
    
    for test_case in chat_test_cases:
        print(f"\n{'='*80}")
        print(f"TEST: {test_case['description']}")
        print(f"{'='*80}")
        print(f"User Input: \"{test_case['input']}\"")
        
        # Phase 1: Extract entities
        extracted = extract_entities_from_text(test_case['input'])
        print(f"\nPhase 1 - Extracted:")
        print(f"  Medications: {extracted['medications']}")
        print(f"  Supplements: {extracted['supplements']}")
        print(f"  Conditions: {extracted['conditions']}")
        print(f"  Dietary Restrictions: {extracted['dietary_restrictions']}")
        
        # Phase 2: Normalize each medication
        if extracted['medications']:
            print(f"\nPhase 2 - Database Normalization:")
            for med in extracted['medications']:
                print(f"\n  → Normalizing: \"{med}\"")
                result = normalize_medication_to_database(med, graph)
                
                if result['confidence'] == 'HIGH':
                    print(f"     ✅ FOUND (HIGH confidence)")
                    print(f"        Matched Drug: {result['matched_drug']}")
                    print(f"        Drug ID: {result['drug_id']}")
                    print(f"        Match Type: {result['match_type']}")
                    if 'brand_name' in result:
                        print(f"        Brand Name: {result['brand_name']}")
                    if 'typo_corrected_from' in result:
                        print(f"        ✏️  Corrected/expanded from: '{result['typo_corrected_from']}'")
                    
                elif result['confidence'] == 'AMBIGUOUS':
                    print(f"     ⚠️  AMBIGUOUS - Multiple matches found")
                    print(f"        Found {len(result['matches'])} different products")
                    print(f"        Top 3 options:")
                    for i, match in enumerate(result['matches'][:3], 1):
                        print(f"          {i}. {match['drug_name']} - {match['brand_name']}")
                    print(f"        Status: needs_clarification = {result['needs_clarification']}")
                    
                elif result['confidence'] == 'NOT_FOUND':
                    print(f"     ❌ NOT FOUND in database")
                    print(f"        Possible reasons:")
                    print(f"          - Generic term (e.g., 'blood thinner')")
                    print(f"          - Misspelling too severe")
                    print(f"          - Not in our database")
        else:
            print(f"\n  No medications to normalize")
        
        print(f"\n{'-'*80}")
    
    # ========================================================================
    # TEST SUITE 2: Patient Profile (Direct Normalization with Typo Correction)
    # ========================================================================
    
    print("\n" + "="*80)
    print("TEST SUITE 2: PATIENT PROFILE PROCESSING")
    print("="*80)
    
    profile_test_cases = [
        {
            "description": "Profile with typos (tests typo correction fallback)",
            "profile": {
                "medications": "metforman, lipiter, advl",
                "supplements": "fish ol, vitmin D",
                "conditions": ["Diabetes", "High Blood Pressure"],
                "dietary_restrictions": ["Vegan"]
            }
        },
        {
            "description": "Profile with correct spelling (no typo correction needed)",
            "profile": {
                "medications": "Warfarin, Metformin, Atorvastatin",
                "supplements": "Fish Oil, Vitamin D, CoQ10",
                "conditions": ["Atrial Fibrillation"],
                "dietary_restrictions": ["Vegetarian"]
            }
        },
        {
            "description": "Profile with mix of brand names and generics + abbreviations",
            "profile": {
                "medications": "Advil, Metformin, Lipitor",
                "supplements": "Omega-3, B12",
                "conditions": [],
                "dietary_restrictions": []
            }
        }
    ]
    
    for test_case in profile_test_cases:
        print(f"\n{'='*80}")
        print(f"TEST: {test_case['description']}")
        print(f"{'='*80}")
        
        profile = test_case['profile']
        print(f"\nPatient Profile Input:")
        print(f"  Medications: {profile['medications']}")
        print(f"  Supplements: {profile['supplements']}")
        print(f"  Conditions: {profile['conditions']}")
        print(f"  Dietary Restrictions: {profile['dietary_restrictions']}")
        
        # Process profile (with typo correction in Phase 2)
        print(f"\nProcessing Profile...")
        processed = process_patient_profile(profile, graph)
        
        # Display results
        print(f"\n📋 NORMALIZED MEDICATIONS:")
        for med_result in processed['medications']:
            if med_result['confidence'] == 'HIGH':
                print(f"  ✅ {med_result['user_input']} → {med_result['matched_drug']} ({med_result['drug_id']})")
                if 'typo_corrected_from' in med_result:
                    print(f"     ✏️  Corrected/expanded from: '{med_result['typo_corrected_from']}'")
            elif med_result['confidence'] == 'AMBIGUOUS':
                print(f"  ⚠️  {med_result['user_input']} → Multiple matches ({len(med_result['matches'])} options)")
            else:
                print(f"  ❌ {med_result['user_input']} → Not found")
        
        print(f"\n💊 NORMALIZED SUPPLEMENTS:")
        for supp_result in processed['supplements']:
            if supp_result['confidence'] == 'HIGH':
                print(f"  ✅ {supp_result['user_input']} → {supp_result['matched_supplement']} ({supp_result['supplement_id']})")
                if 'typo_corrected_from' in supp_result:
                    print(f"     ✏️  Corrected/expanded from: '{supp_result['typo_corrected_from']}'")
            elif supp_result['confidence'] == 'AMBIGUOUS':
                print(f"  ⚠️  {supp_result['user_input']} → Multiple matches")
            else:
                print(f"  ❌ {supp_result['user_input']} → Not found")
        
        print(f"\n🏥 CONDITIONS: {processed['conditions']}")
        print(f"🥗 DIETARY RESTRICTIONS: {processed['dietary_restrictions']}")
        print(f"\n{'-'*80}")
    
    # Summary
    print("\n" + "="*80)
    print("TESTING COMPLETE")
    print("="*80)
    print("\nKey Features Tested:")
    print("  ✅ Chat question entity extraction (Phase 1)")
    print("  ✅ Patient profile parsing (simple comma split)")
    print("  ✅ Database normalization with exact/brand/synonym matching")
    print("  ✅ Enhanced partial matching for abbreviations (B12 → Vitamin B12)")
    print("  ✅ Typo correction + abbreviation expansion fallback")
    print("  ✅ Ambiguity detection for multiple matches")
    print("\nNext Steps:")
    print("  → Phase 3: Disambiguation (ask user which option)")
    print("  → Phase 3: Drug class handling (map 'blood thinner' to category)")
    print("  → Phase 3: Combination product grouping")
    
    graph.close()




    