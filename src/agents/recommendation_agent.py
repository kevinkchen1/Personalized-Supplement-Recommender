"""
Recommendation Agent - FIXED for Knowledge Graph
Finds safe supplement recommendations for conditions/symptoms.
"""
from typing import Dict, Any, List
import os


class RecommendationAgent:
    """
    Specialist agent for supplement recommendations
    """
    
    def __init__(self, graph_interface):
        self.graph = graph_interface
        from tools.query_generator import QueryGenerator
        from tools.query_executor import QueryExecutor
        
        self.generator = QueryGenerator()
        self.executor = QueryExecutor(graph_interface)
    
    
    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Generate supplement recommendations"""
        print("\n" + "="*60)
        print("💊 RECOMMENDATION AGENT: Finding safe options...")
        print("="*60)
        
        # 1. Extract condition/symptom from state
        condition = self._extract_condition(state)
        medications = self._get_medication_names(state)
        
        if not condition:
            print("⚠️  No condition/symptom specified")
            state['recommendations_checked'] = True
            state['recommendation_results'] = {
                'recommendations': [],
                'verdict': 'NO_CONDITION',
                'reason': 'No condition or symptom to address'
            }
            return state
        
        print(f"   Condition/Symptom: {condition}")
        print(f"   Filtering against: {len(medications)} medications")
        
        # 2. Find and filter recommendations
        recommendations = self._generate_recommendations(condition, medications)
        
        # 3. Compile results
        results = {
            'condition': condition,
            'recommendations': recommendations,
            'safe_count': len([r for r in recommendations if r['safe']]),
            'unsafe_count': len([r for r in recommendations if not r['safe']]),
            'total_candidates': len(recommendations),
            'medications_checked': medications,
            'confidence': self._calculate_confidence(recommendations)
        }
        
        state['recommendations_checked'] = True
        state['recommendation_results'] = results
        
        # Update evidence chain
        evidence = state.get('evidence_chain', [])
        evidence.append(
            f"Recommendation check: Found {results['safe_count']} safe options "
            f"for {condition} (filtered {results['unsafe_count']} unsafe)"
        )
        state['evidence_chain'] = evidence
        
        print(f"   ✓ Found {results['safe_count']} safe options")
        print(f"   ✗ Filtered {results['unsafe_count']} unsafe options")
        print("="*60 + "\n")
        
        return state
    
    
    def _generate_recommendations(self, condition: str, medications: List[str]) -> List[Dict]:
        """Generate filtered supplement recommendations"""
        # Step 1: Find supplements that help the condition
        print(f"\n   🔍 Finding supplements for: {condition}")
        candidates = self._find_supplements_for_condition(condition)
        print(f"   Found {len(candidates)} candidate supplements")
        
        if not candidates:
            return []
        
        # Step 2: Check safety for each candidate
        print(f"\n   🛡️  Checking safety against {len(medications)} medications...")
        evaluated = self._evaluate_safety(candidates, medications)
        
        # Step 3: Rank by evidence strength
        print(f"\n   📊 Ranking by evidence strength...")
        ranked = self._rank_by_evidence(evaluated)
        
        return ranked
    
    
    def _find_supplements_for_condition(self, condition: str) -> List[Dict]:
        """
        Find supplements that help with condition/symptom
        
        FIXED: Uses direct Cypher query that matches your actual schema:
        - Symptom node has: symptom_id, symptom_name
        - Relationship: Supplement -[:TREATS]-> Symptom
        """
        # OPTION 1: Try using QueryGenerator first
        query_dict = self.generator.generate_query(
            'supplements_for_symptom',
            {'symptom': condition}
        )
        
        if not query_dict.get('error'):
            result = self.executor.execute_query_dict(query_dict)
            
            if result['success'] and result['data']:
                print(f"   ✓ QueryGenerator worked! Found {len(result['data'])} results")
                return self._format_candidates(result['data'])
        
        # OPTION 2: Fallback to manual Cypher query
        print(f"   ⚠️  QueryGenerator returned 0 results, trying manual query...")
        candidates = self._manual_symptom_search(condition)
        
        if candidates:
            print(f"   ✓ Manual query worked! Found {len(candidates)} results")
        else:
            print(f"   ❌ No supplements found for: {condition}")
        
        return candidates
    
    
    def _manual_symptom_search(self, condition: str) -> List[Dict]:
        """
        Manual Cypher query that matches your actual schema
        
        Knowledge graph structure:
        - Supplement nodes: supplement_id, supplement_name, safety_rating
        - Symptom nodes: symptom_id, symptom_name
        - Relationship: (Supplement)-[:TREATS]->(Symptom)
        """
        # Clean up the condition for matching
        condition_clean = condition.lower().strip()
        
        # Build a flexible Cypher query
        cypher = """
        MATCH (s:Supplement)-[r:TREATS]->(sym:Symptom)
        WHERE toLower(sym.symptom_name) CONTAINS $condition_lower
        RETURN DISTINCT
            s.supplement_id AS supplement_id,
            s.supplement_name AS supplement,
            s.safety_rating AS safety_rating,
            sym.symptom_name AS symptom,
            'TREATS' AS relationship_type
        ORDER BY s.supplement_name
        """
        
        params = {'condition_lower': condition_clean}
        
        try:
            result = self.executor.execute(cypher, params)
            
            if result['success'] and result['data']:
                return self._format_candidates(result['data'])
            else:
                # Try even broader search if nothing found
                print(f"   Trying broader search...")
                return self._broad_symptom_search(condition)
        
        except Exception as e:
            print(f"   ❌ Query error: {e}")
            return []
    
    
    def _broad_symptom_search(self, condition: str) -> List[Dict]:
        """
        Very broad search - returns all supplements and lets user decide
        Only used as last resort when specific search fails
        """
        # Split condition into words for matching
        words = [w.strip().lower() for w in condition.split() if len(w) > 3]
        
        if not words:
            return []
        
        # Search for any word match
        cypher = """
        MATCH (s:Supplement)-[r:TREATS]->(sym:Symptom)
        WHERE ANY(word IN $words WHERE toLower(sym.symptom_name) CONTAINS word)
        RETURN DISTINCT
            s.supplement_id AS supplement_id,
            s.supplement_name AS supplement,
            s.safety_rating AS safety_rating,
            sym.symptom_name AS symptom,
            'TREATS' AS relationship_type
        ORDER BY s.supplement_name
        LIMIT 10
        """
        
        params = {'words': words}
        
        try:
            result = self.executor.execute(cypher, params)
            
            if result['success']:
                print(f"   Found {result['count']} supplements with broad search")
                return self._format_candidates(result['data'])
        except Exception as e:
            print(f"   ❌ Broad search error: {e}")
        
        return []
    
    
    def _format_candidates(self, raw_data: List[Dict]) -> List[Dict]:
        """
        Format raw Cypher results into standardized candidate format
        
        Handles different column names from different queries
        """
        seen = set()
        candidates = []
        
        for row in raw_data:
            # Handle different possible column names
            name = (row.get('supplement') or 
                   row.get('supplement_name') or 
                   row.get('s.supplement_name'))
            
            if not name or name in seen:
                continue
            
            seen.add(name)
            
            candidates.append({
                'supplement_id': (row.get('supplement_id') or 
                                 row.get('s.supplement_id')),
                'supplement_name': name,
                'symptom_treated': (row.get('symptom') or 
                                   row.get('symptom_name') or 
                                   row.get('sym.symptom_name')),
                'safety_rating': (row.get('safety_rating') or 
                                 row.get('s.safety_rating') or 
                                 'UNKNOWN'),
                'relationship_type': (row.get('relationship_type') or 
                                     row.get('type(r)') or 
                                     'TREATS')
            })
        
        return candidates
    
    
    def _evaluate_safety(self, candidates: List[Dict], medications: List[str]) -> List[Dict]:
        """Check safety of each candidate supplement against user's medications"""
        if not medications:
            # No medications to check against - all are safe
            for candidate in candidates:
                candidate['safe'] = True
                candidate['interactions'] = []
                candidate['safety_verdict'] = 'SAFE - No medications to check against'
            return candidates
        
        evaluated = []
        
        for candidate in candidates:
            supplement_name = candidate['supplement_name']
            
            # Run comprehensive safety check
            from tools.query_generator import generate_comprehensive_safety_query
            
            query_dict = generate_comprehensive_safety_query(
                supplement_name,
                medications
            )
            
            if query_dict.get('error'):
                candidate['safe'] = False
                candidate['interactions'] = []
                candidate['safety_verdict'] = 'UNKNOWN - Could not check'
                candidate['error'] = query_dict['error']
                evaluated.append(candidate)
                continue
            
            result = self.executor.execute_query_dict(query_dict)
            
            # Evaluate results
            if result['success']:
                interactions = result['data']
                
                if len(interactions) == 0:
                    candidate['safe'] = True
                    candidate['interactions'] = []
                    candidate['safety_verdict'] = 'SAFE - No interactions found'
                else:
                    candidate['safe'] = False
                    candidate['interactions'] = interactions
                    candidate['safety_verdict'] = self._format_safety_verdict(interactions)
                    candidate['interaction_count'] = len(interactions)
            else:
                candidate['safe'] = False
                candidate['interactions'] = []
                candidate['safety_verdict'] = 'UNKNOWN - Query failed'
                candidate['error'] = result.get('error')
            
            evaluated.append(candidate)
        
        return evaluated
    
    
    def _format_safety_verdict(self, interactions: List[Dict]) -> str:
        """Format a human-readable safety verdict from interactions"""
        severities = [ix.get('severity', 'UNKNOWN') for ix in interactions]
        
        high_risk = sum(1 for s in severities if s == 'HIGH')
        medium_risk = sum(1 for s in severities if s == 'MEDIUM')
        
        verdict = f"CAUTION - {len(interactions)} interaction(s) found"
        
        if high_risk > 0:
            verdict += f" ({high_risk} HIGH RISK)"
        elif medium_risk > 0:
            verdict += f" ({medium_risk} MEDIUM RISK)"
        
        return verdict
    
    
    def _rank_by_evidence(self, supplements: List[Dict]) -> List[Dict]:
        """Rank supplements by evidence strength and safety"""
        safety_rating_scores = {
            'A': 3,
            'B': 2,
            'C': 1,
            'UNKNOWN': 0
        }
        
        def rank_key(supp):
            return (
                1 if supp.get('safe') else 0,
                safety_rating_scores.get(supp.get('safety_rating', 'UNKNOWN'), 0),
                supp.get('supplement_name', '')
            )
        
        ranked = sorted(supplements, key=rank_key, reverse=True)
        
        for i, supp in enumerate(ranked):
            supp['rank'] = i + 1
        
        return ranked
    
    
    def _extract_condition(self, state: Dict[str, Any]) -> str:
        """Extract condition/symptom from state"""
        # Source 1: Normalized entities
        normalized = state.get('normalized_entities') or {}
        for key in ('conditions', 'symptoms'):
            items = normalized.get(key, [])
            if items:
                return items[0] if isinstance(items[0], str) else items[0].get('symptom_name', items[0].get('condition'))
        
        # Source 2: Extracted entities
        extracted = state.get('extracted_entities') or {}
        for key in ('conditions', 'symptoms'):
            items = extracted.get(key, [])
            if items:
                return items[0]
        
        # Source 3: Patient profile conditions
        profile = state.get('patient_profile') or {}
        conditions = profile.get('conditions', [])
        if conditions:
            return conditions[0]
        
        # Source 4: Parse user question
        user_query = state.get('user_question', '')
        symptom_keywords = self._extract_symptom_from_query(user_query)
        if symptom_keywords:
            return symptom_keywords
        
        return None
    
    
    def _extract_symptom_from_query(self, query: str) -> str:
        """Extract symptom from natural language query"""
        import re
        
        patterns = [
            r'supplements?\s+(?:for|that help(?: with)?)\s+([a-zA-Z\s]+?)(?:\?|$)',
            r'support\s+([a-zA-Z\s]+?)(?:\?|$)',
            r'help\s+(?:with|for)\s+([a-zA-Z\s]+?)(?:\?|$)',
            r'good\s+for\s+([a-zA-Z\s]+?)(?:\?|$)',
            r'treat\s+([a-zA-Z\s]+?)(?:\?|$)',
            r'recommend.*for\s+([a-zA-Z\s]+?)(?:\?|$)',
            r'for\s+(?:my\s+)?([a-zA-Z\s]+?)(?:\?|$)',
        ]
        
        query_lower = query.lower()
        stop_words = {'me', 'my', 'the', 'a', 'an', 'that', 'this', 'it', 'i', 'you'}
        
        for pattern in patterns:
            match = re.search(pattern, query_lower)
            if match:
                symptom = match.group(1).strip().rstrip('.')
                if symptom and symptom not in stop_words:
                    return symptom
        
        return ''
    
    
    def _get_medication_names(self, state: Dict[str, Any]) -> List[str]:
        """Get medication names from state — merges ALL sources."""
        names = set()
        
        # Source 1: Normalized medications
        for m in (state.get('normalized_medications') or []):
            if isinstance(m, dict):
                name = m.get('matched_drug') or m.get('user_input')
            else:
                name = str(m)
            if name:
                names.add(name)
        
        # Source 2: Extracted entities
        extracted = state.get('extracted_entities') or {}
        for name in (extracted.get('medications') or []):
            if name:
                names.add(name)
        
        # Source 3: Patient profile (always checked)
        profile_meds = (state.get('patient_profile') or {}).get('medications', [])
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
    
    
    def _calculate_confidence(self, recommendations: List[Dict]) -> float:
        """Calculate confidence in recommendations"""
        if not recommendations:
            return 0.3
        
        safe_count = sum(1 for r in recommendations if r.get('safe'))
        total = len(recommendations)
        
        base_confidence = 0.5 + (safe_count / total * 0.3)
        
        a_ratings = sum(1 for r in recommendations if r.get('safety_rating') == 'A')
        evidence_bonus = min(0.2, a_ratings * 0.05)
        
        errors = sum(1 for r in recommendations if 'error' in r)
        if errors > 0:
            base_confidence -= 0.1
        
        final_confidence = min(1.0, base_confidence + evidence_bonus)
        
        return round(final_confidence, 2)


# Standalone function for LangGraph
def recommendation_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    """Wrapper for LangGraph integration"""
    from graph.graph_interface import GraphInterface
    
    graph = state.get('graph_interface')
    if graph is None:
        graph = GraphInterface(
            uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            user=os.getenv("NEO4J_USER", "neo4j"),
            password=os.getenv("NEO4J_PASSWORD", ""),
        )
    
    agent = RecommendationAgent(graph)
    return agent.run(state)