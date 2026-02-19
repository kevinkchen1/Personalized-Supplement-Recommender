"""
Safety Check Agent - Interaction Specialist

Checks for dangerous interactions between supplements and medications
using the QueryGenerator + QueryExecutor tools.

Safety pathways checked:
1. Direct Supplement → Medication interaction
2. Supplement → Drug ← Medication (via CONTAINS_DRUG)
3. Hidden pharma: Supplement → ActiveIngredient → Drug ← Medication
4. Similar effects: Supplement → Category ← Drug ← Medication

Role: Safety specialist
"""

from typing import Dict, Any, List
import os

from tools.query_generator import QueryGenerator, generate_comprehensive_safety_query
from tools.query_executor import QueryExecutor, run_comprehensive_safety


class SafetyCheckAgent:
    """
    Specialist agent for checking supplement-medication interactions.
    Uses the comprehensive safety query to check ALL pathways at once.
    """

    def __init__(self, graph_interface):
        self.graph = graph_interface
        self.executor = QueryExecutor(graph_interface)
        self.generator = QueryGenerator()

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Check safety of supplements against user's medications.

        Reads from state:
            - normalized_supplements (from supervisor entity extraction)
            - normalized_medications (from supervisor entity extraction)
            - patient_profile (from sidebar)
            - extracted_entities (from entity extractor)

        Writes to state:
            - safety_checked: True
            - safety_results: {safe, interactions, confidence, ...}
            - evidence_chain: appended with safety evidence
            - query_history: appended with queries run
        """
        print("\n" + "=" * 60)
        print("🔬 SAFETY AGENT: Checking interactions...")
        print("=" * 60)

        # ----------------------------------------------------------
        # 1. Gather supplement and medication names
        # ----------------------------------------------------------
        supplement_names = self._get_supplement_names(state)
        medication_names = self._get_medication_names(state)

        if not supplement_names:
            print("   ⚠️  No supplements to check")
            state['safety_checked'] = True
            state['safety_results'] = {
                'safe': True,
                'interactions': [],
                'confidence': 0.9,
                'verdict': 'NO_SUPPLEMENTS',
                'reason': 'No supplements identified to check',
            }
            return state

        if not medication_names:
            print("   ⚠️  No medications to check against")
            state['safety_checked'] = True
            state['safety_results'] = {
                'safe': True,
                'interactions': [],
                'confidence': 0.9,
                'verdict': 'NO_MEDICATIONS',
                'reason': 'No medications to check against',
            }
            return state

        print(f"   Supplements: {supplement_names}")
        print(f"   Medications: {medication_names}")
        print(f"   (Sources: normalized_supps={bool(state.get('normalized_supplements'))}, "
              f"extracted={bool((state.get('extracted_entities') or {}).get('supplements'))}, "
              f"profile={bool(state.get('patient_profile', {}).get('supplements'))})")
        print(f"   (Sources: normalized_meds={bool(state.get('normalized_medications'))}, "
              f"extracted={bool((state.get('extracted_entities') or {}).get('medications'))}, "
              f"profile={bool(state.get('patient_profile', {}).get('medications'))})")

        # ----------------------------------------------------------
        # 2. Run comprehensive safety check for each supplement
        # ----------------------------------------------------------
        all_interactions = []
        all_queries_run = []

        for supp in supplement_names:
            print(f"\n   --- Checking: {supp} ---")

            # Generate and execute the comprehensive UNION query
            query_dict = generate_comprehensive_safety_query(supp, medication_names)

            if query_dict.get('error'):
                print(f"   ❌ Query generation error: {query_dict['error']}")
                continue

            result = self.executor.execute_query_dict(query_dict)

            # Track the query for the debug panel
            all_queries_run.append({
                'query_type': 'comprehensive_safety',
                'supplement': supp,
                'medications': medication_names,
                'cypher': query_dict.get('query', ''),
                'parameters': query_dict.get('parameters', {}),
                'success': result['success'],
                'result_count': result['count'],
                'execution_time': result.get('execution_time', 0),
            })

            if result['success'] and result['data']:
                for row in result['data']:
                    interaction = {
                        'supplement': row.get('supplement', supp),
                        'target': row.get('target', ''),
                        'description': row.get('description', ''),
                        'severity': row.get('severity', 'UNKNOWN'),
                        'detail': row.get('detail', ''),
                        'pathway': row.get('pathway', 'UNKNOWN'),
                    }
                    all_interactions.append(interaction)
                    desc = interaction.get('description') or 'No description available'
                    print(f"   ⚠️  [{interaction['pathway']}] {supp} ↔ {interaction['target']}: {desc}")

            elif result['success']:
                print(f"   ✅ No interactions found for {supp}")
            else:
                print(f"   ❌ Query failed: {result.get('error')}")

        # ----------------------------------------------------------
        # 3. Evaluate results
        # ----------------------------------------------------------
        safe = len(all_interactions) == 0
        confidence = self._calculate_confidence(all_interactions)

        unsafe_supplements = list(set([ix['supplement'] for ix in all_interactions]))
        safe_supplements = [s for s in supplement_names if s not in unsafe_supplements]

        state['unsafe_supplements_list'] = unsafe_supplements
        state['safe_supplements_list'] = safe_supplements

        if unsafe_supplements:
            print(f"   ⚠️  Marked {len(unsafe_supplements)} supplements as unsafe: {', '.join(unsafe_supplements)}")
        if safe_supplements:
            print(f"   ✅ Marked {len(safe_supplements)} supplements as safe: {', '.join(safe_supplements)}")

        # Group interactions by pathway for the summary
        by_pathway: Dict[str, List] = {}
        for ix in all_interactions:
            by_pathway.setdefault(ix['pathway'], []).append(ix)

        results = {
            'safe': safe,
            'interactions': all_interactions,
            'interaction_count': len(all_interactions),
            'by_pathway': by_pathway,
            'confidence': confidence,
            'supplements_checked': supplement_names,
            'medications_checked': medication_names,
            'verdict': 'SAFE' if safe else 'CAUTION ADVISED',
            'queries_run': all_queries_run,
        }

        # ----------------------------------------------------------
        # 4. Update state
        # ----------------------------------------------------------
        state['safety_checked'] = True
        state['safety_results'] = results
        state['confidence_level'] = confidence

        # Add to evidence chain
        evidence = state.get('evidence_chain', [])
        if safe:
            evidence.append(
                f"Safety check: No interactions found for "
                f"{', '.join(supplement_names)} with {', '.join(medication_names)}"
            )
        else:
            pathways_summary = ', '.join(
                f"{p}: {len(rows)}" for p, rows in by_pathway.items()
            )
            evidence.append(
                f"Safety check: {len(all_interactions)} interaction(s) found "
                f"({pathways_summary})"
            )
        state['evidence_chain'] = evidence

        # Add to query history
        qh = state.get('query_history', [])
        for qr in all_queries_run:
            qh.append({
                'query_type': qr['query_type'],
                'result_count': qr['result_count'],
                'success': qr['success'],
            })
        state['query_history'] = qh

        print(f"\n   ✅ Safety Check Complete: {results['verdict']}")
        print(f"      Interactions: {len(all_interactions)}, Confidence: {confidence:.2f}")
        print("=" * 60 + "\n")

        return state

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_supplement_names(self, state: Dict) -> List[str]:
        """
        Get supplement names from supervisor's clean list.
        
        Supervisor handles extraction, normalization, and deduplication.
        Agents simply read from the pre-processed list.
        """
        return state.get('supplements_list', [])

    def _get_medication_names(self, state: Dict) -> List[str]:
        """
        Get medication names from supervisor's clean list.
        
        Supervisor handles extraction, normalization, and deduplication.
        Agents simply read from the pre-processed list.
        """
        return state.get('medications_list', [])
    
    def _calculate_confidence(self, interactions: List[Dict]) -> float:
        """
        Calculate confidence based on what was found.

        - No interactions → high confidence (0.90) that it's safe
        - Interactions found → moderate-high confidence (0.80) in the warning
        - Many interactions from multiple pathways → high confidence (0.85) in warning
        """
        if not interactions:
            return 0.90

        pathways = set(ix.get('pathway', '') for ix in interactions)

        if len(pathways) >= 2:
            # Multiple pathways corroborate each other
            return 0.85
        else:
            return 0.80


# ======================================================================
# Standalone function for LangGraph
# ======================================================================

def safety_check_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    """Entry point for LangGraph workflow."""
    from graph.graph_interface import GraphInterface

    # Use existing graph_interface from state, or create new one
    graph = state.get('graph_interface')
    if graph is None:
        graph = GraphInterface(
            uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            user=os.getenv("NEO4J_USER", "neo4j"),
            password=os.getenv("NEO4J_PASSWORD", ""),
        )

    agent = SafetyCheckAgent(graph)
    return agent.run(state)
