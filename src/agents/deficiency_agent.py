"""
Dietary Deficiency Agent

Identifies nutrient deficiencies based on the user's dietary restrictions
by querying the knowledge graph.

DB Schema used:
  (DietaryRestriction)-[:DEFICIENT_IN {risk_level}]->(Nutrient)

State keys read:
  - patient_profile.dietary_restrictions   (from sidebar, e.g. ['Vegan'])
  - extracted_entities.dietary_restrictions (from question text)
  - patient_profile.medications            (for context in synthesis)
  - graph_interface                        (Neo4j connection)

State keys written:
  - deficiency_checked  : True
  - deficiency_results  : {at_risk, risk_levels, deficiency_details, sources, ...}
  - evidence_chain      : appended
  - query_history       : appended
  - confidence_level    : updated
"""

import os
from typing import Dict, Any, List

from tools.query_executor import QueryExecutor


class DietaryDeficiencyAgent:
    """
    Specialist agent that checks which nutrients a user is likely
    deficient in based on their dietary restrictions.
    """

    def __init__(self, graph_interface):
        self.graph = graph_interface
        self.executor = QueryExecutor(graph_interface)

    # ------------------------------------------------------------------
    # Main entry
    # ------------------------------------------------------------------
    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyse dietary deficiencies and write results into LangGraph state.
        """
        print("\n" + "=" * 60)
        print("🥗 DIETARY DEFICIENCY AGENT: Checking nutrient gaps...")
        print("=" * 60)

        # 1. Gather dietary restrictions from ALL sources
        restrictions = self._get_dietary_restrictions(state)
        medications  = self._get_medication_names(state)

        if not restrictions:
            print("   ⚠️  No dietary restrictions provided")
            state['deficiency_checked'] = True
            state['deficiency_results'] = {
                'at_risk': [],
                'risk_levels': {},
                'deficiency_details': [],
                'sources': [],
                'verdict': 'NO_RESTRICTIONS',
                'reason': 'No dietary restrictions provided to analyse',
            }
            return state

        print(f"   Dietary restrictions: {restrictions}")
        if medications:
            print(f"   Medications (context): {medications}")

        # 2. Query knowledge graph for deficiencies
        deficiency_rows, queries_run = self._query_deficiencies(restrictions)

        # 3. Build structured results
        results = self._build_results(deficiency_rows, restrictions, medications)

        # 4. Write to state
        state['deficiency_checked'] = True
        state['deficiency_results'] = results
        state['confidence_level'] = results['confidence']

        # Evidence chain
        evidence = state.get('evidence_chain', [])
        if results['at_risk']:
            nutrients_str = ', '.join(results['at_risk'])
            evidence.append(
                f"Deficiency check: {len(results['at_risk'])} nutrient(s) at risk "
                f"({nutrients_str}) from dietary restrictions {restrictions}"
            )
        else:
            evidence.append(
                f"Deficiency check: No deficiencies found for restrictions {restrictions}"
            )
        state['evidence_chain'] = evidence

        # Query history
        qh = state.get('query_history', [])
        for qr in queries_run:
            qh.append(qr)
        state['query_history'] = qh

        print(f"\n   ✅ Deficiency Check Complete")
        print(f"      At-risk nutrients: {len(results['at_risk'])}")
        print(f"      High-risk: {results.get('high_risk_count', 0)}")
        print("=" * 60 + "\n")

        return state

    # ------------------------------------------------------------------
    # Data gathering helpers
    # ------------------------------------------------------------------
    def _get_dietary_restrictions(self, state: Dict) -> List[str]:
        """
        Merge dietary restrictions from all sources (sidebar + question).
        """
        restrictions = set()

        # Source 1: Patient profile sidebar
        profile = state.get('patient_profile', {})
        for key in ('dietary_restrictions', 'diet'):
            vals = profile.get(key, [])
            if isinstance(vals, str):
                vals = [vals]
            for v in (vals or []):
                if v:
                    restrictions.add(v)

        # Source 2: Extracted entities from question text
        extracted = state.get('extracted_entities') or {}
        for v in (extracted.get('dietary_restrictions') or []):
            if v:
                restrictions.add(v)

        return list(restrictions)

    def _get_medication_names(self, state: Dict) -> List[str]:
        """Get medication names (used for context, not for querying)."""
        names = set()

        # Normalized medications
        for m in (state.get('normalized_medications') or []):
            name = m.get('matched_drug') or m.get('user_input')
            if name:
                names.add(name)

        # Extracted entities
        extracted = state.get('extracted_entities') or {}
        for name in (extracted.get('medications') or []):
            if name:
                names.add(name)

        # Patient profile sidebar
        profile_meds = state.get('patient_profile', {}).get('medications', [])
        for m in profile_meds:
            if isinstance(m, dict):
                name = m.get('drug_name') or m.get('matched_drug') or m.get('user_input', '')
            elif isinstance(m, str):
                name = m
            else:
                name = ''
            if name:
                names.add(name)

        return list(names)

    # ------------------------------------------------------------------
    # Knowledge graph queries
    # ------------------------------------------------------------------
    def _query_deficiencies(self, restrictions: List[str]):
        """
        Query the Neo4j graph for nutrient deficiencies linked to
        dietary restrictions.

        Returns:
            (rows, queries_run) where rows is a list of dicts and
            queries_run is metadata for the debug panel.
        """
        restrictions_lower = [r.lower() for r in restrictions]

        query = """
        MATCH (dr:DietaryRestriction)-[r:DEFICIENT_IN]->(n:Nutrient)
        WHERE toLower(dr.dietary_restriction_name) IN $restrictions
        RETURN dr.dietary_restriction_name AS diet,
               n.nutrient_name             AS nutrient,
               n.category                  AS nutrient_category,
               n.rda_adult                 AS rda,
               n.description               AS nutrient_description,
               r.risk_level                AS risk_level
        ORDER BY
            CASE r.risk_level
                WHEN 'HIGH'   THEN 0
                WHEN 'MEDIUM' THEN 1
                ELSE 2
            END,
            n.nutrient_name
        """

        result = self.executor.execute(query, {'restrictions': restrictions_lower})

        queries_run = [{
            'query_type': 'dietary_deficiency',
            'restrictions': restrictions,
            'success': result['success'],
            'result_count': result['count'],
        }]

        rows = result['data'] if result['success'] else []
        return rows, queries_run

    # ------------------------------------------------------------------
    # Result building
    # ------------------------------------------------------------------
    def _build_results(
        self,
        rows: List[Dict],
        restrictions: List[str],
        medications: List[str],
    ) -> Dict[str, Any]:
        """
        Transform raw DB rows into the structured result dict that the
        synthesis agent and UI expect.
        """
        at_risk: List[str] = []
        risk_levels: Dict[str, str] = {}
        deficiency_details: List[Dict] = []
        sources: List[str] = []

        seen_nutrients = set()

        for row in rows:
            nutrient = row.get('nutrient', 'Unknown')
            risk     = row.get('risk_level', 'MEDIUM')
            diet     = row.get('diet', 'Unknown')

            if nutrient not in seen_nutrients:
                at_risk.append(nutrient)
                seen_nutrients.add(nutrient)

            # Keep the highest risk level per nutrient
            prev = risk_levels.get(nutrient)
            if prev is None or self._risk_rank(risk) < self._risk_rank(prev):
                risk_levels[nutrient] = risk

            deficiency_details.append({
                'nutrient': nutrient,
                'nutrient_category': row.get('nutrient_category', ''),
                'rda': row.get('rda', ''),
                'description': row.get('nutrient_description', ''),
                'risk_level': risk,
                'source_diet': diet,
                'reason': f"{diet} diet is commonly deficient in {nutrient}",
            })

            source_label = f"Diet: {diet}"
            if source_label not in sources:
                sources.append(source_label)

        high_risk_count = sum(1 for v in risk_levels.values() if v == 'HIGH')
        confidence = 0.85 if rows else 0.70

        return {
            'at_risk': at_risk,
            'risk_levels': risk_levels,
            'deficiency_details': deficiency_details,
            'sources': sources,
            'restrictions_checked': restrictions,
            'medications_context': medications,
            'total_deficiencies': len(at_risk),
            'high_risk_count': high_risk_count,
            'confidence': confidence,
            'verdict': 'DEFICIENCIES_FOUND' if at_risk else 'NO_DEFICIENCIES',
        }

    @staticmethod
    def _risk_rank(level: str) -> int:
        """Lower number = higher risk."""
        return {'HIGH': 0, 'MEDIUM': 1, 'LOW': 2}.get(level, 3)


# ======================================================================
# Standalone function for LangGraph
# ======================================================================

def deficiency_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    """Entry point for LangGraph workflow."""
    from graph.graph_interface import GraphInterface

    graph = state.get('graph_interface')
    if graph is None:
        graph = GraphInterface(
            uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            user=os.getenv("NEO4J_USER", "neo4j"),
            password=os.getenv("NEO4J_PASSWORD", ""),
        )

    agent = DietaryDeficiencyAgent(graph)
    return agent.run(state)
