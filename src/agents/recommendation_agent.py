"""
Recommendation Agent - Supplement Advisor

Finds safe supplement recommendations for conditions/symptoms:
- Finds supplements that help the condition
- Filters out ones that interact with user's medications
- Ranks by evidence strength

Role: Recommendation specialist
"""

from typing import Dict, Any
import os


class RecommendationAgent:
    """
    Specialist agent for supplement recommendations
    """
    
    def __init__(self, graph_interface):
        self.graph = graph_interface
    
    
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
        
        # Get condition/symptom from extracted entities or profile
        normalized = state.get('normalized_entities', {})
        profile = state.get('patient_profile', {})
        
        conditions = normalized.get('conditions', []) or profile.get('conditions', [])
        medications = profile.get('medications', [])
        
        if not conditions:
            print("⚠️  No conditions specified")
            state['recommendations_checked'] = True
            state['recommendation_results'] = {'recommendations': []}
            return state
        
        condition = conditions[0]  # Check first condition
        print(f"   Condition: {condition}")
        print(f"   Filtering against: {len(medications)} medications")
        
        # Find and filter recommendations
        recommendations = self._generate_recommendations(condition, medications)
        
        results = {
            'condition': condition,
            'recommendations': recommendations,
            'filtered_count': 0  # TODO: Track how many were filtered
        }
        
        state['recommendations_checked'] = True
        state['recommendation_results'] = results
        
        print(f"   ✓ Found {len(recommendations)} safe options")
        print("="*60 + "\n")
        
        return state
    
    
    def _generate_recommendations(self, condition: str, medications: list) -> list:
        """
        Generate filtered supplement recommendations
        
        Args:
            condition: Health condition to address
            medications: User's medications
            
        Returns:
            List of safe supplement recommendations
        """
        # Step 1: Find supplements that help the condition
        candidates = self._find_supplements_for_condition(condition)
        
        # Step 2: Filter out unsafe ones
        safe_options = self._filter_unsafe(candidates, medications)
        
        # Step 3: Rank by evidence strength
        ranked = self._rank_by_evidence(safe_options)
        
        return ranked
    
    
    def _find_supplements_for_condition(self, condition: str) -> list:
        """
        Find supplements that help with condition
        
        Args:
            condition: Health condition
            
        Returns:
            List of supplement candidates
        """
        # TODO: Implement with actual database query
        # Query: MATCH (s:Supplement)-[:HELPS_WITH]->(c:Condition)
        
        return []
    
    
    def _filter_unsafe(self, candidates: list, medications: list) -> list:
        """
        Filter out supplements that interact with user's medications
        
        Args:
            candidates: List of supplement candidates
            medications: User's medications
            
        Returns:
            List of safe supplements
        """
        # TODO: Use safety_check logic to filter
        
        safe = []
        for supplement in candidates:
            # Check if it interacts with any medication
            has_interaction = False
            
            # TODO: Check interactions
            # if has_interaction:
            #     continue
            
            safe.append(supplement)
        
        return safe
    
    
    def _rank_by_evidence(self, supplements: list) -> list:
        """
        Rank supplements by evidence strength
        
        Args:
            supplements: List of safe supplements
            
        Returns:
            Ranked list
        """
        # TODO: Implement evidence-based ranking
        # Consider: clinical trials, meta-analyses, expert consensus
        
        return supplements


# Standalone function for LangGraph
def recommendation_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    """Wrapper for LangGraph integration"""
    from graph.graph_interface import GraphInterface
    
    graph = GraphInterface(
        uri=os.getenv("NEO4J_URI"),
        user=os.getenv("NEO4J_USER"),
        password=os.getenv("NEO4J_PASSWORD")
    )
    
    agent = RecommendationAgent(graph)
    return agent.run(state)