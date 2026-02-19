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
        from tools.query_executor import QueryExecutor
        
        self.executor = QueryExecutor(graph_interface)
    
    
    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate supplement recommendations (NO safety filtering).
        Safety agent will check interactions separately.
        """
        print("\n" + "="*60)
        print("💊 RECOMMENDATION AGENT: Finding candidates...")
        print("="*60)
        
        # 1. Extract condition/symptom from state
        condition = self._extract_condition(state)
        
        if not condition:
            print("⚠️  No condition/symptom specified")
            state['recommendations_checked'] = True
            state['recommendation_results'] = {
                'candidates': [],
                'verdict': 'NO_CONDITION',
                'reason': 'No condition or symptom to address'
            }
            return state
        
        print(f"   Condition/Symptom: {condition}")
        
        # 2. Find recommendations (NO safety filtering)
        recommendations = self._generate_recommendations(condition)
        
        # ✨ NEW: Add ALL recommendations to supplements_list for safety agent
        if recommendations:
            supplement_names = [rec['supplement_name'] for rec in recommendations]
            current_supplements = state.get('supplements_list', [])
            # Combine and deduplicate
            updated_supplements = list(set(current_supplements + supplement_names))
            state['supplements_list'] = updated_supplements
            
            print(f"\n   ✨ Added {len(supplement_names)} supplements to state for safety verification")
            print(f"      Candidates: {', '.join(supplement_names[:3])}{'...' if len(supplement_names) > 3 else ''}")
        
        # 3. Compile results (no safety info - that comes from safety agent)
        results = {
            'condition': condition,
            'candidates': recommendations,  # ALL candidates (not pre-filtered)
            'candidate_count': len(recommendations),
            'confidence': self._calculate_confidence_simple(recommendations)
        }
        
        state['recommendations_checked'] = True
        state['recommendation_results'] = results
        
        # Update evidence chain
        evidence = state.get('evidence_chain', [])
        evidence.append(
            f"Recommendation check: Found {len(recommendations)} candidates for {condition}"
        )
        state['evidence_chain'] = evidence
        
        print(f"   ✓ Found {len(recommendations)} candidate supplements")
        print("="*60 + "\n")
        
        return state
    
    
    def _generate_recommendations(self, condition: str) -> List[Dict]:
        """
        Generate supplement recommendations (NO safety filtering).
        Just finds supplements that help the condition.
        """
        # Step 1: Find supplements that help the condition
        print(f"\n   🔍 Finding supplements for: {condition}")
        candidates = self._find_supplements_for_condition(condition)
        print(f"   Found {len(candidates)} candidate supplements")
        
        if not candidates:
            return []
        
        # Step 2: Rank by safety rating (no interaction checking)
        print(f"\n   📊 Ranking by safety rating...")
        ranked = self._rank_by_safety_rating(candidates)
        
        return ranked
        
    
    
    def _find_supplements_for_condition(self, condition: str) -> List[Dict]:
        """
        Find supplements that help with condition/symptom.
        
        Uses direct Cypher that matches our actual DB schema:
        - Symptom node has: symptom_id, symptom_name
        - Relationship: Supplement -[:TREATS]-> Symptom
        """
        # Direct Cypher query against actual schema
        candidates = self._manual_symptom_search(condition)
        
        if candidates:
            print(f"   ✓ Found {len(candidates)} candidate supplements")
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
    
    
    def _rank_by_safety_rating(self, supplements: List[Dict]) -> List[Dict]:
        """
        Rank supplements by safety rating only (no interaction checking).
        Safety agent will handle medication interactions.
        """
        # Use actual safety ratings from database
        safety_rating_scores = {
            'Generally safe': 3,      # Most supplements
            'Use with caution': 2,    # Some supplements
            'Not recommended': 1,     # Few supplements
            'UNKNOWN': 0              # No rating in database
        }
        
        def rank_key(supp):
            return (
                safety_rating_scores.get(supp.get('safety_rating', 'UNKNOWN'), 0),  # By safety rating
                supp.get('supplement_name', '')  # Then alphabetically
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
        """
        Get medication names from supervisor's clean list.
        
        Supervisor handles extraction, normalization, and deduplication.
        Agents simply read from the pre-processed list.
        """
        return state.get('medications_list', [])
    
    
    def _calculate_confidence_simple(self, recommendations: List[Dict]) -> float:
        """
        Calculate confidence based on safety ratings and variety (no interaction checking).
        """
        if not recommendations:
            return 0.3
        
        # Count by safety rating
        generally_safe = sum(1 for r in recommendations 
                            if r.get('safety_rating') == 'Generally safe')
        use_caution = sum(1 for r in recommendations 
                         if r.get('safety_rating') == 'Use with caution')
        
        base_confidence = 0.5
        
        # Bonus for "Generally safe" supplements
        safety_bonus = min(0.3, generally_safe * 0.1)
        
        # Small bonus for "Use with caution"
        caution_bonus = min(0.1, use_caution * 0.03)
        
        # Bonus for variety (having multiple options)
        variety_bonus = min(0.2, len(recommendations) * 0.02)
        
        final_confidence = min(1.0, base_confidence + safety_bonus + caution_bonus + variety_bonus)
        
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