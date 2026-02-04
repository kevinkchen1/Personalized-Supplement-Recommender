"""
Deficiency Analysis Agent - Nutrition Specialist

Checks for nutrient deficiency risks from:
- Dietary restrictions (vegan → B12, Iron)
- Medication depletions (Metformin → B12)
- Combined risks (vegan + Metformin → HIGH B12 risk)

Role: Nutrition specialist
"""

from typing import Dict, Any
import os


class DeficiencyAgent:
    """
    Specialist agent for analyzing nutrient deficiency risks
    """
    
    def __init__(self, graph_interface):
        self.graph = graph_interface
    
    
    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze nutrient deficiency risks
        
        Args:
            state: Current conversation state
            
        Returns:
            Updated state with deficiency results
        """
        print("\n" + "="*60)
        print("🥗 DEFICIENCY AGENT: Analyzing nutrient risks...")
        print("="*60)
        
        profile = state.get('patient_profile', {})
        
        diet = profile.get('dietary_restrictions', [])
        medications = profile.get('medications', [])
        
        print(f"   Diet: {diet}")
        print(f"   Medications: {len(medications)} drugs")
        
        # Check deficiency risks
        deficiencies = self._analyze_deficiencies(diet, medications)
        
        # Calculate risk levels
        risk_assessment = self._assess_risk_levels(deficiencies)
        
        results = {
            'at_risk': list(deficiencies.keys()),
            'risk_levels': risk_assessment,
            'deficiency_details': deficiencies,
            'sources': self._get_sources(deficiencies)
        }
        
        state['deficiency_checked'] = True
        state['deficiency_results'] = results
        
        print(f"   ✓ Found {len(deficiencies)} potential deficiencies")
        print(f"   At risk: {results['at_risk']}")
        print("="*60 + "\n")
        
        return state
    
    
    def _analyze_deficiencies(self, diet: list, medications: list) -> Dict:
        """
        Analyze deficiency risks from diet and medications
        
        Args:
            diet: List of dietary restrictions
            medications: List of normalized medications
            
        Returns:
            Dict of {nutrient: {sources: [...], severity: ...}}
        """
        deficiencies = {}
        
        # Check diet-related deficiencies
        for restriction in diet:
            diet_deficiencies = self._check_diet_deficiencies(restriction)
            for nutrient, info in diet_deficiencies.items():
                if nutrient not in deficiencies:
                    deficiencies[nutrient] = {'sources': [], 'severity': 'LOW'}
                deficiencies[nutrient]['sources'].append(f"Diet: {restriction}")
        
        # Check medication depletions
        for med in medications:
            med_depletions = self._check_medication_depletions(med)
            for nutrient, info in med_depletions.items():
                if nutrient not in deficiencies:
                    deficiencies[nutrient] = {'sources': [], 'severity': 'LOW'}
                else:
                    # Combined risk - upgrade severity
                    deficiencies[nutrient]['severity'] = 'HIGH'
                deficiencies[nutrient]['sources'].append(
                    f"Medication: {med.get('matched_drug', med.get('user_input'))}"
                )
        
        return deficiencies
    
    
    def _check_diet_deficiencies(self, restriction: str) -> Dict:
        """
        Check deficiencies associated with dietary restriction
        
        Args:
            restriction: Dietary restriction (e.g., "Vegan")
            
        Returns:
            Dict of nutrients at risk
        """
        # TODO: Implement with actual database query
        # Query: MATCH (dr:DietaryRestriction)-[:DEFICIENT_IN]->(n:Nutrient)
        
        # Placeholder
        deficiency_map = {
            'Vegan': {'Vitamin B-12': {}, 'Iron': {}, 'Vitamin D': {}},
            'Vegetarian': {'Vitamin B-12': {}, 'Iron': {}},
            # Add more...
        }
        
        return deficiency_map.get(restriction, {})
    
    
    def _check_medication_depletions(self, medication: Dict) -> Dict:
        """
        Check nutrient depletions caused by medication
        
        Args:
            medication: Normalized medication dict
            
        Returns:
            Dict of nutrients depleted
        """
        # TODO: Implement with actual database query
        # Query: MATCH (d:Drug)-[:DEPLETES]->(n:Nutrient)
        
        return {}
    
    
    def _assess_risk_levels(self, deficiencies: Dict) -> Dict:
        """
        Assess risk level for each deficiency
        
        Args:
            deficiencies: Dict of deficiency info
            
        Returns:
            Dict of {nutrient: risk_level}
        """
        risk_levels = {}
        
        for nutrient, info in deficiencies.items():
            sources = info.get('sources', [])
            
            if len(sources) >= 2:
                risk_levels[nutrient] = 'HIGH'  # Multiple sources
            elif len(sources) == 1:
                risk_levels[nutrient] = 'MEDIUM'
            else:
                risk_levels[nutrient] = 'LOW'
        
        return risk_levels
    
    
    def _get_sources(self, deficiencies: Dict) -> list:
        """
        Compile list of all sources
        
        Args:
            deficiencies: Dict of deficiency info
            
        Returns:
            List of source strings
        """
        sources = []
        for nutrient, info in deficiencies.items():
            sources.extend(info.get('sources', []))
        return list(set(sources))


# Standalone function for LangGraph
def deficiency_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    """Wrapper for LangGraph integration"""
    from graph.graph_interface import GraphInterface
    
    graph = GraphInterface(
        uri=os.getenv("NEO4J_URI"),
        user=os.getenv("NEO4J_USER"),
        password=os.getenv("NEO4J_PASSWORD")
    )
    
    agent = DeficiencyAgent(graph)
    return agent.run(state)