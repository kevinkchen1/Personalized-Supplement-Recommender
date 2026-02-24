"""
Safety Check - Interaction Specialist

Checks for dangerous interactions between supplements and medications
across four pathways in the knowledge graph:

1. DIRECT             — Supplement -[SUPPLEMENT_INTERACTS_WITH]-> Medication
2. DRUG_DRUG          — Supplement -> ActiveIngredient -> Drug -[INTERACTS_WITH]-> Drug <- Medication
3. HIDDEN_PHARMA      — Supplement -> ActiveIngredient -[EQUIVALENT_TO]-> Drug <- Medication
4. SIMILAR_EFFECT     — Supplement -[HAS_SIMILAR_EFFECT_TO]-> Category <- Drug <- Medication

Reads from state : supplements_list, medications_list
Writes to state  : safety_checked, safety_results, evidence_chain
"""

import logging
from typing import Any, Dict, List

from src.graph.connections import graph_interface

logger = logging.getLogger(__name__)


# ==================== CYPHER QUERY ====================

SAFETY_QUERY = """
// === PATH 1: Direct Supplement → Medication interaction ===
MATCH (s:Supplement)-[r:SUPPLEMENT_INTERACTS_WITH]->(m:Medication)
WHERE toLower(s.supplement_name) = $supplement_name
  AND toLower(m.medication_name) IN $medication_names_lower
RETURN s.supplement_name AS supplement,
       m.medication_name AS target,
       r.interaction_description AS description,
       'MODERATE' AS severity,
       null AS detail,
       'DIRECT_SUPPLEMENT_MEDICATION' AS pathway

UNION

// === PATH 2: Supplement → Drug ← Medication (shared drug interaction) ===
MATCH (s:Supplement)-[:CONTAINS]->(ai:ActiveIngredient)-[:EQUIVALENT_TO]->(d1:Drug)
      -[r:INTERACTS_WITH]->(d2:Drug)<-[:MEDICATION_CONTAINS_DRUG]-(m:Medication)
WHERE toLower(s.supplement_name) = $supplement_name
  AND toLower(m.medication_name) IN $medication_names_lower
RETURN s.supplement_name AS supplement,
       m.medication_name AS target,
       r.description AS description,
       'HIGH' AS severity,
       d1.drug_name + ' interacts with ' + d2.drug_name AS detail,
       'DRUG_DRUG_INTERACTION' AS pathway

UNION

// === PATH 3: Hidden pharma equivalence ===
MATCH (s:Supplement)-[:CONTAINS]->(a:ActiveIngredient)
      -[:EQUIVALENT_TO]->(d:Drug)<-[:MEDICATION_CONTAINS_DRUG]-(m:Medication)
WHERE toLower(s.supplement_name) = $supplement_name
  AND toLower(m.medication_name) IN $medication_names_lower
RETURN s.supplement_name AS supplement,
       m.medication_name AS target,
       'Contains equivalent pharmaceutical ingredient - duplication risk' AS description,
       'HIGH' AS severity,
       a.active_ingredient + ' = ' + d.drug_name AS detail,
       'HIDDEN_PHARMA_EQUIVALENCE' AS pathway

UNION

// === PATH 4: Similar pharmacological effect ===
MATCH (s:Supplement)-[:HAS_SIMILAR_EFFECT_TO]->(c:Category)
      <-[:BELONGS_TO]-(d:Drug)<-[:MEDICATION_CONTAINS_DRUG]-(m:Medication)
WHERE toLower(s.supplement_name) = $supplement_name
  AND toLower(m.medication_name) IN $medication_names_lower
RETURN s.supplement_name AS supplement,
       m.medication_name AS target,
       'Similar pharmacological effect - additive or antagonistic risk' AS description,
       'MODERATE' AS severity,
       c.category AS detail,
       'SIMILAR_EFFECT' AS pathway
"""


# ==================== QUERY RUNNER ====================

def _check_supplement(supplement_name: str, medication_names: List[str]) -> List[Dict[str, Any]]:
    """
    Run SAFETY_QUERY for one supplement against all medications.

    Args:
        supplement_name: Matched supplement name from supplements_list
        medication_names: Matched medication names from medications_list

    Returns:
        List of interaction records, empty if none found
    """
    parameters = {
        'supplement_name': supplement_name.lower(),
        'medication_names_lower': [m.lower() for m in medication_names]
    }

    try:
        results = graph_interface.execute_query(SAFETY_QUERY, parameters)
        return results or []
    except Exception as e:
        logger.error(f"Safety query failed for '{supplement_name}': {e}")
        return []


# ==================== RESULT BUILDER ====================

def _build_results(
    all_interactions: List[Dict[str, Any]],
    supplements_checked: List[str],
    medications_checked: List[str]
) -> Dict[str, Any]:

    by_pathway: Dict[str, List] = {}
    for ix in all_interactions:
        by_pathway.setdefault(ix.get('pathway', 'UNKNOWN'), []).append(ix)

    if not all_interactions:
        status = 'not_found'
        summary = (
            f"No interactions found between "
            f"{', '.join(supplements_checked)} and "
            f"{', '.join(medications_checked)}"
        )
    else:
        status = 'found'
        pathway_summary = ', '.join(
            f"{pathway}: {len(records)}"
            for pathway, records in by_pathway.items()
        )
        summary = (
            f"Found {len(all_interactions)} interaction(s) "
            f"between {', '.join(supplements_checked)} and "
            f"{', '.join(medications_checked)} "
            f"({pathway_summary})"
        )

    return {
        'specialist': 'safety',
        'status': status,
        'entities_checked': supplements_checked + medications_checked,
        'summary': summary,
        'interactions': all_interactions,
        'by_pathway': by_pathway,
        'supplements_checked': supplements_checked,
        'medications_checked': medications_checked,
    }


# ==================== LANGGRAPH NODE ====================

def safety_check(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    LangGraph node: Check supplement-medication interactions.

    Reads from state:
        - supplements_list: clean matched supplement names
        - medications_list: clean matched medication names

    Writes to state:
        - safety_checked: True
        - safety_results: compact structured summary
        - evidence_chain: appended with safety finding

    Args:
        state: Current ConversationState

    Returns:
        Partial state update dict
    """
    print("\n" + "=" * 60)
    print("🔬 SAFETY CHECK: Checking supplement-medication interactions...")
    print("=" * 60)

    current_supplements = state.get('supplements_list', [])
    candidate_supplements = state.get('candidate_supplements_list', [])
    supplements = list(dict.fromkeys(current_supplements + candidate_supplements)) 
    medications = state.get('medications_list', [])

    # ── Early exit: nothing to check ──
    if not supplements:
        print("   ⚠️  No supplements to check")
        results = {
            'specialist': 'safety',
            'status': 'no_supplements',
            'entities_checked': [],
            'summary': 'No supplements identified to check',
            'interactions': [],
            'by_pathway': {}
        }
        return {
            'safety_checked': True,
            'safety_results': results,
            'evidence_chain': state.get('evidence_chain', []) + [
                'Safety check: skipped — no supplements to check'
            ]
        }

    if not medications:
        print("   ⚠️  No medications to check against")
        results = {
            'specialist': 'safety',
            'status': 'no_medications',
            'entities_checked': supplements,
            'summary': 'No medications to check against',
            'interactions': [],
            'by_pathway': {}
        }
        return {
            'safety_checked': True,
            'safety_results': results,
            'evidence_chain': state.get('evidence_chain', []) + [
                'Safety check: skipped — no medications to check against'
            ]
        }

    if candidate_supplements:
        print(f"   Current supplements  : {current_supplements if current_supplements else 'none'}")
        print(f"   Candidate supplements: {candidate_supplements}")
        print(f"   Checking combined    : {supplements}")
    else:
        print(f"   Supplements : {supplements}")
    print(f"   Medications : {medications}")

    # ── Run check for each supplement ──
    all_interactions = []
    for supplement in supplements:
        print(f"\n   Checking: {supplement}")
        interactions = _check_supplement(supplement, medications)

        if interactions:
            for ix in interactions:
                print(f"      ⚠️  [{ix.get('pathway')}] "
                      f"{ix.get('supplement')} ↔ {ix.get('target')}: "
                      f"{str(ix.get('description', ''))[:80]}")
            all_interactions.extend(interactions)
        else:
            print(f"      ✅ No interactions found")

    # ── Build compact results ──
    results = _build_results(all_interactions, supplements, medications)

    print(f"\n   {'⚠️  Interactions found' if all_interactions else '✅ No interactions found'}: "
          f"{results['summary']}")
    print("=" * 60 + "\n")

    return {
        'safety_checked': True,
        'safety_results': results,
        'evidence_chain': state.get('evidence_chain', []) + [
            f"Safety check: {results['summary']}"
        ]
    }