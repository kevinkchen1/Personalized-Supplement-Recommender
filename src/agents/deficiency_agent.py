"""
Comprehensive Deficiency Agent - Diet + Supplements + Medications

Identifies nutrient deficiencies from THREE sources:
1. Diet-based deficiencies (DietaryRestriction -[:DEFICIENT_IN]-> Nutrient)
2. Supplement-induced deficiencies (Supplement -[:NEGATIVE_INTERACTION]-> Nutrient)
3. Medication-induced deficiencies (Drug -[:INTERACTS_WITH_NUTRIENT]-> Nutrient)

Detects CRITICAL overlaps when multiple sources affect the same nutrient.
"""

import os
from typing import Dict, Any, List, Tuple

from tools.query_executor import QueryExecutor
from tools.query_generator import (
    generate_diet_deficiency_query_dict,
    generate_supplement_depletion_query_dict,
    generate_medication_nutrient_depletion_query_dict 
)


class ComprehensiveDeficiencyAgent:
    """
    Specialist agent that checks nutrient deficiencies from:
    - Dietary restrictions (graph relationship)
    - Supplements (graph relationship: NEGATIVE_INTERACTION)
    - Medications (LLM analysis of Drug properties)
    """

    def __init__(self, graph_interface):
        self.graph = graph_interface
        self.executor = QueryExecutor(graph_interface)

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze nutrient deficiencies from all three pathways.
        """
        print("\n" + "=" * 70)
        print("🥗 COMPREHENSIVE DEFICIENCY AGENT: Analyzing nutrient gaps...")
        print("=" * 70)

        # DEBUG: Check what's in state
        print(f"   🔍 DEBUG: Checking state keys...")
        print(f"      medications_list in state: {'medications_list' in state}")
        print(f"      supplements_list in state: {'supplements_list' in state}")
        print(f"      dietary_restrictions_list in state: {'dietary_restrictions_list' in state}")
        
        if 'medications_list' in state:
            print(f"      medications_list value: {state['medications_list']}")
        if 'supplements_list' in state:
            print(f"      supplements_list value: {state['supplements_list']}")
        if 'dietary_restrictions_list' in state:
            print(f"      dietary_restrictions_list value: {state['dietary_restrictions_list']}")

        # Gather inputs 
        dietary_restriction_names = self._get_dietary_restriction_names(state)
        supplement_names = self._get_supplement_names(state)
        medication_names = self._get_medication_names(state)

        print(f"   📋 After gathering:")
        print(f"      dietary_restriction_names: {dietary_restriction_names}")
        print(f"      supplement_names: {supplement_names}")
        print(f"      medication_names: {medication_names}")

        # Early exit if nothing to check
        if not dietary_restriction_names and not supplement_names and not medication_names:
            print("   ⚠️  No dietary restrictions, medications, or supplements to analyze")
            state['deficiency_checked'] = True
            state['deficiency_results'] = {
                'all_at_risk': [],
                'diet_based': [],
                'supplement_based': [],
                'medication_based': [],
                'critical_overlaps': [],
                'total_count': 0,
                'confidence': 0.70,
                'verdict': 'NOTHING_TO_CHECK',
                'queries_run': [],
            }
            return state

        print(f"   Dietary restrictions: {dietary_restriction_names or 'None'}")
        print(f"   Supplements: {supplement_names or 'None'}")
        print(f"   Medications: {medication_names or 'None'}")

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
        
        # PATHWAY 3: Medication-induced deficiencies (NEW!)
        med_deficiencies, med_queries = self._check_medication_deficiencies(
            medication_names
        )
        all_queries.extend(med_queries)

        # Aggregate and detect overlaps
        all_at_risk, critical_overlaps = self._aggregate_deficiencies(
            diet_deficiencies,
            supp_deficiencies,
            med_deficiencies
        )

        # Build final results
        results = self._build_final_results(
            diet_deficiencies,
            supp_deficiencies,
            med_deficiencies,
            all_at_risk,
            critical_overlaps,
            dietary_restriction_names,
            supplement_names,
            medication_names,
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
                f"from {len(dietary_restriction_names)} diet(s), {len(supplement_names)} supplement(s), "
                f"{len(medication_names)} medication(s)"
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

        deficient_nutrients = []
        for d in diet_deficiencies:
            deficient_nutrients.append(d['nutrient'])
        for d in supp_deficiencies:
            deficient_nutrients.append(d['nutrient'])
        for d in med_deficiencies:
            deficient_nutrients.append(d['nutrient'])

        # Deduplicate
        deficient_nutrients = list(set(deficient_nutrients))
        state['deficient_nutrients_list'] = deficient_nutrients

        if deficient_nutrients:
            print(f"   📋 Identified {len(deficient_nutrients)} deficient nutrients: {', '.join(deficient_nutrients)}")

        # Summary
        print(f"\n   ✅ Deficiency Analysis Complete")
        print(f"      Total at-risk nutrients: {results['total_count']}")
        print(f"      Diet-based: {len(diet_deficiencies)}")
        print(f"      Supplement-based: {len(supp_deficiencies)}")
        print(f"      Medication-based: {len(med_deficiencies)}")
        print(f"      🚨 Critical overlaps: {len(critical_overlaps)}")
        print("=" * 70 + "\n")

        return state

    # ==================================================================
    # INPUT GATHERING 
    # ==================================================================
    
    def _get_dietary_restriction_names(self, state: Dict) -> List[str]:
        """
        Get dietary restriction names from supervisor's clean list.
        
        Supervisor handles extraction, normalization, and deduplication.
        Agents simply read from the pre-processed list.
        """
        return state.get('dietary_restrictions_list', [])

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


    # ==================================================================
    # PATHWAY 1: DIET-BASED DEFICIENCIES
    # ==================================================================
    
    def _check_diet_deficiencies(
        self, 
        restrictions: List[str]
    ) -> Tuple[List[Dict], List[Dict]]:
        """
        Query graph for diet-based nutrient deficiencies.
        Uses QueryGenerator for query construction.
        """
        if not restrictions:
            return [], []

        print(f"   🔍 Analyzing {len(restrictions)} dietary restriction(s)...")

        # Use query generator
        query_dict = generate_diet_deficiency_query_dict(restrictions)
        result = self.executor.execute_query_dict(query_dict)

        queries_run = [{
            'query_type': 'diet_deficiency',
            'restrictions': restrictions,
            'cypher': query_dict['query'],
            'parameters': query_dict['parameters'],
            'success': result['success'],
            'result_count': result['count'],
            'execution_time': result.get('execution_time', 0),
        }]

        deficiencies = []
        if result['success'] and result['data']:
            for row in result['data']:
                deficiencies.append({
                    'nutrient': row['nutrient'],
                    'source_type': 'diet',
                    'source_name': row['diet'],
                    'risk_level': row.get('risk_level', 'MEDIUM'),
                    'mechanism': 'dietary_restriction',
                    'evidence': f"{row['diet']} diet is commonly deficient in {row['nutrient']}",
                    'confidence': 0.90,
                    'nutrient_category': row.get('nutrient_category', ''),
                    'rda': row.get('rda', '')
                })
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
        Uses QueryGenerator for query construction.
        """
        if not supplements:
            return [], []

        print(f"   🔍 Analyzing {len(supplements)} supplement(s)...")

        # Use query generator
        query_dict = generate_supplement_depletion_query_dict(supplements)
        result = self.executor.execute_query_dict(query_dict)

        queries_run = [{
            'query_type': 'supplement_depletion',
            'supplements': supplements,
            'cypher': query_dict['query'],
            'parameters': query_dict['parameters'],
            'success': result['success'],
            'result_count': result['count'],
            'execution_time': result.get('execution_time', 0),
        }]

        deficiencies = []
        if result['success'] and result['data']:
            for row in result['data']:
                deficiencies.append({
                    'nutrient': row['nutrient'],
                    'source_type': 'supplement',
                    'source_name': row['supplement'],
                    'risk_level': row['severity'],
                    'mechanism': row['mechanism'],
                    'evidence': row.get('notes', ''),
                    'confidence': 0.95
                })
                print(f"      ✅ Found: {row['supplement']} → {row['nutrient']} ({row['severity']})")
        else:
            print(f"      ⊘  No deficiencies found")

        return deficiencies, queries_run

    # ==================================================================
    # PATHWAY 3: MEDICATION-INDUCED DEFICIENCIES (GRAPH-BASED)
    # ==================================================================
    
    def _check_medication_deficiencies(
        self,
        medications: List[str]
    ) -> Tuple[List[Dict], List[Dict]]:
        """
        Query graph for medication-nutrient interactions.
        Uses QueryGenerator for query construction - NO LLM needed!
        
        Returns:
            (deficiencies, queries_run)
        """
        if not medications:
            return [], []

        print(f"   🔍 Analyzing {len(medications)} medication(s)...")

        # Use query generator
        query_dict = generate_medication_nutrient_depletion_query_dict(medications)
        result = self.executor.execute_query_dict(query_dict)

        queries_run = [{
            'query_type': 'medication_nutrient_depletion',
            'medications': medications,
            'cypher': query_dict['query'],
            'parameters': query_dict['parameters'],
            'success': result['success'],
            'result_count': result['count'],
            'execution_time': result.get('execution_time', 0),
        }]

        deficiencies = []
        if result['success'] and result['data']:
            for row in result['data']:
                interaction_type = row['interaction_type']
                
                # Map interaction_type to risk_level
                if interaction_type == 'depletes':
                    risk_level = 'HIGH'
                    mechanism = 'depletes'
                elif interaction_type == 'interferes_with_absorption':
                    risk_level = 'MODERATE'
                    mechanism = 'interferes_with_absorption'
                elif interaction_type == 'increases_level':
                    risk_level = 'MODERATE'
                    mechanism = 'increases_level'
                elif interaction_type == 'redistributes':
                    risk_level = 'LOW'
                    mechanism = 'redistributes'
                elif interaction_type == 'may_cause_loss':
                    risk_level = 'MODERATE'
                    mechanism = 'may_cause_loss'
                elif interaction_type == 'antagonizes':
                    risk_level = 'HIGH'
                    mechanism = 'antagonizes'
                else:
                    risk_level = 'MEDIUM'
                    mechanism = interaction_type
                
                deficiencies.append({
                    'nutrient': row['nutrient'],
                    'source_type': 'medication',
                    'source_name': row['medication'],
                    'risk_level': risk_level,
                    'mechanism': mechanism,
                    'evidence': f"{row['medication']} {interaction_type} {row['nutrient']}",
                    'confidence': 0.95  # High confidence - from curated database
                })
                print(f"      ✅ Found: {row['medication']} → {row['nutrient']} ({interaction_type})")
        else:
            print(f"      ⊘  No deficiencies found")

        return deficiencies, queries_run

    # ==================================================================
    # AGGREGATION & OVERLAP DETECTION
    # ==================================================================
    
    def _aggregate_deficiencies(
        self,
        diet_def: List[Dict],
        supp_def: List[Dict],
        med_def: List[Dict]
    ) -> Tuple[Dict[str, List[Dict]], List[Dict]]:
        """
        Aggregate all deficiencies and detect critical overlaps.
        
        Returns:
            (all_at_risk, critical_overlaps)
        """
        all_at_risk = {}  # nutrient -> list of sources

        # Aggregate from all pathways
        for deficiency in diet_def + supp_def + med_def:
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
                source_names = [s['source_name'] for s in sources]
                highest_risk = self._get_highest_risk(sources)
                
                # Classify overlap type
                source_types = {s['source_type'] for s in sources}
                if len(source_types) == 3:
                    overlap_type = 'TRIPLE_OVERLAP'
                elif len(source_types) == 2:
                    overlap_type = 'DOUBLE_OVERLAP'
                else:
                    overlap_type = 'SINGLE_SOURCE_MULTIPLE'
                
                critical_overlaps.append({
                    'nutrient': nutrient,
                    'sources': sources,
                    'source_names': source_names,
                    'overlap_type': overlap_type,
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
        med_def: List[Dict],
        all_at_risk: Dict[str, List[Dict]],
        critical_overlaps: List[Dict],
        dietary_restrictions: List[str],
        supplements: List[str],
        medications: List[str],
        queries_run: List[Dict]
    ) -> Dict[str, Any]:
        """Build comprehensive results structure for state."""
        
        # Count by risk level
        all_deficiencies = diet_def + supp_def + med_def
        high_risk_count = sum(1 for d in all_deficiencies if d['risk_level'] in ['HIGH', 'CRITICAL'])
        critical_count = len(critical_overlaps)

        # Calculate confidence
        if all_deficiencies:
            avg_confidence = sum(d['confidence'] for d in all_deficiencies) / len(all_deficiencies)
            if critical_overlaps:
                avg_confidence = min(0.95, avg_confidence + 0.05)
            confidence = round(avg_confidence, 2)
        else:
            confidence = 0.70

        return {
            # Individual pathways
            'diet_based': diet_def,
            'supplement_based': supp_def,
            'medication_based': med_def,
            
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
            'medication_count': len(med_def),
            'critical_count': critical_count,
            'high_risk_count': high_risk_count,
            
            # Context
            'restrictions_checked': dietary_restrictions,
            'supplements_checked': supplements,
            'medications_checked': medications,
            
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