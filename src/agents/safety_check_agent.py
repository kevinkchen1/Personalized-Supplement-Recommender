"""
Safety Check Agent - Interaction Specialist

Checks for dangerous interactions between supplements and medications:
- Direct drug-supplement interactions
- Similar pharmacological effects (both increase bleeding)
- Shared metabolism pathways (CYP450 enzymes)

Role: Safety specialist
"""

from typing import Dict, Any
import os


class SafetyCheckAgent:
    """
    Specialist agent for checking supplement-medication interactions
    """
    
    def __init__(self, graph_interface):
        self.graph = graph_interface
    
    
    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Check safety of supplement with user's medications
        
        Args:
            state: Current conversation state
            
        Returns:
            Updated state with safety results
        """
        print("\n" + "="*60)
        print("🔬 SAFETY AGENT: Checking interactions...")
        print("="*60)
        
        # Get normalized entities from state
        normalized = state.get('normalized_entities', {})
        profile = state.get('patient_profile', {})
        
        # Get supplement to check
        new_supplements = normalized.get('supplements', [])
        if not new_supplements:
            print("⚠️  No supplements to check")
            state['safety_checked'] = True
            state['safety_results'] = {'safe': True, 'reason': 'No supplements to check'}
            return state
        
        supplement = new_supplements[0]  # Check first supplement
        medications = profile.get('medications', [])
        
        print(f"   Checking: {supplement.get('matched_supplement', supplement.get('user_input'))}")
        print(f"   Against: {len(medications)} medications")
        
        # Perform safety checks
        interactions = self._check_all_interactions(supplement, medications)
        
        # Evaluate safety
        safe = len(interactions) == 0
        confidence = self._calculate_confidence(interactions)
        
        results = {
            'safe': safe,
            'interactions': interactions,
            'confidence': confidence,
            'supplement_checked': supplement.get('matched_supplement'),
            'verdict': 'SAFE' if safe else 'CAUTION ADVISED'
        }
        
        state['safety_checked'] = True
        state['safety_results'] = results
        state['confidence_level'] = confidence
        
        print(f"   ✓ Safety Check Complete: {results['verdict']} (confidence: {confidence:.2f})")
        print("="*60 + "\n")
        
        return state
    
    
    def _check_all_interactions(self, supplement: Dict, medications: list) -> list:
        """
        Check all types of interactions
        
        Args:
            supplement: Normalized supplement dict
            medications: List of normalized medication dicts
            
        Returns:
            List of interactions found
        """
        interactions = []
        
        # TODO: Implement using query_generator and query_executor
        
        # Check 1: Direct interactions
        # Query: MATCH (s:Supplement)-[:INTERACTS_WITH]->(d:Drug)
        direct = self._check_direct_interactions(supplement, medications)
        interactions.extend(direct)
        
        # Check 2: Similar pharmacological effects
        # Query: Find supplements and drugs with same effects (bleeding, sedation, etc.)
        effects = self._check_similar_effects(supplement, medications)
        interactions.extend(effects)
        
        # Check 3: Shared metabolism pathways
        # Query: Find shared CYP450 enzymes
        metabolism = self._check_shared_metabolism(supplement, medications)
        interactions.extend(metabolism)
        
        return interactions
    
    
    def _check_direct_interactions(self, supplement: Dict, medications: list) -> list:
        """
        Check for direct drug-supplement interactions in database
        
        Returns:
            List of direct interactions
        """
        # TODO: Implement with actual Cypher query
        interactions = []
        
        supplement_id = supplement.get('supplement_id')
        if not supplement_id:
            return interactions
        
        for med in medications:
            drug_id = med.get('drug_id')
            if not drug_id:
                continue
            
            # Example query (implement with query_generator)
            query = f"""
            MATCH (s:Supplement {{supplement_id: $supplement_id}})
                  -[r:INTERACTS_WITH]-
                  (d:Drug {{drug_id: $drug_id}})
            RETURN r.severity as severity,
                   r.description as description,
                   r.evidence_level as evidence
            """
            
            # TODO: Execute query with query_executor
            # results = self.graph.execute_query(query, {...})
            # interactions.extend(results)
        
        return interactions
    
    
    def _check_similar_effects(self, supplement: Dict, medications: list) -> list:
        """
        Check for similar pharmacological effects
        
        Returns:
            List of effect overlaps
        """
        # TODO: Implement
        return []
    
    
    def _check_shared_metabolism(self, supplement: Dict, medications: list) -> list:
        """
        Check for shared metabolism pathways
        
        Returns:
            List of metabolism conflicts
        """
        # TODO: Implement
        return []
    
    
    def _calculate_confidence(self, interactions: list) -> float:
        """
        Calculate confidence score based on evidence quality
        
        Args:
            interactions: List of interactions found
            
        Returns:
            Confidence score (0-1)
        """
        if not interactions:
            return 0.9  # High confidence when no interactions
        
        # TODO: Implement sophisticated confidence calculation
        # Consider: evidence quality, number of sources, consistency
        
        return 0.75  # Default moderate confidence


# Standalone function for LangGraph
def safety_check_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    """Wrapper for LangGraph integration"""
    from graph.graph_interface import GraphInterface
    
    graph = GraphInterface(
        uri=os.getenv("NEO4J_URI"),
        user=os.getenv("NEO4J_USER"),
        password=os.getenv("NEO4J_PASSWORD")
    )
    
    agent = SafetyCheckAgent(graph)
    return agent.run(state)