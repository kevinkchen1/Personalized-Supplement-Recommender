"""
Updated Query Generator with corrected Neo4j schema properties

Schema corrections:
- DietaryRestriction.dietary_restriction_name (not .name)  
- Nutrient.nutrient_name (not .name)
- DEFICIENT_IN.risk_level (not .severity or .reason)
"""

from enum import Enum
from typing import List, Dict, Any

class QueryType(Enum):
    SAFETY_CHECK = "safety_check"
    DEFICIENCY_CHECK = "deficiency_check"
    RECOMMENDATION = "recommendation"
    DIET_DEFICIENCY = "diet_deficiency"
    MEDICATION_DEPLETION = "medication_depletion"
    COMBINED_DEFICIENCY = "combined_deficiency"

class QueryGenerator:
    """Generates Neo4j Cypher queries for the supplement safety system."""
    
    def generate_query(self, query_type: QueryType, **kwargs) -> str:
        """Generate a Neo4j Cypher query based on the query type and parameters."""
        
        if query_type == QueryType.SAFETY_CHECK:
            return self._safety_check_query(**kwargs)
        elif query_type == QueryType.DEFICIENCY_CHECK:
            return self._deficiency_check_query(**kwargs)
        elif query_type == QueryType.RECOMMENDATION:
            return self._recommendation_query(**kwargs)
        elif query_type == QueryType.DIET_DEFICIENCY:
            return self._diet_deficiency(**kwargs)
        elif query_type == QueryType.MEDICATION_DEPLETION:
            return self._medication_depletion(**kwargs)
        elif query_type == QueryType.COMBINED_DEFICIENCY:
            return self._combined_deficiency(**kwargs)
        else:
            raise ValueError(f"Unknown query type: {query_type}")
    
    def _diet_deficiency(self, dietary_restrictions: List[str]) -> str:
        """Generate query for diet-based nutrient deficiencies."""
        restrictions_str = ", ".join([f"'{r.lower()}'" for r in dietary_restrictions])
        return f"""
        MATCH (dr:DietaryRestriction)-[r:DEFICIENT_IN]->(n:Nutrient)
        WHERE toLower(dr.dietary_restriction_name) IN [{restrictions_str}]
        RETURN dr.dietary_restriction_name as diet,
               n.nutrient_name as nutrient,
               r.risk_level as risk_level
        """
    
    def _medication_depletion(self, medications: List[str]) -> str:
        """Generate query for medication-induced nutrient depletion."""
        medications_str = ", ".join([f"'{med.lower()}'" for med in medications])
        return f"""
        MATCH (m:Medication)-[:MEDICATION_CONTAINS_DRUG]->(d:Drug)-[r:DEPLETES]->(n:Nutrient)
        WHERE toLower(m.medication_name) IN [{medications_str}]
        RETURN m.medication_name as medication,
               d.drug_name as drug,
               n.nutrient_name as nutrient,
               r.risk_level as risk_level,
               r.mechanism as mechanism
        """
    
    def _combined_deficiency(self, dietary_restrictions: List[str], medications: List[str]) -> str:
        """Generate query for combined diet and medication deficiency risks."""
        restrictions_str = ", ".join([f"'{r.lower()}'" for r in dietary_restrictions])
        medications_str = ", ".join([f"'{med.lower()}'" for med in medications])
        
        return f"""
        // Diet-based deficiencies
        MATCH (dr:DietaryRestriction)-[r1:DEFICIENT_IN]->(n:Nutrient)
        WHERE toLower(dr.dietary_restriction_name) IN [{restrictions_str}]
        WITH n.nutrient_name as nutrient, 'diet' as source, dr.dietary_restriction_name as diet_name, r1.risk_level as risk_level
        
        UNION
        
        // Medication-based depletions
        MATCH (m:Medication)-[:MEDICATION_CONTAINS_DRUG]->(d:Drug)-[r2:DEPLETES]->(n:Nutrient)
        WHERE toLower(m.medication_name) IN [{medications_str}]
        WITH n.nutrient_name as nutrient, 'medication' as source, m.medication_name as med_name, r2.risk_level as risk_level
        
        RETURN nutrient, source, 
               CASE WHEN source = 'diet' THEN diet_name ELSE med_name END as source_name,
               risk_level
        ORDER BY nutrient, source
        """
    
    def _safety_check_query(self, medications: List[str], supplements: List[str]) -> str:
        """Generate safety check query for supplement-medication interactions."""
        medications_str = ", ".join([f"'{med.lower()}'" for med in medications])
        supplements_str = ", ".join([f"'{supp.lower()}'" for supp in supplements])
        
        return f"""
        MATCH (s:Supplement)-[r:SUPPLEMENT_INTERACTS_WITH]->(m:Medication)
        WHERE toLower(s.supplement_name) IN [{supplements_str}]
        AND toLower(m.medication_name) IN [{medications_str}]
        RETURN s.supplement_name as supplement,
               m.medication_name as medication,
               r.interaction_type as interaction,
               r.severity as severity,
               r.description as description
        """
    
    def _deficiency_check_query(self, dietary_restrictions: List[str]) -> str:
        """Generate deficiency check query - wrapper for diet_deficiency."""
        return self._diet_deficiency(dietary_restrictions)
    
    def _recommendation_query(self, health_condition: str) -> str:
        """Generate recommendation query for supplements that help with a health condition."""
        return f"""
        MATCH (condition:MedicalCondition)-[:ADDRESSES]-(benefit:BeneficialEffect)-[:PRODUCED_BY]-(s:Supplement)
        WHERE toLower(condition.condition_name) = toLower('{health_condition}')
        RETURN s.supplement_name as supplement,
               benefit.benefit_name as benefit,
               benefit.evidence_strength as evidence_level
        ORDER BY benefit.evidence_strength DESC
        """

# Convenience functions for common query patterns
def generate_diet_deficiency_query(dietary_restrictions: List[str]) -> str:
    """Convenience function to generate diet deficiency query."""
    generator = QueryGenerator()
    return generator.generate_query(QueryType.DIET_DEFICIENCY, dietary_restrictions=dietary_restrictions)

def generate_medication_depletion_query(medications: List[str]) -> str:
    """Convenience function to generate medication depletion query."""
    generator = QueryGenerator()
    return generator.generate_query(QueryType.MEDICATION_DEPLETION, medications=medications)

def generate_combined_deficiency_query(dietary_restrictions: List[str], medications: List[str]) -> str:
    """Convenience function to generate combined deficiency query."""
    generator = QueryGenerator()
    return generator.generate_query(QueryType.COMBINED_DEFICIENCY, 
                                   dietary_restrictions=dietary_restrictions, 
                                   medications=medications)

def generate_safety_check_query(medications: List[str], supplements: List[str]) -> str:
    """Convenience function to generate safety check query."""
    generator = QueryGenerator()
    return generator.generate_query(QueryType.SAFETY_CHECK, 
                                   medications=medications, 
                                   supplements=supplements)

def generate_comprehensive_safety_query(supplement_name: str, medication_names: List[str]) -> Dict[str, Any]:
    """
    Generate a comprehensive safety query that checks ALL interaction pathways:
    1. Direct Supplement → Medication interactions
    2. Supplement → Drug ← Medication (via CONTAINS_DRUG)
    3. Hidden pharma: Supplement → ActiveIngredient → Drug ← Medication
    4. Similar effects: Supplement → Category ← Drug ← Medication
    
    Args:
        supplement_name: Single supplement to check
        medication_names: List of medications to check against
        
    Returns:
        Dict with 'query', 'parameters', and optionally 'error' keys
    """
    if not supplement_name or not medication_names:
        return {'error': 'Missing supplement_name or medication_names'}
    
    # Convert to lowercase for case-insensitive matching
    supplement_lower = supplement_name.lower()
    medications_lower = [med.lower() for med in medication_names]
    
    query = """
    // === PATH 1: Direct Supplement -> Medication interaction ===
    // Relationship: SUPPLEMENT_INTERACTS_WITH (from load_data line 617)
    MATCH (s:Supplement)-[r:SUPPLEMENT_INTERACTS_WITH]->(m:Medication)
    WHERE toLower(s.supplement_name) = toLower($supplement_name)
        AND toLower(m.medication_name) IN $medication_names_lower
    RETURN s.supplement_name AS supplement,
           m.medication_name AS target,
           r.interaction_description AS description,
           'MODERATE'         AS severity,
           null               AS detail,
           'DIRECT_SUPPLEMENT_MEDICATION' AS pathway

    UNION

    // === PATH 2: Supplement -> Drug <- Medication (shared drug interaction) ===
    // Supplement contains ActiveIngredient equivalent to Drug,
    // and that Drug INTERACTS_WITH another Drug that the Medication contains
    MATCH (s:Supplement)-[:CONTAINS]->(ai:ActiveIngredient)-[:EQUIVALENT_TO]->(d1:Drug)
          -[r:INTERACTS_WITH]->(d2:Drug)<-[:MEDICATION_CONTAINS_DRUG]-(m:Medication)
    WHERE toLower(s.supplement_name) = toLower($supplement_name)
        AND toLower(m.medication_name) IN $medication_names_lower
    RETURN s.supplement_name AS supplement,
           m.medication_name AS target,
           r.description     AS description,
           'HIGH'             AS severity,
           d1.drug_name + ' interacts with ' + d2.drug_name AS detail,
           'SUPPLEMENT_DRUG_MEDICATION' AS pathway

    UNION

    // === PATH 3: Hidden pharma equivalence ===
    // Supplement contains ActiveIngredient equivalent to same Drug that Medication contains
    MATCH (s:Supplement)-[:CONTAINS]->(a:ActiveIngredient)
        -[:EQUIVALENT_TO]->(d:Drug)<-[:MEDICATION_CONTAINS_DRUG]-(m:Medication)
    WHERE toLower(s.supplement_name) = toLower($supplement_name)
        AND toLower(m.medication_name) IN $medication_names_lower
    RETURN s.supplement_name AS supplement,
           m.medication_name AS target,
           'Contains equivalent pharmaceutical ingredient - duplication risk' AS description,
           'HIGH'             AS severity,
           a.active_ingredient + ' = ' + d.drug_name AS detail,
           'HIDDEN_PHARMA_EQUIVALENCE' AS pathway

    UNION

    // === PATH 4: Similar pharmacological effect ===
    // Supplement has similar effect to a Category that a Drug belongs to,
    // and that Drug is contained in the Medication
    MATCH (s:Supplement)-[:HAS_SIMILAR_EFFECT_TO]->(c:Category)
        <-[:BELONGS_TO]-(d:Drug)<-[:MEDICATION_CONTAINS_DRUG]-(m:Medication)
    WHERE toLower(s.supplement_name) = toLower($supplement_name)
        AND toLower(m.medication_name) IN $medication_names_lower
    RETURN s.supplement_name AS supplement,
           m.medication_name AS target,
           'Similar pharmacological effect - additive or antagonistic risk' AS description,
           'MODERATE'         AS severity,
           c.category         AS detail,
           'SIMILAR_EFFECT'   AS pathway
    """
    
    return {
        'query': query,
        'parameters': {
            'supplement_name': supplement_lower,
            'medication_names_lower': medications_lower
        }
    }

def generate_safety_queries(supplement_name: str, medication_names: List[str]) -> List[Dict[str, Any]]:
    """
    Generate multiple safety check queries (backwards compatibility).
    Returns a list of query dictionaries.
    """
    return [generate_comprehensive_safety_query(supplement_name, medication_names)]

def generate_supplement_info_query(supplement_name: str) -> Dict[str, Any]:
    """
    Generate query to get detailed information about a supplement.
    """
    if not supplement_name:
        return {'error': 'Missing supplement_name'}
    
    query = """
    MATCH (s:Supplement)
    WHERE toLower(s.supplement_name) = toLower($supplement)
    OPTIONAL MATCH (s)-[:CONTAINS]->(ai:ActiveIngredient)
    OPTIONAL MATCH (s)-[:BELONGS_TO]->(cat:Category)
    RETURN s.supplement_name as supplement,
           s.description as description,
           cat.category_name as category,
           collect(ai.active_ingredient) as active_ingredients
    """
    
    return {
        'query': query,
        'parameters': {'supplement': supplement_name.lower()}
    }

def generate_symptom_recommendation_query(symptom: str) -> Dict[str, Any]:
    """
    Generate query to find supplements that may help with a symptom.
    """
    if not symptom:
        return {'error': 'Missing symptom'}
    
    query = """
    MATCH (sym:Symptom)-[:CAN_CAUSE]->(condition:MedicalCondition)
    MATCH (condition)-[:ADDRESSES]-(benefit:BeneficialEffect)-[:PRODUCED_BY]-(s:Supplement)
    WHERE toLower(sym.symptom_name) = toLower($symptom)
    RETURN s.supplement_name as supplement,
           condition.condition_name as condition,
           benefit.benefit_name as benefit,
           benefit.evidence_strength as evidence_level
    ORDER BY benefit.evidence_strength DESC
    """
    
    return {
        'query': query,
        'parameters': {'symptom': symptom.lower()}
    }
