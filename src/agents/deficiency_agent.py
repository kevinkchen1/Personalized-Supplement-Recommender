# """
# SIMPLIFIED Deficiency Agent - DEBUG VERSION

# ONLY checks supplement-nutrient negative interactions.
# Medications and dietary restrictions removed for debugging.
# """

# import os
# from typing import Dict, Any, List, Tuple

# from tools.query_executor import QueryExecutor


# class SimplifiedDeficiencyAgent:
#     """
#     Simplified agent - ONLY checks supplements for debugging.
#     """

#     def __init__(self, graph_interface):
#         self.graph = graph_interface
#         self.executor = QueryExecutor(graph_interface)

#     def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
#         """
#         Check ONLY supplement-nutrient negative interactions.
#         """
#         print("\n" + "=" * 70)
#         print("🥗 SIMPLIFIED DEFICIENCY AGENT: Checking supplements only...")
#         print("=" * 70)

#         # Get supplement names (same pattern as safety agent)
#         supplement_names = self._get_supplement_names(state)

#         # Early exit if no supplements
#         if not supplement_names:
#             print("   ⚠️  No supplements to check")
#             state['deficiency_checked'] = True
#             state['deficiency_results'] = {
#                 'all_at_risk': [],
#                 'supplement_based': [],
#                 'total_count': 0,
#                 'confidence': 0.70,
#                 'verdict': 'NO_SUPPLEMENTS',
#                 'queries_run': [],  # ✨ ADD THIS
#             }
#             return state

#         print(f"   Supplements: {supplement_names}")
#         print(f"   (Sources: normalized_supps={bool(state.get('normalized_supplements'))}, "
#               f"extracted={bool((state.get('extracted_entities') or {}).get('supplements'))}, "
#               f"profile={bool(state.get('patient_profile', {}).get('supplements'))})")

#         # Check supplement deficiencies
#         supp_deficiencies, queries_run = self._check_supplement_deficiencies(supplement_names)

#         # Build results (MATCH safety agent format)
#         results = {
#             'supplement_based': supp_deficiencies,
#             'all_at_risk': [d['nutrient'] for d in supp_deficiencies],
#             'deficiency_details': supp_deficiencies,  # ✨ ADD THIS for app.py
#             'total_count': len(supp_deficiencies),
#             'supplements_checked': supplement_names,
#             'confidence': 0.95 if supp_deficiencies else 0.70,
#             'verdict': 'DEFICIENCIES_FOUND' if supp_deficiencies else 'NO_DEFICIENCIES',
#             'queries_run': queries_run,  # ✨ ADD THIS (key part!)
#         }

#         # Update state
#         state['deficiency_checked'] = True
#         state['deficiency_results'] = results
#         state['confidence_level'] = results['confidence']

#         # Evidence chain
#         evidence = state.get('evidence_chain', [])
#         if supp_deficiencies:
#             nutrients = ', '.join([d['nutrient'] for d in supp_deficiencies])
#             evidence.append(f"Deficiency check: {len(supp_deficiencies)} nutrient(s) at risk ({nutrients}) from supplements")
#         else:
#             evidence.append("Deficiency check: No deficiencies detected")
#         state['evidence_chain'] = evidence

#         # Query history
#         qh = state.get('query_history', [])
#         qh.extend(queries_run)
#         state['query_history'] = qh

#         # Summary
#         print(f"\n   ✅ Deficiency Check Complete")
#         print(f"      Supplement-based: {len(supp_deficiencies)}")
#         print(f"      Total at-risk nutrients: {results['total_count']}")
#         print("=" * 70 + "\n")

#         return state

#     def _get_supplement_names(self, state: Dict) -> List[str]:
#         """
#         Get supplement names from all sources.
#         Matches pattern from safety_check_agent._get_supplement_names()
#         """
#         names = set()

#         # Source 1: Normalized supplements (preferred - from entity_normalizer)
#         for supp in (state.get('normalized_supplements') or []):
#             name = supp.get('matched_supplement') or supp.get('user_input')
#             if name:
#                 names.add(name)

#         # Source 2: Extracted entities from question text
#         extracted = state.get('extracted_entities') or {}
#         for name in (extracted.get('supplements') or []):
#             if name:
#                 names.add(name)

#         # Source 3: Patient profile sidebar
#         profile_supps = state.get('patient_profile', {}).get('supplements', [])
#         for s in profile_supps:
#             if isinstance(s, dict):
#                 name = s.get('supplement_name') or s.get('user_input', '')
#             elif isinstance(s, str):
#                 name = s
#             else:
#                 name = ''
#             if name:
#                 names.add(name)

#         return list(names)

#     def _check_supplement_deficiencies(
#         self,
#         supplements: List[str]
#     ) -> Tuple[List[Dict], List[Dict]]:
#         """
#         Query graph for supplement-nutrient negative interactions.
        
#         Returns:
#             (deficiencies, queries_run)
#         """
#         if not supplements:
#             return [], []

#         print(f"   🔍 Querying database for {len(supplements)} supplement(s)...")

#         # Convert to lowercase for case-insensitive matching
#         supplements_lower = [s.lower() for s in supplements]

#         # DEBUG: Print what we're searching for
#         print(f"   🔍 Searching for (lowercase): {supplements_lower}")

#         query = """
#         MATCH (s:Supplement)-[r:NEGATIVE_INTERACTION]->(n:Nutrient)
#         WHERE toLower(s.supplement_name) IN $supplement_names_lower
#         RETURN s.supplement_name AS supplement,
#                n.nutrient_name AS nutrient,
#                r.mechanism AS mechanism,
#                r.severity AS severity,
#                r.notes AS notes
#         """

#         result = self.executor.execute(query, {'supplement_names_lower': supplements_lower})

#         # DEBUG: Print query result
#         print(f"   📊 Query success: {result['success']}")
#         print(f"   📊 Query count: {result['count']}")
#         if result['success'] and result['data']:
#             print(f"   📊 First result: {result['data'][0]}")

#         # Build queries_run metadata (match safety agent format)
#         queries_run = [{
#             'query_type': 'supplement_depletion',
#             'supplements': supplements,
#             'cypher': query,  # ✨ ADD CYPHER TEXT
#             'parameters': {'supplement_names_lower': supplements_lower},  # ✨ ADD PARAMETERS
#             'success': result['success'],
#             'result_count': result['count'],
#             'execution_time': result.get('execution_time', 0),
#         }]

#         deficiencies = []
#         if result['success'] and result['data']:
#             for row in result['data']:
#                 deficiency = {
#                     'nutrient': row['nutrient'],
#                     'source_type': 'supplement',
#                     'source_name': row['supplement'],
#                     'risk_level': row['severity'],
#                     'mechanism': row['mechanism'],
#                     'evidence': row.get('notes', ''),
#                     'confidence': 0.95
#                 }
#                 deficiencies.append(deficiency)
#                 print(f"      ✅ Found: {row['supplement']} → {row['nutrient']} ({row['severity']})")
#         else:
#             print(f"      ⚠️  No results found in database")

#         return deficiencies, queries_run


# # ======================================================================
# # STANDALONE FUNCTION FOR LANGGRAPH
# # ======================================================================

# def deficiency_agent(state: Dict[str, Any]) -> Dict[str, Any]:
#     """Entry point for LangGraph workflow."""
#     from graph.graph_interface import GraphInterface

#     graph = state.get('graph_interface')
#     if graph is None:
#         graph = GraphInterface(
#             uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
#             user=os.getenv("NEO4J_USER", "neo4j"),
#             password=os.getenv("NEO4J_PASSWORD", ""),
#         )

#     agent = SimplifiedDeficiencyAgent(graph)
#     return agent.run(state)

"""
Comprehensive Deficiency Agent - Dietary + Supplements

Identifies nutrient deficiencies from TWO sources:
1. Diet-based deficiencies (DietaryRestriction -[:DEFICIENT_IN]-> Nutrient)
2. Supplement-induced deficiencies (Supplement -[:NEGATIVE_INTERACTION]-> Nutrient)

Detects CRITICAL overlaps when multiple sources affect the same nutrient.

Input gathering matches safety_check_agent.py pattern.
"""

import os
from typing import Dict, Any, List, Tuple

from tools.query_executor import QueryExecutor


class ComprehensiveDeficiencyAgent:
    """
    Specialist agent that checks nutrient deficiencies from:
    - Dietary restrictions (graph relationship)
    - Supplements (graph relationship: NEGATIVE_INTERACTION)
    """

    def __init__(self, graph_interface):
        self.graph = graph_interface
        self.executor = QueryExecutor(graph_interface)

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze nutrient deficiencies from dietary restrictions and supplements.
        """
        print("\n" + "=" * 70)
        print("🥗 COMPREHENSIVE DEFICIENCY AGENT: Analyzing nutrient gaps...")
        print("=" * 70)

        # Gather inputs using pattern from safety_check_agent.py
        dietary_restriction_names = self._get_dietary_restriction_names(state)
        supplement_names = self._get_supplement_names(state)

        # Early exit if nothing to check
        if not dietary_restriction_names and not supplement_names:
            print("   ⚠️  No dietary restrictions or supplements to analyze")
            state['deficiency_checked'] = True
            state['deficiency_results'] = {
                'all_at_risk': [],
                'diet_based': [],
                'supplement_based': [],
                'critical_overlaps': [],
                'total_count': 0,
                'confidence': 0.70,
                'verdict': 'NOTHING_TO_CHECK',
                'queries_run': [],
            }
            return state

        print(f"   Dietary restrictions: {dietary_restriction_names or 'None'}")
        print(f"   Supplements: {supplement_names or 'None'}")
        
        # Print sources for debugging
        print(f"   (Sources: normalized_diet={bool(state.get('normalized_dietary_restrictions'))}, "
              f"extracted={bool((state.get('extracted_entities') or {}).get('dietary_restrictions'))}, "
              f"profile={bool(state.get('patient_profile', {}).get('dietary_restrictions'))})")
        print(f"   (Sources: normalized_supps={bool(state.get('normalized_supplements'))}, "
              f"extracted={bool((state.get('extracted_entities') or {}).get('supplements'))}, "
              f"profile={bool(state.get('patient_profile', {}).get('supplements'))})")

        # Initialize results
        all_queries = []
        
        # PATHWAY 1: Diet-based deficiencies
        diet_deficiencies, diet_queries = self._check_diet_deficiencies(
            dietary_restriction_names
        )
        all_queries.extend(diet_queries)
        
        # PATHWAY 2: Supplement-induced deficiencies
        supp_deficiencies, supp_queries = self._check_supplement_deficiencies(
            supplement_names
        )
        all_queries.extend(supp_queries)

        # Aggregate and detect overlaps
        all_at_risk, critical_overlaps = self._aggregate_deficiencies(
            diet_deficiencies,
            supp_deficiencies
        )

        # Build final results
        results = self._build_final_results(
            diet_deficiencies,
            supp_deficiencies,
            all_at_risk,
            critical_overlaps,
            dietary_restriction_names,
            supplement_names,
            all_queries
        )

        # Update state
        state['deficiency_checked'] = True
        state['deficiency_results'] = results
        state['confidence_level'] = results['confidence']

        # Evidence chain
        evidence = state.get('evidence_chain', [])
        if results['total_count'] > 0:
            evidence.append(
                f"Deficiency check: {results['total_count']} nutrient(s) at risk "
                f"from {len(dietary_restriction_names)} diet(s), {len(supplement_names)} supplement(s)"
            )
            if critical_overlaps:
                evidence.append(
                    f"⚠️ CRITICAL: {len(critical_overlaps)} nutrient(s) affected by multiple sources!"
                )
        else:
            evidence.append("Deficiency check: No deficiencies detected")
        state['evidence_chain'] = evidence

        # Query history
        qh = state.get('query_history', [])
        qh.extend(all_queries)
        state['query_history'] = qh

        # Summary
        print(f"\n   ✅ Deficiency Analysis Complete")
        print(f"      Total at-risk nutrients: {results['total_count']}")
        print(f"      Diet-based: {len(diet_deficiencies)}")
        print(f"      Supplement-based: {len(supp_deficiencies)}")
        print(f"      🚨 Critical overlaps: {len(critical_overlaps)}")
        print("=" * 70 + "\n")

        return state

    # ==================================================================
    # INPUT GATHERING (matches safety_check_agent.py pattern)
    # ==================================================================
    
    def _get_dietary_restriction_names(self, state: Dict) -> List[str]:
        """
        Get dietary restriction names from all sources.
        Matches pattern from safety_check_agent._get_supplement_names()
        """
        names = set()

        # Source 1: Normalized dietary restrictions (if you create this in supervisor)
        for restriction in (state.get('normalized_dietary_restrictions') or []):
            if isinstance(restriction, dict):
                name = restriction.get('matched_restriction') or restriction.get('user_input')
            elif isinstance(restriction, str):
                name = restriction
            else:
                name = ''
            if name:
                names.add(name)

        # Source 2: Extracted entities from question text
        extracted = state.get('extracted_entities') or {}
        for name in (extracted.get('dietary_restrictions') or []):
            if name:
                names.add(name)

        # Source 3: Patient profile sidebar
        profile = state.get('patient_profile', {})
        profile_restrictions = profile.get('dietary_restrictions', [])
        
        # Handle both list and comma-separated string
        if isinstance(profile_restrictions, str):
            profile_restrictions = [r.strip() for r in profile_restrictions.split(',') if r.strip()]
        
        for restriction in profile_restrictions:
            if isinstance(restriction, dict):
                name = restriction.get('restriction_name') or restriction.get('user_input', '')
            elif isinstance(restriction, str):
                name = restriction
            else:
                name = ''
            if name:
                names.add(name)

        return list(names)

    def _get_supplement_names(self, state: Dict) -> List[str]:
        """
        Get supplement names from all sources.
        Matches pattern from safety_check_agent._get_supplement_names()
        """
        names = set()

        # Source 1: Normalized supplements (preferred - from entity_normalizer)
        for supp in (state.get('normalized_supplements') or []):
            name = supp.get('matched_supplement') or supp.get('user_input')
            if name:
                names.add(name)

        # Source 2: Extracted entities from question text
        extracted = state.get('extracted_entities') or {}
        for name in (extracted.get('supplements') or []):
            if name:
                names.add(name)

        # Source 3: Patient profile sidebar
        profile_supps = state.get('patient_profile', {}).get('supplements', [])
        for s in profile_supps:
            if isinstance(s, dict):
                name = s.get('supplement_name') or s.get('user_input', '')
            elif isinstance(s, str):
                name = s
            else:
                name = ''
            if name:
                names.add(name)

        return list(names)

    # ==================================================================
    # PATHWAY 1: DIET-BASED DEFICIENCIES
    # ==================================================================
    
    def _check_diet_deficiencies(
        self, 
        restrictions: List[str]
    ) -> Tuple[List[Dict], List[Dict]]:
        """
        Query graph for diet-based nutrient deficiencies.
        
        Returns:
            (deficiencies, queries_run)
        """
        if not restrictions:
            return [], []

        print(f"   🔍 Analyzing {len(restrictions)} dietary restriction(s)...")

        # Convert restriction names to lowercase
        restrictions_lower = [r.lower() for r in restrictions]

        query = """
        MATCH (dr:DietaryRestriction)-[r:DEFICIENT_IN]->(n:Nutrient)
        WHERE toLower(dr.dietary_restriction_name) IN $restrictions_lower
        RETURN dr.dietary_restriction_name AS diet,
               n.nutrient_name             AS nutrient,
               n.category                  AS nutrient_category,
               n.rda_adult                 AS rda,
               r.risk_level                AS risk_level
        ORDER BY
            CASE r.risk_level
                WHEN 'HIGH'   THEN 0
                WHEN 'MEDIUM' THEN 1
                ELSE 2
            END,
            n.nutrient_name
        """

        result = self.executor.execute(query, {'restrictions_lower': restrictions_lower})

        # Build queries_run metadata (match safety agent format)
        queries_run = [{
            'query_type': 'diet_deficiency',
            'restrictions': restrictions,
            'cypher': query,
            'parameters': {'restrictions_lower': restrictions_lower},
            'success': result['success'],
            'result_count': result['count'],
            'execution_time': result.get('execution_time', 0),
        }]

        deficiencies = []
        if result['success'] and result['data']:
            for row in result['data']:
                deficiency = {
                    'nutrient': row['nutrient'],
                    'source_type': 'diet',
                    'source_name': row['diet'],
                    'risk_level': row.get('risk_level', 'MEDIUM'),
                    'mechanism': 'dietary_restriction',
                    'evidence': f"{row['diet']} diet is commonly deficient in {row['nutrient']}",
                    'confidence': 0.90,
                    'nutrient_category': row.get('nutrient_category', ''),
                    'rda': row.get('rda', '')
                }
                deficiencies.append(deficiency)
                print(f"      ✅ Found: {row['diet']} → {row['nutrient']} ({row.get('risk_level', 'MEDIUM')})")
        else:
            print(f"      ⊘  No deficiencies found")

        return deficiencies, queries_run

    # ==================================================================
    # PATHWAY 2: SUPPLEMENT-INDUCED DEFICIENCIES
    # ==================================================================
    
    def _check_supplement_deficiencies(
        self,
        supplements: List[str]
    ) -> Tuple[List[Dict], List[Dict]]:
        """
        Query graph for supplement-nutrient negative interactions.
        
        Returns:
            (deficiencies, queries_run)
        """
        if not supplements:
            return [], []

        print(f"   🔍 Analyzing {len(supplements)} supplement(s)...")

        # Convert to lowercase for case-insensitive matching
        supplements_lower = [s.lower() for s in supplements]

        query = """
        MATCH (s:Supplement)-[r:NEGATIVE_INTERACTION]->(n:Nutrient)
        WHERE toLower(s.supplement_name) IN $supplement_names_lower
        RETURN s.supplement_name AS supplement,
               n.nutrient_name AS nutrient,
               r.mechanism AS mechanism,
               r.severity AS severity,
               r.notes AS notes
        """

        result = self.executor.execute(query, {'supplement_names_lower': supplements_lower})

        # Build queries_run metadata (match safety agent format)
        queries_run = [{
            'query_type': 'supplement_depletion',
            'supplements': supplements,
            'cypher': query,
            'parameters': {'supplement_names_lower': supplements_lower},
            'success': result['success'],
            'result_count': result['count'],
            'execution_time': result.get('execution_time', 0),
        }]

        deficiencies = []
        if result['success'] and result['data']:
            for row in result['data']:
                deficiency = {
                    'nutrient': row['nutrient'],
                    'source_type': 'supplement',
                    'source_name': row['supplement'],
                    'risk_level': row['severity'],
                    'mechanism': row['mechanism'],
                    'evidence': row.get('notes', ''),
                    'confidence': 0.95
                }
                deficiencies.append(deficiency)
                print(f"      ✅ Found: {row['supplement']} → {row['nutrient']} ({row['severity']})")
        else:
            print(f"      ⊘  No deficiencies found")

        return deficiencies, queries_run

    # ==================================================================
    # AGGREGATION & OVERLAP DETECTION
    # ==================================================================
    
    def _aggregate_deficiencies(
        self,
        diet_def: List[Dict],
        supp_def: List[Dict]
    ) -> Tuple[Dict[str, List[Dict]], List[Dict]]:
        """
        Aggregate all deficiencies and detect critical overlaps.
        
        Returns:
            (all_at_risk, critical_overlaps)
            
            all_at_risk: {nutrient_name -> [source1, source2, ...]}
            critical_overlaps: [{nutrient, sources, risk_multiplier, ...}]
        """
        all_at_risk = {}  # nutrient -> list of sources

        # Aggregate from both pathways
        for deficiency in diet_def + supp_def:
            nutrient = deficiency['nutrient']
            
            if nutrient not in all_at_risk:
                all_at_risk[nutrient] = []
            
            all_at_risk[nutrient].append({
                'source_type': deficiency['source_type'],
                'source_name': deficiency['source_name'],
                'risk_level': deficiency['risk_level'],
                'mechanism': deficiency['mechanism']
            })

        # Detect critical overlaps (2+ sources affecting same nutrient)
        critical_overlaps = []
        for nutrient, sources in all_at_risk.items():
            if len(sources) >= 2:
                # Multiple sources = CRITICAL
                source_names = [s['source_name'] for s in sources]
                highest_risk = self._get_highest_risk(sources)
                
                critical_overlaps.append({
                    'nutrient': nutrient,
                    'sources': sources,
                    'source_names': source_names,
                    'risk_multiplier': len(sources),
                    'combined_risk': 'CRITICAL',
                    'highest_individual_risk': highest_risk,
                    'warning': f"{nutrient} is affected by {len(sources)} different sources!"
                })
                print(f"      🚨 CRITICAL OVERLAP: {nutrient} affected by {source_names}")

        return all_at_risk, critical_overlaps

    def _get_highest_risk(self, sources: List[Dict]) -> str:
        """Get the highest risk level from a list of sources."""
        risk_order = {'CRITICAL': 0, 'HIGH': 1, 'MODERATE': 2, 'MEDIUM': 2, 'LOW': 3}
        highest = 'LOW'
        for source in sources:
            risk = source.get('risk_level', 'LOW')
            if risk_order.get(risk, 3) < risk_order.get(highest, 3):
                highest = risk
        return highest

    # ==================================================================
    # RESULT BUILDING
    # ==================================================================
    
    def _build_final_results(
        self,
        diet_def: List[Dict],
        supp_def: List[Dict],
        all_at_risk: Dict[str, List[Dict]],
        critical_overlaps: List[Dict],
        dietary_restrictions: List[str],
        supplements: List[str],
        queries_run: List[Dict]
    ) -> Dict[str, Any]:
        """
        Build comprehensive results structure for state.
        """
        # Count by risk level
        all_deficiencies = diet_def + supp_def
        high_risk_count = sum(1 for d in all_deficiencies if d['risk_level'] in ['HIGH', 'CRITICAL'])
        critical_count = len(critical_overlaps)

        # Calculate confidence
        if all_deficiencies:
            # Average confidence from all sources
            avg_confidence = sum(d['confidence'] for d in all_deficiencies) / len(all_deficiencies)
            # Boost if we have critical overlaps (high certainty)
            if critical_overlaps:
                avg_confidence = min(0.95, avg_confidence + 0.05)
            confidence = round(avg_confidence, 2)
        else:
            confidence = 0.70

        return {
            # Individual pathways
            'diet_based': diet_def,
            'supplement_based': supp_def,
            
            # Aggregated view
            'all_at_risk': list(all_at_risk.keys()),
            'all_at_risk_details': all_at_risk,
            'deficiency_details': all_deficiencies,  # For app.py display
            
            # Critical overlaps
            'critical_overlaps': critical_overlaps,
            
            # Summary counts
            'total_count': len(all_at_risk),
            'diet_count': len(diet_def),
            'supplement_count': len(supp_def),
            'critical_count': critical_count,
            'high_risk_count': high_risk_count,
            
            # Context
            'restrictions_checked': dietary_restrictions,
            'supplements_checked': supplements,
            
            # Metadata
            'confidence': confidence,
            'verdict': 'DEFICIENCIES_FOUND' if all_at_risk else 'NO_DEFICIENCIES',
            'queries_run': queries_run,  # For app.py display
        }


# ======================================================================
# STANDALONE FUNCTION FOR LANGGRAPH
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

    agent = ComprehensiveDeficiencyAgent(graph)
    return agent.run(state)