"""
Deficiency Agent - Final corrected version with proper Neo4j schema

Confirmed Schema:
- DietaryRestriction nodes: 'dietary_restriction_name' property  
- Nutrient nodes: 'nutrient_name' property
- DEFICIENT_IN relationship: 'risk_level' property (not 'severity' or 'reason')
"""

import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class DeficiencyAgent:
    """Agent responsible for identifying nutrient deficiencies from diet and medications."""
    
    def __init__(self, llm, query_executor):
        """Initialize the deficiency agent.
        
        Args:
            llm: Language model for processing
            query_executor: Tool for executing Neo4j queries
        """
        self.llm = llm
        self.query_executor = query_executor
        self.agent_name = "DeficiencyAgent"
    
    def analyze_deficiencies(self, patient_profile: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze potential nutrient deficiencies based on dietary restrictions and medications.
        
        Args:
            patient_profile: User's health profile containing dietary restrictions and medications
            
        Returns:
            Dictionary containing deficiency analysis results
        """
        try:
            logger.info(f"{self.agent_name}: Starting deficiency analysis")
            
            # Extract dietary restrictions (handle both possible keys)
            dietary_restrictions = (
                patient_profile.get('dietary_restrictions', []) or 
                patient_profile.get('diet', [])
            )
            
            # Ensure it's a list
            if isinstance(dietary_restrictions, str):
                dietary_restrictions = [dietary_restrictions]
            elif not isinstance(dietary_restrictions, list):
                dietary_restrictions = []
            
            medications = patient_profile.get('medications', [])
            
            logger.info(f"Dietary restrictions: {dietary_restrictions}")
            logger.info(f"Medications: {medications}")
            
            # Check deficiencies from different sources
            diet_deficiencies = self._check_diet_deficiencies(dietary_restrictions)
            medication_depletions = self._check_medication_depletions(medications)
            
            # Calculate combined risks and recommendations
            analysis_results = self._analyze_combined_risks(
                diet_deficiencies, 
                medication_depletions,
                medications
            )
            
            return {
                'agent': self.agent_name,
                'status': 'success',
                'analysis': analysis_results,
                'diet_deficiencies': diet_deficiencies,
                'medication_depletions': medication_depletions
            }
            
        except Exception as e:
            logger.error(f"{self.agent_name}: Error in analysis - {str(e)}")
            return {
                'agent': self.agent_name,
                'status': 'error',
                'error': str(e),
                'analysis': None
            }
    
    def _check_diet_deficiencies(self, dietary_restrictions: List[str]) -> List[Dict]:
        """Check for nutrient deficiencies based on dietary restrictions."""
        if not dietary_restrictions:
            return []
        
        # Convert to lowercase for case-insensitive matching
        restrictions_lower = [r.lower() for r in dietary_restrictions]
        
        query = """
        MATCH (dr:DietaryRestriction)-[r:DEFICIENT_IN]->(n:Nutrient)
        WHERE toLower(dr.dietary_restriction_name) IN $restrictions
        RETURN dr.dietary_restriction_name as diet,
               n.nutrient_name as nutrient,
               r.risk_level as risk_level
        """
        
        try:
            results = self.query_executor.execute_query(
                query, 
                {"restrictions": restrictions_lower}
            )
            
            deficiencies = []
            for record in results:
                deficiencies.append({
                    'diet': record.get('diet'),
                    'nutrient': record.get('nutrient'),
                    'risk_level': record.get('risk_level', 'MEDIUM'),
                    'reason': f'Common deficiency in {record.get("diet")} diet',
                    'source': 'dietary_restriction'
                })
            
            logger.info(f"Found {len(deficiencies)} diet-based deficiencies")
            return deficiencies
            
        except Exception as e:
            logger.error(f"Error checking diet deficiencies: {str(e)}")
            return []
    
    def _check_medication_depletions(self, medications: List[str]) -> List[Dict]:
        """Check for nutrient depletions caused by medications."""
        if not medications:
            return []
        
        # Convert medications to lowercase for case-insensitive matching
        medications_lower = [med.lower() for med in medications]
        
        # First, let's check what the actual medication schema looks like
        # We'll need to discover the correct relationship path
        query = """
        MATCH (m:Medication)-[:MEDICATION_CONTAINS_DRUG]->(d:Drug)-[r:DEPLETES]->(n:Nutrient)
        WHERE toLower(m.medication_name) IN $medications
        RETURN m.medication_name as medication,
               d.drug_name as drug,
               n.nutrient_name as nutrient,
               r.risk_level as risk_level,
               r.mechanism as mechanism
        """
        
        try:
            results = self.query_executor.execute_query(
                query, 
                {"medications": medications_lower}
            )
            
            depletions = []
            for record in results:
                depletions.append({
                    'medication': record.get('medication'),
                    'drug': record.get('drug'),
                    'nutrient': record.get('nutrient'),
                    'risk_level': record.get('risk_level', 'MEDIUM'),
                    'mechanism': record.get('mechanism', 'Nutrient depletion'),
                    'source': 'medication'
                })
            
            logger.info(f"Found {len(depletions)} medication-induced depletions")
            return depletions
            
        except Exception as e:
            logger.error(f"Error checking medication depletions: {str(e)}")
            return []
    
    def _analyze_combined_risks(self, diet_deficiencies: List[Dict], 
                               medication_depletions: List[Dict],
                               medications: List[str]) -> Dict[str, Any]:
        """Analyze combined risks and generate recommendations."""
        
        # Group deficiencies by nutrient
        nutrient_risks = {}
        
        # Add diet-based deficiencies
        for deficiency in diet_deficiencies:
            nutrient = deficiency['nutrient']
            if nutrient not in nutrient_risks:
                nutrient_risks[nutrient] = {
                    'nutrient': nutrient,
                    'sources': [],
                    'risk_level': 'LOW',
                    'reasons': []
                }
            
            nutrient_risks[nutrient]['sources'].append('diet')
            nutrient_risks[nutrient]['reasons'].append(deficiency['reason'])
            
            # Update risk level based on database risk_level
            db_risk = deficiency.get('risk_level', 'MEDIUM')
            if db_risk in ['HIGH', 'SEVERE']:
                nutrient_risks[nutrient]['risk_level'] = 'HIGH'
            elif db_risk == 'MEDIUM' and nutrient_risks[nutrient]['risk_level'] == 'LOW':
                nutrient_risks[nutrient]['risk_level'] = 'MEDIUM'
        
        # Add medication-based depletions
        for depletion in medication_depletions:
            nutrient = depletion['nutrient']
            if nutrient not in nutrient_risks:
                nutrient_risks[nutrient] = {
                    'nutrient': nutrient,
                    'sources': [],
                    'risk_level': 'LOW',
                    'reasons': []
                }
            
            nutrient_risks[nutrient]['sources'].append('medication')
            nutrient_risks[nutrient]['reasons'].append(
                f"Medication ({depletion['medication']}): {depletion['mechanism']}"
            )
            
            # Update risk level
            db_risk = depletion.get('risk_level', 'MEDIUM')
            if db_risk in ['HIGH', 'SEVERE']:
                nutrient_risks[nutrient]['risk_level'] = 'HIGH'
            elif db_risk == 'MEDIUM' and nutrient_risks[nutrient]['risk_level'] == 'LOW':
                nutrient_risks[nutrient]['risk_level'] = 'MEDIUM'
        
        # Identify HIGH RISK nutrients (affected by both diet and medications)
        for nutrient_data in nutrient_risks.values():
            if 'diet' in nutrient_data['sources'] and 'medication' in nutrient_data['sources']:
                nutrient_data['risk_level'] = 'HIGH'
                nutrient_data['reasons'].append("🚨 COMBINED RISK: Both diet and medication affect this nutrient")
        
        # Generate supplement recommendations for deficient nutrients
        recommendations = self._get_supplement_recommendations(
            list(nutrient_risks.keys()),
            medications
        )
        
        return {
            'nutrient_risks': list(nutrient_risks.values()),
            'total_deficiencies': len(nutrient_risks),
            'high_risk_count': sum(1 for nr in nutrient_risks.values() if nr['risk_level'] == 'HIGH'),
            'recommendations': recommendations
        }
    
    def _get_supplement_recommendations(self, deficient_nutrients: List[str], 
                                      medications: List[str]) -> List[Dict]:
        """Get supplement recommendations for deficient nutrients, checking safety."""
        if not deficient_nutrients:
            return []
        
        recommendations = []
        
        for nutrient in deficient_nutrients:
            # Find supplements that provide this nutrient
            # We need to discover the correct relationship path for supplements
            supplement_query = """
            MATCH (s:Supplement)-[:CONTAINS]->(ai:ActiveIngredient)-[:PROVIDES]->(n:Nutrient)
            WHERE toLower(n.nutrient_name) = toLower($nutrient)
            RETURN s.supplement_name as supplement,
                   s.category as category,
                   ai.active_ingredient as active_ingredient
            LIMIT 5
            """
            
            try:
                supplement_results = self.query_executor.execute_query(
                    supplement_query, 
                    {"nutrient": nutrient}
                )
                
                if supplement_results:
                    for record in supplement_results:
                        supplement_name = record.get('supplement')
                        
                        # Check safety against user's medications
                        safety_status = self._check_supplement_safety(supplement_name, medications)
                        
                        recommendations.append({
                            'nutrient': nutrient,
                            'supplement': supplement_name,
                            'category': record.get('category'),
                            'active_ingredient': record.get('active_ingredient'),
                            'safety_status': safety_status['status'],
                            'safety_warnings': safety_status.get('warnings', [])
                        })
                else:
                    # If no specific supplements found, provide general recommendation
                    recommendations.append({
                        'nutrient': nutrient,
                        'supplement': f'{nutrient} supplement',
                        'category': 'General',
                        'active_ingredient': nutrient,
                        'safety_status': 'CHECK_REQUIRED',
                        'safety_warnings': ['Please consult healthcare provider for specific product recommendations']
                    })
                    
            except Exception as e:
                logger.error(f"Error getting recommendations for {nutrient}: {str(e)}")
                # Provide fallback recommendation
                recommendations.append({
                    'nutrient': nutrient,
                    'supplement': f'{nutrient} supplement',
                    'category': 'General',
                    'active_ingredient': nutrient,
                    'safety_status': 'CHECK_REQUIRED',
                    'safety_warnings': ['Please consult healthcare provider']
                })
        
        return recommendations
    
    def _check_supplement_safety(self, supplement_name: str, medications: List[str]) -> Dict:
        """Check if a supplement is safe with user's medications."""
        if not medications:
            return {'status': 'SAFE', 'warnings': []}
        
        # Check for direct supplement-medication interactions
        safety_query = """
        MATCH (s:Supplement)-[r:SUPPLEMENT_INTERACTS_WITH]->(m:Medication)
        WHERE toLower(s.supplement_name) = toLower($supplement)
        AND toLower(m.medication_name) IN $medications
        RETURN r.interaction_type as interaction,
               r.severity as severity,
               r.description as description
        """
        
        try:
            medications_lower = [med.lower() for med in medications]
            results = self.query_executor.execute_query(
                safety_query, 
                {"supplement": supplement_name, "medications": medications_lower}
            )
            
            if results:
                warnings = []
                max_severity = 'LOW'
                
                for record in results:
                    interaction = record.get('interaction', 'Unknown interaction')
                    severity = record.get('severity', 'MEDIUM')
                    description = record.get('description', 'Potential interaction detected')
                    
                    warnings.append(f"{severity}: {description}")
                    
                    if severity in ['HIGH', 'SEVERE'] and max_severity != 'SEVERE':
                        max_severity = 'SEVERE'
                    elif severity == 'MEDIUM' and max_severity == 'LOW':
                        max_severity = 'MEDIUM'
                
                status = 'UNSAFE' if max_severity in ['HIGH', 'SEVERE'] else 'CAUTION'
                return {'status': status, 'warnings': warnings}
            else:
                return {'status': 'SAFE', 'warnings': []}
                
        except Exception as e:
            logger.error(f"Error checking safety for {supplement_name}: {str(e)}")
            return {'status': 'CHECK_REQUIRED', 'warnings': ['Unable to verify safety']}


# ======================================================================
# Standalone function for LangGraph
# ======================================================================

def deficiency_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    """Entry point for LangGraph workflow."""
    from graph.graph_interface import GraphInterface
    from tools.query_executor import QueryExecutor
    import anthropic
    
    # Use existing graph_interface from state, or create new one
    graph = state.get('graph_interface')
    if graph is None:
        import os
        graph = GraphInterface(
            uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            user=os.getenv("NEO4J_USER", "neo4j"),
            password=os.getenv("NEO4J_PASSWORD", ""),
        )
    
    # Create query executor
    query_executor = QueryExecutor(graph)
    
    # Create LLM client
    llm = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    
    # Create and run the agent
    agent = DeficiencyAgent(llm, query_executor)
    return agent.analyze_deficiencies(state.get('patient_profile', {}))
