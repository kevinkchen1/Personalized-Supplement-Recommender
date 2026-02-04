"""
Query Generator Tool - Cypher Query Builder

Translates high-level intents into Neo4j Cypher queries:
- Safety checks (interactions, effects, metabolism)
- Deficiency analysis (diet, medication depletions)
- Supplement recommendations
- Can try multiple query strategies if first fails

Role: SQL/Cypher writer for the agents
"""

from typing import Dict, Any, List, Optional
from enum import Enum


class QueryType(Enum):
    """Types of queries the system can generate"""
    DIRECT_INTERACTION = "direct_interaction"
    SIMILAR_EFFECTS = "similar_effects"
    SHARED_METABOLISM = "shared_metabolism"
    DIET_DEFICIENCY = "diet_deficiency"
    MEDICATION_DEPLETION = "medication_depletion"
    CONDITION_SUPPLEMENTS = "condition_supplements"
    SUPPLEMENT_EVIDENCE = "supplement_evidence"


class QueryGenerator:
    """
    Generates Cypher queries based on agent intents
    """
    
    def __init__(self):
        """Initialize query generator"""
        self.query_templates = self._load_query_templates()
    
    
    def generate_query(
        self, 
        query_type: str, 
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate a Cypher query based on type and parameters
        
        Args:
            query_type: Type of query to generate (from QueryType enum)
            params: Parameters for the query (IDs, names, etc.)
            
        Returns:
            Dict with:
                - query: Cypher query string
                - parameters: Dict of parameters for query
                - explanation: Human-readable explanation
                
        Example:
            >>> gen = QueryGenerator()
            >>> result = gen.generate_query(
            ...     "direct_interaction",
            ...     {"supplement_id": "S07", "drug_id": "DB00682"}
            ... )
            >>> print(result['query'])
            MATCH (s:Supplement)-[r:INTERACTS_WITH]-(d:Drug) ...
        """
        # Validate query type
        try:
            query_type_enum = QueryType(query_type)
        except ValueError:
            return {
                'error': f"Invalid query type: {query_type}",
                'query': None,
                'parameters': None
            }
        
        # Route to appropriate generator
        if query_type_enum == QueryType.DIRECT_INTERACTION:
            return self._generate_direct_interaction_query(params)
        
        elif query_type_enum == QueryType.SIMILAR_EFFECTS:
            return self._generate_similar_effects_query(params)
        
        elif query_type_enum == QueryType.SHARED_METABOLISM:
            return self._generate_metabolism_query(params)
        
        elif query_type_enum == QueryType.DIET_DEFICIENCY:
            return self._generate_diet_deficiency_query(params)
        
        elif query_type_enum == QueryType.MEDICATION_DEPLETION:
            return self._generate_medication_depletion_query(params)
        
        elif query_type_enum == QueryType.CONDITION_SUPPLEMENTS:
            return self._generate_condition_supplements_query(params)
        
        elif query_type_enum == QueryType.SUPPLEMENT_EVIDENCE:
            return self._generate_evidence_query(params)
        
        else:
            return {
                'error': f"Query type not implemented: {query_type}",
                'query': None,
                'parameters': None
            }
    
    
    def _generate_direct_interaction_query(self, params: Dict) -> Dict:
        """
        Generate query for direct drug-supplement interactions
        
        Args:
            params: {
                'supplement_id': str,
                'drug_ids': List[str] (can be single drug_id as string)
            }
            
        Returns:
            Query dict
        """
        supplement_id = params.get('supplement_id')
        drug_ids = params.get('drug_ids', [])
        
        # Handle single drug_id
        if isinstance(drug_ids, str):
            drug_ids = [drug_ids]
        elif params.get('drug_id'):
            drug_ids = [params['drug_id']]
        
        if not supplement_id or not drug_ids:
            return {
                'error': 'Missing supplement_id or drug_ids',
                'query': None,
                'parameters': None
            }
        
        query = """
        MATCH (s:Supplement {supplement_id: $supplement_id})
              -[r:INTERACTS_WITH]-
              (d:Drug)
        WHERE d.drug_id IN $drug_ids
        RETURN s.supplement_name as supplement,
               d.drug_name as drug,
               r.severity as severity,
               r.description as description,
               r.evidence_level as evidence,
               r.mechanism as mechanism
        """
        
        parameters = {
            'supplement_id': supplement_id,
            'drug_ids': drug_ids
        }
        
        explanation = (
            f"Checking direct interactions between supplement {supplement_id} "
            f"and {len(drug_ids)} medication(s)"
        )
        
        return {
            'query': query.strip(),
            'parameters': parameters,
            'explanation': explanation
        }
    
    
    def _generate_similar_effects_query(self, params: Dict) -> Dict:
        """
        Generate query for similar pharmacological effects
        
        Args:
            params: {
                'supplement_id': str,
                'drug_ids': List[str]
            }
            
        Returns:
            Query dict
        """
        supplement_id = params.get('supplement_id')
        drug_ids = params.get('drug_ids', [])
        
        if isinstance(drug_ids, str):
            drug_ids = [drug_ids]
        
        query = """
        // Find effects of the supplement
        MATCH (s:Supplement {supplement_id: $supplement_id})
              -[:HAS_EFFECT]->(effect:PharmacologicalEffect)
        
        // Find drugs with same effects
        MATCH (d:Drug)-[:HAS_EFFECT]->(effect)
        WHERE d.drug_id IN $drug_ids
        
        RETURN DISTINCT
               s.supplement_name as supplement,
               d.drug_name as drug,
               effect.effect_name as shared_effect,
               effect.severity_potential as potential_severity,
               'similar_effects' as interaction_type
        """
        
        parameters = {
            'supplement_id': supplement_id,
            'drug_ids': drug_ids
        }
        
        explanation = (
            f"Checking for similar pharmacological effects between "
            f"supplement {supplement_id} and medications"
        )
        
        return {
            'query': query.strip(),
            'parameters': parameters,
            'explanation': explanation
        }
    
    
    def _generate_metabolism_query(self, params: Dict) -> Dict:
        """
        Generate query for shared metabolism pathways
        
        Args:
            params: {
                'supplement_id': str,
                'drug_ids': List[str]
            }
            
        Returns:
            Query dict
        """
        supplement_id = params.get('supplement_id')
        drug_ids = params.get('drug_ids', [])
        
        if isinstance(drug_ids, str):
            drug_ids = [drug_ids]
        
        query = """
        // Find supplement's metabolism pathways
        MATCH (s:Supplement {supplement_id: $supplement_id})
              -[sr:METABOLIZED_BY]->(enzyme:Enzyme)
        
        // Find drugs using same enzymes
        MATCH (d:Drug)-[dr:METABOLIZED_BY]->(enzyme)
        WHERE d.drug_id IN $drug_ids
        
        // Check if they compete (both are substrates) or one inhibits
        WITH s, d, enzyme, sr, dr
        WHERE (sr.role = 'substrate' AND dr.role = 'substrate')
           OR (sr.role = 'inhibitor' AND dr.role = 'substrate')
           OR (sr.role = 'substrate' AND dr.role = 'inhibitor')
        
        RETURN s.supplement_name as supplement,
               d.drug_name as drug,
               enzyme.enzyme_name as enzyme,
               sr.role as supplement_role,
               dr.role as drug_role,
               'metabolism_conflict' as interaction_type
        """
        
        parameters = {
            'supplement_id': supplement_id,
            'drug_ids': drug_ids
        }
        
        explanation = (
            f"Checking for shared metabolism pathways (CYP450 enzymes) "
            f"between supplement and medications"
        )
        
        return {
            'query': query.strip(),
            'parameters': parameters,
            'explanation': explanation
        }
    
    
    def _generate_diet_deficiency_query(self, params: Dict) -> Dict:
        """
        Generate query for diet-related deficiencies
        
        Args:
            params: {
                'dietary_restrictions': List[str] or str
            }
            
        Returns:
            Query dict
        """
        restrictions = params.get('dietary_restrictions', [])
        
        if isinstance(restrictions, str):
            restrictions = [restrictions]
        
        if not restrictions:
            return {
                'error': 'No dietary restrictions provided',
                'query': None,
                'parameters': None
            }
        
        query = """
        MATCH (dr:DietaryRestriction)-[:DEFICIENT_IN]->(n:Nutrient)
        WHERE dr.restriction_name IN $restrictions
        RETURN dr.restriction_name as diet,
               n.nutrient_name as nutrient,
               n.recommended_daily_intake as rdi,
               n.deficiency_symptoms as symptoms,
               'diet' as source
        """
        
        parameters = {
            'restrictions': restrictions
        }
        
        explanation = (
            f"Checking nutrient deficiencies associated with "
            f"{', '.join(restrictions)} diet"
        )
        
        return {
            'query': query.strip(),
            'parameters': parameters,
            'explanation': explanation
        }
    
    
    def _generate_medication_depletion_query(self, params: Dict) -> Dict:
        """
        Generate query for medication-induced nutrient depletion
        
        Args:
            params: {
                'drug_ids': List[str]
            }
            
        Returns:
            Query dict
        """
        drug_ids = params.get('drug_ids', [])
        
        if isinstance(drug_ids, str):
            drug_ids = [drug_ids]
        
        if not drug_ids:
            return {
                'error': 'No drug IDs provided',
                'query': None,
                'parameters': None
            }
        
        query = """
        MATCH (d:Drug)-[:DEPLETES]->(n:Nutrient)
        WHERE d.drug_id IN $drug_ids
        RETURN d.drug_name as medication,
               n.nutrient_name as nutrient,
               n.recommended_daily_intake as rdi,
               n.deficiency_symptoms as symptoms,
               'medication' as source
        """
        
        parameters = {
            'drug_ids': drug_ids
        }
        
        explanation = (
            f"Checking nutrient depletions caused by {len(drug_ids)} medication(s)"
        )
        
        return {
            'query': query.strip(),
            'parameters': parameters,
            'explanation': explanation
        }
    
    
    def _generate_condition_supplements_query(self, params: Dict) -> Dict:
        """
        Generate query for supplements that help a condition
        
        Args:
            params: {
                'condition': str
            }
            
        Returns:
            Query dict
        """
        condition = params.get('condition')
        
        if not condition:
            return {
                'error': 'No condition provided',
                'query': None,
                'parameters': None
            }
        
        query = """
        MATCH (s:Supplement)-[r:HELPS_WITH]->(c:Condition)
        WHERE toLower(c.condition_name) CONTAINS toLower($condition)
        RETURN s.supplement_id as supplement_id,
               s.supplement_name as supplement_name,
               c.condition_name as condition,
               r.effectiveness as effectiveness,
               r.evidence_level as evidence_level,
               r.dosage as recommended_dosage
        ORDER BY r.evidence_level DESC, r.effectiveness DESC
        """
        
        parameters = {
            'condition': condition
        }
        
        explanation = f"Finding supplements that help with {condition}"
        
        return {
            'query': query.strip(),
            'parameters': parameters,
            'explanation': explanation
        }
    
    
    def _generate_evidence_query(self, params: Dict) -> Dict:
        """
        Generate query for supplement evidence/research
        
        Args:
            params: {
                'supplement_id': str
            }
            
        Returns:
            Query dict
        """
        supplement_id = params.get('supplement_id')
        
        if not supplement_id:
            return {
                'error': 'No supplement_id provided',
                'query': None,
                'parameters': None
            }
        
        query = """
        MATCH (s:Supplement {supplement_id: $supplement_id})
              -[:STUDIED_IN]->(study:ClinicalStudy)
        RETURN s.supplement_name as supplement,
               study.title as study_title,
               study.study_type as study_type,
               study.year as year,
               study.conclusion as conclusion,
               study.evidence_quality as quality
        ORDER BY study.year DESC, study.evidence_quality DESC
        """
        
        parameters = {
            'supplement_id': supplement_id
        }
        
        explanation = f"Retrieving research evidence for supplement {supplement_id}"
        
        return {
            'query': query.strip(),
            'parameters': parameters,
            'explanation': explanation
        }
    
    
    def _load_query_templates(self) -> Dict:
        """
        Load pre-defined query templates
        
        Returns:
            Dict of query templates
        """
        # TODO: Load from config file if needed
        return {}
    
    
    def generate_fallback_query(
        self, 
        original_type: str, 
        params: Dict
    ) -> Dict:
        """
        Generate an alternative query if the first one fails
        
        Args:
            original_type: The query type that failed
            params: Original parameters
            
        Returns:
            Alternative query dict
        """
        # TODO: Implement fallback strategies
        # Example: If direct interaction fails, try text search
        
        return {
            'query': None,
            'parameters': None,
            'explanation': 'No fallback available'
        }


# Helper functions for agents
def generate_safety_queries(
    supplement_id: str, 
    drug_ids: List[str]
) -> List[Dict]:
    """
    Generate all safety-related queries
    
    Args:
        supplement_id: Supplement to check
        drug_ids: List of drug IDs to check against
        
    Returns:
        List of query dicts for all safety checks
    """
    generator = QueryGenerator()
    
    queries = []
    
    # Direct interactions
    queries.append(generator.generate_query(
        'direct_interaction',
        {'supplement_id': supplement_id, 'drug_ids': drug_ids}
    ))
    
    # Similar effects
    queries.append(generator.generate_query(
        'similar_effects',
        {'supplement_id': supplement_id, 'drug_ids': drug_ids}
    ))
    
    # Shared metabolism
    queries.append(generator.generate_query(
        'shared_metabolism',
        {'supplement_id': supplement_id, 'drug_ids': drug_ids}
    ))
    
    return queries


def generate_deficiency_queries(
    dietary_restrictions: List[str],
    drug_ids: List[str]
) -> List[Dict]:
    """
    Generate all deficiency-related queries
    
    Args:
        dietary_restrictions: List of diet restrictions
        drug_ids: List of medications
        
    Returns:
        List of query dicts for deficiency checks
    """
    generator = QueryGenerator()
    
    queries = []
    
    # Diet deficiencies
    if dietary_restrictions:
        queries.append(generator.generate_query(
            'diet_deficiency',
            {'dietary_restrictions': dietary_restrictions}
        ))
    
    # Medication depletions
    if drug_ids:
        queries.append(generator.generate_query(
            'medication_depletion',
            {'drug_ids': drug_ids}
        ))
    
    return queries


if __name__ == "__main__":
    # Quick test
    gen = QueryGenerator()
    
    # Test direct interaction query
    result = gen.generate_query(
        'direct_interaction',
        {
            'supplement_id': 'S07',
            'drug_ids': ['DB00682', 'DB00331']
        }
    )
    
    print("Query:", result['query'])
    print("\nParameters:", result['parameters'])
    print("\nExplanation:", result['explanation'])
