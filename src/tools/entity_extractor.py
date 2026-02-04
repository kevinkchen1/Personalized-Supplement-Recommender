"""
Entity Extractor - Phase 1

Extracts medications, supplements, conditions, and dietary restrictions from:
1. Natural language chat questions (unstructured)
2. Patient profile data (structured comma-separated)

Functions:
- extract_entities_from_text(): For chat questions
- process_patient_profile(): For patient profile sidebar
"""

import os
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()


def extract_entities_from_text(user_input: str) -> dict:
    """
    Extract entities from natural language chat questions.
    
    USE CASE: When user asks questions in natural language
    Example: "I take Advil and want to add Fish Oil. Is it safe?"
    
    Features:
    - Automatically corrects typos ("metforman" → "metformin")
    - Distinguishes medications from supplements
    - Extracts health conditions
    - Identifies dietary restrictions
    
    Args:
        user_input: Natural language question from user
        
    Returns:
        {
            "medications": ["Advil"],
            "supplements": ["Fish Oil"],
            "conditions": [],
            "dietary_restrictions": []
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


def process_patient_profile(profile_data: dict, graph_interface) -> dict:
    """
    Process structured patient profile from sidebar.
    
    USE CASE: When user fills out patient profile form
    Input is already categorized by user into separate fields.
    
    Process:
    1. Simple parsing (split comma-separated values)
    2. Normalize medications to database (with typo correction)
    3. Normalize supplements to database (with typo correction)
    4. Pass through conditions and dietary restrictions
    
    Args:
        profile_data: {
            'medications': 'Warfarin, Metformin, Atorvastatin',
            'supplements': 'Fish Oil, Vitamin D, CoQ10',
            'conditions': ['Diabetes', 'High Blood Pressure'],
            'dietary_restrictions': ['Vegan']
        }
        graph_interface: Neo4j database connection
        
    Returns:
        {
            'medications': [
                {'drug_id': 'DB00682', 'drug_name': 'Warfarin', ...},
                ...
            ],
            'supplements': [
                {'supplement_id': 'S07', 'supplement_name': 'Fish Oil', ...},
                ...
            ],
            'conditions': ['Diabetes', 'High Blood Pressure'],
            'dietary_restrictions': ['Vegan']
        }
    """
    # Import here to avoid circular imports
    from .entity_normalizer import (
        normalize_medication_to_database,
        normalize_supplement_to_database
    )
    
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
    
    # Step 3: Normalize supplements (includes typo correction fallback)
    normalized_supplements = []
    for supp in supplements_raw:
        result = normalize_supplement_to_database(supp, graph_interface)
        normalized_supplements.append(result)
    
    # Step 4: Pass through conditions and dietary restrictions (already structured)
    conditions = profile_data.get('conditions', [])
    dietary_restrictions = profile_data.get('dietary_restrictions', [])
    
    return {
        'medications': normalized_medications,
        'supplements': normalized_supplements,
        'conditions': conditions,
        'dietary_restrictions': dietary_restrictions
    }
