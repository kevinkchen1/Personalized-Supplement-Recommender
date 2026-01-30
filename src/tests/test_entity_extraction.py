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


# ============================================================================
# PHASE 2: DATABASE NORMALIZATION (NO LLM YET - JUST LOOKUPS)
# ============================================================================

def normalize_medication_to_database(medication_name: str, graph_interface) -> dict:
    """
    Map user's medication name to database drug ID.
    
    Strategy:
    1. Exact match on drug name
    2. Check brand names table
    3. Check synonyms table
    4. Fuzzy match (future)
    5. LLM fallback (future)
    
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
    
    # Not found - return None for now (Phase 5: LLM fallback)
    return {
        "user_input": medication_name,
        "matched_drug": None,
        "drug_id": None,
        "confidence": "NOT_FOUND",
        "match_type": "none"
    }


# ============================================================================
# TEST CASES
# ============================================================================

def run_tests():
    """Run test cases for entity extraction and normalization"""
    
    print("=" * 80)
    print("PHASE 1: ENTITY EXTRACTION TESTS")
    print("=" * 80)
    
    test_inputs = [
        "I take Advil for headaches",
        "I'm on metforman and lipiter",
        "I take fish oil and vitamin D",
        "I'm vegan and take B12 supplements",
        "I have diabetes and high blood pressure. I take metformin and lisinopril.",
        "I take Tylenol and Motrin",
        "I take BP meds and cholesterol pills",
        "I take Tylenol Cold & Flu",
        "I take a blood thinner",
        "I'm vegan and gluten-free",
    ]
    
    for user_input in test_inputs:
        print(f"\nInput: {user_input}")
        extracted = extract_entities_from_text(user_input)
        print(f"Extracted: {extracted}")
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

    import sys
    from pathlib import Path

    # Add the agents directory to Python path
    sys.path.append(str(Path(__file__).parent.parent / 'agents'))
    from graph_interface import GraphInterface
    import os
    
    print("\n" + "="*80)
    print("PHASE 2: TESTING COMPLETE PIPELINE (Phase 1 → Phase 2)")
    print("="*80)
    
    graph = GraphInterface(
        uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        user=os.getenv("NEO4J_USER", "neo4j"),
        password=os.getenv("NEO4J_PASSWORD")
    )
    
    # Test complete pipeline: Extract (Phase 1) → Normalize (Phase 2)
    test_cases = [
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
    
    for test_case in test_cases:
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
                    
                elif result['confidence'] == 'AMBIGUOUS':
                    print(f"     ⚠️  AMBIGUOUS - Multiple matches found")
                    print(f"        Found {len(result['matches'])} different products")
                    print(f"        Random 3 options:")
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
    
    # Summary
    print("\n" + "="*80)
    print("PHASE 2 TESTING COMPLETE")
    print("="*80)
    print("\nKey Findings:")
    print("  ✅ = Successfully matched to database")
    print("  ⚠️  = Multiple matches found (needs user clarification)")
    print("  ❌ = Not found in database (needs Phase 3 handling)")
    print("\nNext Step: Build Phase 3 - Disambiguation & Drug Class Handling")
    
    graph.close()
