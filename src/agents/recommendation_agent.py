"""
Recommendation Agent - Supplement Advisor
Finds safe supplement recommendations for conditions/symptoms:
- Finds supplements that help the condition
- Filters out ones that interact with user's medications
- Ranks by evidence strength
Role: Recommendation specialist
"""
from typing import Dict, Any, List
import os


class RecommendationAgent:
    """
    Specialist agent for supplement recommendations
    """
    
    def __init__(self, graph_interface):
        self.graph = graph_interface
        # Import query tools
        from tools.query_generator import QueryGenerator
        from tools.query_executor import QueryExecutor
        
        self.generator = QueryGenerator()
        self.executor = QueryExecutor(graph_interface)
    
    
    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate supplement recommendations
        
        Args:
            state: Current conversation state
            
        Returns:
            Updated state with recommendations
        """
        print("\n" + "="*60)
        print("💊 RECOMMENDATION AGENT: Finding safe options...")
        print("="*60)
        
        # ----------------------------------------------------------
        # 1. Extract condition/symptom from state
        # ----------------------------------------------------------
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
        
        # ----------------------------------------------------------
        # 2. Find and filter recommendations
        # ----------------------------------------------------------
        recommendations = self._generate_recommendations(condition, medications)
        
        # ----------------------------------------------------------
        # 3. Compile results
        # ----------------------------------------------------------
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
        """
        Generate filtered supplement recommendations
        
        Args:
            condition: Health condition/symptom to address
            medications: User's medications
            
        Returns:
            List of supplement recommendations with safety info
        """
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
        
        Uses query: MATCH (s:Supplement)-[:TREATS]->(sym:Symptom)
        WHERE sym.description CONTAINS condition
        
        Args:
            condition: Health condition or symptom
            
        Returns:
            List of supplement candidates with basic info
        """
        # Generate query using QueryGenerator
        # FIX: param key is 'symptom' (what QueryGenerator expects), not 'symptom_name'
        query_dict = self.generator.generate_query(
            'supplements_for_symptom',
            {'symptom': condition}
        )
        
        if query_dict.get('error'):
            print(f"   ❌ Query generation error: {query_dict['error']}")
            return []
        
        # Execute query
        result = self.executor.execute_query_dict(query_dict)
        
        if not result['success']:
            print(f"   ❌ Query execution failed: {result.get('error')}")
            return []
        
        # Format results
        # FIX: column names match the actual Cypher RETURN clause:
        #   'supplement' (not 'supplement_name'), 'symptom' (not 'symptom_name')
        seen = set()
        candidates = []
        for row in result['data']:
            name = row.get('supplement', '')
            if not name or name in seen:
                continue
            seen.add(name)
            candidates.append({
                'supplement_id': row.get('supplement_id'),
                'supplement_name': name,
                'symptom_treated': row.get('symptom'),
                'safety_rating': row.get('safety_rating', 'UNKNOWN'),
                'relationship_type': row.get('relationship_type', 'TREATS')
            })
        
        return candidates
    
    
    def _evaluate_safety(self, candidates: List[Dict], medications: List[str]) -> List[Dict]:
        """
        Check safety of each candidate supplement against user's medications
        
        Args:
            candidates: List of supplement candidates
            medications: User's medications
            
        Returns:
            List of candidates with safety evaluation added
        """
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
                    # No interactions found - SAFE
                    candidate['safe'] = True
                    candidate['interactions'] = []
                    candidate['safety_verdict'] = 'SAFE - No interactions found'
                else:
                    # Interactions found - UNSAFE
                    candidate['safe'] = False
                    candidate['interactions'] = interactions
                    candidate['safety_verdict'] = self._format_safety_verdict(interactions)
                    candidate['interaction_count'] = len(interactions)
            else:
                # Query failed - mark as unknown
                candidate['safe'] = False
                candidate['interactions'] = []
                candidate['safety_verdict'] = 'UNKNOWN - Query failed'
                candidate['error'] = result.get('error')
            
            evaluated.append(candidate)
        
        return evaluated
    
    
    def _format_safety_verdict(self, interactions: List[Dict]) -> str:
        """
        Format a human-readable safety verdict from interactions
        
        Args:
            interactions: List of interaction records
            
        Returns:
            Safety verdict string
        """
        pathways = set(ix.get('pathway', 'UNKNOWN') for ix in interactions)
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
        """
        Rank supplements by evidence strength and safety
        
        Ranking criteria (in order):
        1. Safety (safe supplements first)
        2. Safety rating from database (A > B > C)
        3. Number of symptoms treated (more versatile = better)
        4. Alphabetical (tiebreaker)
        
        Args:
            supplements: List of evaluated supplements
            
        Returns:
            Ranked list
        """
        # Define safety rating scores
        safety_rating_scores = {
            'A': 3,  # High quality evidence
            'B': 2,  # Moderate quality evidence
            'C': 1,  # Low quality evidence
            'UNKNOWN': 0
        }
        
        def rank_key(supp):
            return (
                1 if supp.get('safe') else 0,  # Safe first
                safety_rating_scores.get(supp.get('safety_rating', 'UNKNOWN'), 0),
                supp.get('supplement_name', '')
            )
        
        # Sort in descending order (higher = better)
        ranked = sorted(supplements, key=rank_key, reverse=True)
        
        # Add rank position
        for i, supp in enumerate(ranked):
            supp['rank'] = i + 1
        
        return ranked
    
    
    def _extract_condition(self, state: Dict[str, Any]) -> str:
        """
        Extract condition/symptom from state
        
        Tries multiple sources:
        1. normalized_entities.conditions or .symptoms
        2. extracted_entities.conditions or .symptoms
        3. patient_profile.conditions
        4. user_question (parse for symptom keywords)
        
        Args:
            state: Current conversation state
            
        Returns:
            Condition/symptom string or None
        """
        # Source 1: Normalized entities
        # FIX: use `or {}` to handle explicit None values in state
        # FIX: check both 'conditions' AND 'symptoms' (entity extractor returns 'conditions')
        normalized = state.get('normalized_entities') or {}
        for key in ('conditions', 'symptoms'):
            items = normalized.get(key, [])
            if items:
                return items[0] if isinstance(items[0], str) else items[0].get('symptom_name')
        
        # Source 2: Extracted entities
        # FIX: use `or {}` and check both 'conditions' and 'symptoms'
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
        
        # Source 4: Parse user question for symptom keywords
        # FIX: state key is 'user_question', not 'user_query'
        user_query = state.get('user_question', '')
        symptom_keywords = self._extract_symptom_from_query(user_query)
        if symptom_keywords:
            return symptom_keywords
        
        return None
    
    
    def _extract_symptom_from_query(self, query: str) -> str:
        """
        Extract symptom from natural language query
        
        Looks for patterns like:
        - "help with [symptom]"
        - "for [symptom]"
        - "treat [symptom]"
        - "support [condition]"
        - "supplements for [condition]"
        
        Args:
            query: User's natural language query
            
        Returns:
            Extracted symptom or empty string
        """
        import re
        
        # FIX: added patterns for 'support X', 'good for X', 'supplements for X'
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
                # Filter out common words
                if symptom and symptom not in stop_words:
                    return symptom
        
        return ''
    
    
    def _get_medication_names(self, state: Dict[str, Any]) -> List[str]:
        """
        Get medication names from state
        
        Tries multiple sources:
        1. normalized_medications
        2. extracted_entities.medications
        3. patient_profile.medications
        
        Args:
            state: Current conversation state
            
        Returns:
            List of medication names
        """
        names = []
        
        # Source 1: Normalized medications
        # FIX: handle both dict and str formats
        for m in state.get('normalized_medications', []):
            if isinstance(m, dict):
                name = m.get('matched_drug') or m.get('user_input')
            else:
                name = str(m)
            if name:
                names.append(name)
        
        # Source 2: Extracted entities
        if not names:
            extracted = state.get('extracted_entities') or {}
            names = extracted.get('medications', [])
        
        # Source 3: Patient profile
        if not names:
            profile_meds = (state.get('patient_profile') or {}).get('medications', [])
            for m in profile_meds:
                if isinstance(m, dict):
                    names.append(m.get('drug_name') or m.get('matched_drug') or m.get('user_input', ''))
                elif isinstance(m, str):
                    names.append(m)
        
        return [n for n in names if n]
    
    
    def _calculate_confidence(self, recommendations: List[Dict]) -> float:
        """
        Calculate confidence in recommendations
        
        Factors:
        - Number of safe options found (more = higher confidence)
        - Safety rating quality (A ratings = higher confidence)
        - Query success (all queries successful = higher confidence)
        
        Args:
            recommendations: List of recommendations
            
        Returns:
            Confidence score (0.0 to 1.0)
        """
        if not recommendations:
            return 0.3  # Low confidence - nothing found
        
        safe_count = sum(1 for r in recommendations if r.get('safe'))
        total = len(recommendations)
        
        # Base confidence on percentage of safe options
        base_confidence = 0.5 + (safe_count / total * 0.3)
        
        # Bonus for high-quality evidence (A ratings)
        a_ratings = sum(1 for r in recommendations if r.get('safety_rating') == 'A')
        evidence_bonus = min(0.2, a_ratings * 0.05)
        
        # Check if any queries failed
        errors = sum(1 for r in recommendations if 'error' in r)
        if errors > 0:
            base_confidence -= 0.1
        
        final_confidence = min(1.0, base_confidence + evidence_bonus)
        
        return round(final_confidence, 2)


# ======================================================================
# Standalone function for LangGraph
# ======================================================================

def recommendation_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    """Wrapper for LangGraph integration"""
    from graph.graph_interface import GraphInterface
    
    # Use existing graph_interface from state, or create new one
    graph = state.get('graph_interface')
    if graph is None:
        graph = GraphInterface(
            uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            user=os.getenv("NEO4J_USER", "neo4j"),
            password=os.getenv("NEO4J_PASSWORD", ""),
        )
    
    agent = RecommendationAgent(graph)
    return agent.run(state)
