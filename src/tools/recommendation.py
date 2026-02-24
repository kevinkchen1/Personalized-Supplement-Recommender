"""
Recommendation - Recommendation Specialist

Finds supplements that treat the patient's conditions/symptoms.
Safety checking of candidates is handled separately by safety_check.py
after the supervisor routes back through the loop.

Query flow:
1. SYMPTOM_QUERY  — find supplements via TREATS relationship (exact match)
2. BROAD_QUERY    — fallback keyword search if no exact match

Current supplements are excluded from candidates — no point recommending
what the patient already takes.

Reads from state : conditions_list, supplements_list
Writes to state  : recommendations_checked, recommendation_results, evidence_chain
"""

import logging
from typing import Any, Dict, List

from src.graph.connections import graph_interface

logger = logging.getLogger(__name__)


# ==================== CYPHER QUERIES ====================

# Find supplements that treat a condition — exact symptom name match

SYMPTOM_QUERY = """
MATCH (s:Supplement)-[:TREATS]->(sym:Symptom)
WHERE toLower(sym.symptom_name) CONTAINS $condition_lower
RETURN DISTINCT
    s.supplement_id AS supplement_id,
    s.supplement_name AS supplement_name,
    s.safety_rating AS safety_rating,
    sym.symptom_name AS symptom_treated
ORDER BY s.supplement_name
"""

# Fallback — search by individual keywords when exact match fails

BROAD_QUERY = """
MATCH (s:Supplement)-[:TREATS]->(sym:Symptom)
WHERE ANY(word IN $words WHERE toLower(sym.symptom_name) CONTAINS word)
RETURN DISTINCT
    s.supplement_id AS supplement_id,
    s.supplement_name AS supplement_name,
    s.safety_rating AS safety_rating,
    sym.symptom_name AS symptom_treated
ORDER BY s.supplement_name
LIMIT 10
"""


# ==================== CANDIDATE FINDER ====================

def _find_candidates(condition: str) -> List[Dict[str, Any]]:
    """
    Find supplements that treat the given condition.

    Tries exact symptom match first, falls back to keyword search
    if no results found.

    Args:
        condition: Condition or symptom string from conditions_list

    Returns:
        List of candidate dicts with supplement_name, safety_rating, symptom_treated
    """
    condition_lower = condition.lower().strip()

    # Primary: exact symptom name match
    try:
        results = graph_interface.execute_query(
            SYMPTOM_QUERY,
            {'condition_lower': condition_lower}
        )
        if results:
            print(f"      ✅ Found {len(results)} candidates for '{condition}'")
            return results
    except Exception as e:
        logger.error(f"Symptom query failed for '{condition}': {e}")

    # Fallback: keyword search
    words = [w for w in condition_lower.split() if len(w) > 3]
    if not words:
        return []

    print(f"      🔄 No exact match for '{condition}', trying keyword search: {words}")
    try:
        results = graph_interface.execute_query(
            BROAD_QUERY,
            {'words': words}
        )
        if results:
            print(f"      ✅ Keyword search found {len(results)} candidates")
            return results
    except Exception as e:
        logger.error(f"Broad query failed for '{condition}': {e}")

    return []


# ==================== RESULT BUILDER ====================

def _build_results(
    candidates: List[Dict[str, Any]],
    conditions: List[str],
    medications: List[str]
) -> Dict[str, Any]:

    if not candidates:
        status = 'not_found'
        summary = f"No supplement candidates found for: {', '.join(conditions)}"
    else:
        status = 'found'
        summary = (
            f"Found {len(candidates)} supplement candidate(s) for "
            f"{', '.join(conditions)} — safety check pending"
        )

    return {
        'specialist': 'recommendation',
        'status': status,
        'entities_checked': conditions + medications,
        'summary': summary,
        'recommendations': candidates,
        'candidate_supplements': [c.get('supplement_name') for c in candidates],
        'conditions_checked': conditions,
    }


# ==================== LANGGRAPH NODE ====================

def recommendation(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    LangGraph node: Find and evaluate supplement recommendations.

    Reads from state:
        - conditions_list: health conditions / symptoms from question + profile
        - medications_list: patient's medications (for safety cross-check)
        - supplements_list: patient's current supplements (excluded from candidates)

    Writes to state:
        - recommendations_checked: True
        - recommendation_results: compact structured summary
        - evidence_chain: appended with recommendation finding

    Args:
        state: Current ConversationState

    Returns:
        Partial state update dict
    """
    print("\n" + "=" * 60)
    print("💊 RECOMMENDATION: Finding supplement options...")
    print("=" * 60)

    conditions = state.get('conditions_list', [])
    current_supplements = state.get('supplements_list', [])
    current_supplements_lower = {s.lower() for s in current_supplements}

    # ── Early exit: no conditions to address ──
    if not conditions:
        print("   ⚠️  No conditions to find recommendations for")
        results = {
            'specialist': 'recommendation',
            'status': 'no_conditions',
            'entities_checked': [],
            'summary': 'No conditions or symptoms to find recommendations for',
            'recommendations': [],
            'candidate_supplements': []
        }
        return {
            'recommendations_checked': True,
            'recommendation_results': results,
            'evidence_chain': state.get('evidence_chain', []) + [
                'Recommendation check: skipped — no conditions to address'
            ]
        }

    print(f"   Conditions  : {conditions}")
    print(f"   Current supplements (excluded): "
          f"{current_supplements if current_supplements else 'none'}")

    # ── Find and evaluate candidates for each condition ──
    seen_supplements: set = set()
    all_evaluated: List[Dict[str, Any]] = []

    for condition in conditions:
        print(f"\n   Searching for: '{condition}'")
        candidates = _find_candidates(condition)

        if not candidates:
            print(f"      ❌ No candidates found")
            continue

        for candidate in candidates:
            name = candidate.get('supplement_name', '')

            # Skip if already seen or is a current supplement
            if not name or name in seen_supplements:
                continue
            if name.lower() in current_supplements_lower:
                print(f"      ⏭️  Skipping '{name}' — already in current supplements")
                continue

            seen_supplements.add(name)
            all_evaluated.append(candidate)
            print(f"      ✅ {name} (safety_rating: {candidate.get('safety_rating', 'unknown')})")

    # ── Sort by safety_rating ──
    safety_rating_rank = {'Generally safe': 2, 'Use with caution': 1, 'Not recommended': 0}
    all_evaluated.sort(
        key=lambda r: safety_rating_rank.get(r.get('safety_rating', ''), 0),
        reverse=True
    )

    # ── Build compact results ──
    results = _build_results(all_evaluated, conditions, [])

    print(f"\n   {results['summary']}")
    print("=" * 60 + "\n")

    return {
        'recommendations_checked': True,
        'recommendation_results': results,
        'candidate_supplements_list': results['candidate_supplements'],
        'evidence_chain': state.get('evidence_chain', []) + [
            f"Recommendation check: {results['summary']}"
        ]
    }