"""
Query Generator Tool - Cypher Query Builder

Translates high-level intents into Neo4j Cypher queries matched to the
actual knowledge graph schema:

NODE LABELS:
    Supplement, ActiveIngredient, Drug, Medication, BrandName,
    Category, Salt, Synonym, Symptom, FoodInteraction

RELATIONSHIPS:
    Supplement -[:CONTAINS]-> ActiveIngredient
    Supplement -[:INTERACTS_WITH]-> Drug
    Supplement -[:INTERACTS_WITH]-> Medication
    Supplement -[:HAS_SIMILAR_EFFECT_TO]-> Category
    Supplement -[:TREATS]-> Symptom
    Supplement -[:CAN_CAUSE]-> Symptom
    ActiveIngredient -[:EQUIVALENT_TO]-> Drug
    Drug -[:BELONGS_TO]-> Category
    Drug -[:INTERACTS_WITH]-> Drug
    Drug -[:INTERACTS_WITH]-> Medication
    Drug -[:KNOWN_AS]-> Synonym
    Drug -[:HAS_SALT_FORM]-> Salt
    Drug -[:HAS_FOOD_INTERACTION]-> FoodInteraction
    BrandName -[:CONTAINS_DRUG]-> Drug
    Medication -[:CONTAINS_DRUG]-> Drug

PROPERTY KEYS (commonly indexed):
    Drug: drug_id, drug_name
    Supplement: supplement_id, supplement_name
    Medication: medication_id, medication_name
    ActiveIngredient: active_ingredient_id, active_ingredient
    Category: category_id, category
    BrandName: brand_name_id, brand_name
    Symptom: symptom_id
    Others: description, confidence, safety_rating, notes, indication, etc.

Role: Cypher writer for the agents
"""

from typing import Dict, Any, List, Optional
from enum import Enum


class QueryType(Enum):
    """Types of queries the system can generate"""
    # Safety queries
    SUPPLEMENT_MEDICATION_INTERACTION = "supplement_medication_interaction"
    SUPPLEMENT_DRUG_INTERACTION = "supplement_drug_interaction"
    HIDDEN_PHARMA_EQUIVALENCE = "hidden_pharma_equivalence"
    SIMILAR_EFFECT_OVERLAP = "similar_effect_overlap"
    DRUG_DRUG_INTERACTION = "drug_drug_interaction"
    COMPREHENSIVE_SAFETY = "comprehensive_safety"

    # Info / side-effect queries
    FOOD_INTERACTIONS = "food_interactions"
    SUPPLEMENT_SIDE_EFFECTS = "supplement_side_effects"

    # Recommendation queries
    SUPPLEMENTS_FOR_SYMPTOM = "supplements_for_symptom"
    SUPPLEMENT_INFO = "supplement_info"

    # Lookup / utility queries
    FIND_SUPPLEMENT = "find_supplement"
    FIND_MEDICATION = "find_medication"
    FIND_DRUG = "find_drug"


class QueryGenerator:
    """
    Generates Cypher queries matched to the actual Neo4j schema.

    All queries use parameterised inputs ($param) so they are safe
    against injection and work with the QueryExecutor.
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_query(
        self,
        query_type: str,
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Generate a Cypher query for a given intent.

        Args:
            query_type: One of the QueryType enum values (as string).
            params: Parameters needed for the query.

        Returns:
            {
                'query': str | None,
                'parameters': dict | None,
                'explanation': str,
                'query_type': str,
                'error': str | None
            }
        """
        # Validate
        try:
            qt = QueryType(query_type)
        except ValueError:
            return self._error(f"Unknown query type: {query_type}")

        # Dispatch
        dispatch = {
            # Safety
            QueryType.SUPPLEMENT_MEDICATION_INTERACTION: self._supplement_medication_interaction,
            QueryType.SUPPLEMENT_DRUG_INTERACTION: self._supplement_drug_interaction,
            QueryType.HIDDEN_PHARMA_EQUIVALENCE: self._hidden_pharma_equivalence,
            QueryType.SIMILAR_EFFECT_OVERLAP: self._similar_effect_overlap,
            QueryType.DRUG_DRUG_INTERACTION: self._drug_drug_interaction,
            QueryType.COMPREHENSIVE_SAFETY: self._comprehensive_safety,
            # Info / side-effects
            QueryType.FOOD_INTERACTIONS: self._food_interactions,
            QueryType.SUPPLEMENT_SIDE_EFFECTS: self._supplement_side_effects,
            # Recommendations
            QueryType.SUPPLEMENTS_FOR_SYMPTOM: self._supplements_for_symptom,
            QueryType.SUPPLEMENT_INFO: self._supplement_info,
            # Lookup
            QueryType.FIND_SUPPLEMENT: self._find_supplement,
            QueryType.FIND_MEDICATION: self._find_medication,
            QueryType.FIND_DRUG: self._find_drug,
        }

        handler = dispatch.get(qt)
        if handler is None:
            return self._error(f"No handler for query type: {query_type}")

        try:
            result = handler(params)
            result['query_type'] = query_type
            result.setdefault('error', None)
            return result
        except Exception as exc:
            return self._error(f"Error generating query: {exc}")

    def generate_multi_query(
        self,
        query_type: str,
        params: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Some intents need multiple queries (e.g. comprehensive safety).
        This always returns a *list* of query dicts.
        """
        result = self.generate_query(query_type, params)
        # comprehensive_safety already returns a list via _comprehensive_safety
        if isinstance(result.get('query'), list):
            # Expand into individual query dicts
            queries = []
            for i, q in enumerate(result['query']):
                queries.append({
                    'query': q,
                    'parameters': result['parameters'],
                    'explanation': f"{result['explanation']} (query {i+1})",
                    'query_type': query_type,
                    'error': None,
                })
            return queries
        return [result]

    # ------------------------------------------------------------------
    # SAFETY QUERIES
    # ------------------------------------------------------------------

    def _supplement_medication_interaction(self, params: Dict) -> Dict:
        """
        Direct Supplement -[:INTERACTS_WITH]-> Medication

        params: supplement_name, medication_names (list)
        """
        supp = params.get('supplement_name', '')
        meds = self._ensure_list(params.get('medication_names', params.get('medication_name', [])))

        if not supp or not meds:
            return self._error("Need supplement_name and medication_names")

        query = """
MATCH (s:Supplement)-[r:INTERACTS_WITH]->(m:Medication)
WHERE toLower(s.supplement_name) = toLower($supplement_name)
  AND toLower(m.medication_name) IN $medication_names_lower
RETURN s.supplement_name AS supplement,
       m.medication_name  AS medication,
       r.description      AS description,
       r.severity         AS severity,
       r.confidence        AS confidence,
       'DIRECT_SUPPLEMENT_MEDICATION' AS interaction_type
"""
        return {
            'query': query.strip(),
            'parameters': {
                'supplement_name': supp,
                'medication_names_lower': [m.lower() for m in meds],
            },
            'explanation': f"Checking direct interactions between {supp} and medications: {', '.join(meds)}",
        }

    def _supplement_drug_interaction(self, params: Dict) -> Dict:
        """
        Supplement -[:INTERACTS_WITH]-> Drug
        Also checks via Medication -[:CONTAINS_DRUG]-> Drug

        params: supplement_name, medication_names (list)
        """
        supp = params.get('supplement_name', '')
        meds = self._ensure_list(params.get('medication_names', params.get('medication_name', [])))

        if not supp or not meds:
            return self._error("Need supplement_name and medication_names")

        query = """
// Path: Supplement interacts with Drug, Drug is contained in Medication
MATCH (s:Supplement)-[r:INTERACTS_WITH]->(d:Drug)<-[:CONTAINS_DRUG]-(m:Medication)
WHERE toLower(s.supplement_name) = toLower($supplement_name)
  AND toLower(m.medication_name) IN $medication_names_lower
RETURN s.supplement_name AS supplement,
       d.drug_name       AS drug,
       m.medication_name  AS medication,
       r.description      AS description,
       r.severity         AS severity,
       'SUPPLEMENT_DRUG_MEDICATION' AS interaction_type
"""
        return {
            'query': query.strip(),
            'parameters': {
                'supplement_name': supp,
                'medication_names_lower': [m.lower() for m in meds],
            },
            'explanation': (
                f"Checking {supp} interactions with drugs contained in medications: "
                f"{', '.join(meds)}"
            ),
        }

    def _hidden_pharma_equivalence(self, params: Dict) -> Dict:
        """
        Supplement -[:CONTAINS]-> ActiveIngredient -[:EQUIVALENT_TO]-> Drug
        <- [:CONTAINS_DRUG]- Medication

        Detects hidden pharmaceutical duplication (e.g. Red Yeast Rice
        contains Monacolin K which is equivalent to Lovastatin).

        params: supplement_name, medication_names (list, optional)
        """
        supp = params.get('supplement_name', '')
        meds = self._ensure_list(params.get('medication_names', params.get('medication_name', [])))

        if not supp:
            return self._error("Need supplement_name")

        # If user has medications, check for duplication risk
        if meds:
            query = """
MATCH (s:Supplement)-[:CONTAINS]->(a:ActiveIngredient)-[:EQUIVALENT_TO]->(d:Drug)
WHERE toLower(s.supplement_name) = toLower($supplement_name)
OPTIONAL MATCH (m:Medication)-[:CONTAINS_DRUG]->(d)
WHERE toLower(m.medication_name) IN $medication_names_lower
RETURN s.supplement_name        AS supplement,
       a.active_ingredient       AS active_ingredient,
       d.drug_name               AS equivalent_drug,
       d.drug_id                 AS drug_id,
       m.medication_name          AS medication,
       a.equivalence_type         AS equivalence_type,
       CASE WHEN m IS NOT NULL
            THEN 'DUPLICATION_RISK'
            ELSE 'HIDDEN_PHARMA'
       END                        AS interaction_type
"""
            parameters = {
                'supplement_name': supp,
                'medication_names_lower': [m.lower() for m in meds],
            }
        else:
            # No medications - just show what the supplement contains
            query = """
MATCH (s:Supplement)-[:CONTAINS]->(a:ActiveIngredient)-[:EQUIVALENT_TO]->(d:Drug)
WHERE toLower(s.supplement_name) = toLower($supplement_name)
RETURN s.supplement_name        AS supplement,
       a.active_ingredient       AS active_ingredient,
       d.drug_name               AS equivalent_drug,
       d.drug_id                 AS drug_id,
       'HIDDEN_PHARMA'            AS interaction_type
"""
            parameters = {'supplement_name': supp}

        return {
            'query': query.strip(),
            'parameters': parameters,
            'explanation': (
                f"Checking if {supp} contains active ingredients equivalent to "
                f"prescription drugs"
                + (f" (user takes: {', '.join(meds)})" if meds else "")
            ),
        }

    def _similar_effect_overlap(self, params: Dict) -> Dict:
        """
        Supplement -[:HAS_SIMILAR_EFFECT_TO]-> Category <-[:BELONGS_TO]- Drug
        <- [:CONTAINS_DRUG]- Medication

        Detects additive / antagonistic pharmacological effects.

        params: supplement_name, medication_names (list)
        """
        supp = params.get('supplement_name', '')
        meds = self._ensure_list(params.get('medication_names', params.get('medication_name', [])))

        if not supp or not meds:
            return self._error("Need supplement_name and medication_names")

        query = """
MATCH (s:Supplement)-[:HAS_SIMILAR_EFFECT_TO]->(c:Category)
      <-[:BELONGS_TO]-(d:Drug)<-[:CONTAINS_DRUG]-(m:Medication)
WHERE toLower(s.supplement_name) = toLower($supplement_name)
  AND toLower(m.medication_name) IN $medication_names_lower
RETURN s.supplement_name AS supplement,
       c.category        AS shared_category,
       d.drug_name       AS drug,
       m.medication_name  AS medication,
       'SIMILAR_EFFECT'   AS interaction_type
"""
        return {
            'query': query.strip(),
            'parameters': {
                'supplement_name': supp,
                'medication_names_lower': [m.lower() for m in meds],
            },
            'explanation': (
                f"Checking if {supp} has similar pharmacological effects to drugs in "
                f"medications: {', '.join(meds)}"
            ),
        }

    def _drug_drug_interaction(self, params: Dict) -> Dict:
        """
        Drug -[:INTERACTS_WITH]-> Drug (via Medication nodes)

        params: medication_names (list of at least 2)
        """
        meds = self._ensure_list(params.get('medication_names', []))
        if len(meds) < 2:
            return self._error("Need at least 2 medication_names for drug-drug interaction check")

        query = """
MATCH (m1:Medication)-[:CONTAINS_DRUG]->(d1:Drug)
      -[r:INTERACTS_WITH]->(d2:Drug)<-[:CONTAINS_DRUG]-(m2:Medication)
WHERE toLower(m1.medication_name) IN $medication_names_lower
  AND toLower(m2.medication_name) IN $medication_names_lower
  AND m1 <> m2
RETURN m1.medication_name AS medication_1,
       d1.drug_name       AS drug_1,
       m2.medication_name AS medication_2,
       d2.drug_name       AS drug_2,
       r.description      AS description,
       'DRUG_DRUG'         AS interaction_type
"""
        return {
            'query': query.strip(),
            'parameters': {
                'medication_names_lower': [m.lower() for m in meds],
            },
            'explanation': f"Checking drug-drug interactions among: {', '.join(meds)}",
        }

    def _comprehensive_safety(self, params: Dict) -> Dict:
        """
        Run ALL safety pathways in one UNION query.

        This is the main query agents should use for a complete safety check.

        params: supplement_name, medication_names (list)
        """
        supp = params.get('supplement_name', '')
        meds = self._ensure_list(params.get('medication_names', params.get('medication_name', [])))

        if not supp or not meds:
            return self._error("Need supplement_name and medication_names")

        query = """
// === PATH 1: Direct Supplement -> Medication interaction ===
MATCH (s:Supplement)-[r:INTERACTS_WITH]->(m:Medication)
WHERE toLower(s.supplement_name) = toLower($supplement_name)
  AND toLower(m.medication_name) IN $medication_names_lower
RETURN s.supplement_name AS supplement,
       m.medication_name  AS target,
       r.description      AS description,
       r.severity         AS severity,
       null               AS detail,
       'DIRECT_SUPPLEMENT_MEDICATION' AS pathway

UNION

// === PATH 2: Supplement -> Drug <- Medication ===
MATCH (s:Supplement)-[r:INTERACTS_WITH]->(d:Drug)<-[:CONTAINS_DRUG]-(m:Medication)
WHERE toLower(s.supplement_name) = toLower($supplement_name)
  AND toLower(m.medication_name) IN $medication_names_lower
RETURN s.supplement_name AS supplement,
       m.medication_name  AS target,
       r.description      AS description,
       r.severity         AS severity,
       d.drug_name        AS detail,
       'SUPPLEMENT_DRUG_MEDICATION' AS pathway

UNION

// === PATH 3: Hidden pharma equivalence ===
MATCH (s:Supplement)-[:CONTAINS]->(a:ActiveIngredient)
      -[:EQUIVALENT_TO]->(d:Drug)<-[:CONTAINS_DRUG]-(m:Medication)
WHERE toLower(s.supplement_name) = toLower($supplement_name)
  AND toLower(m.medication_name) IN $medication_names_lower
RETURN s.supplement_name        AS supplement,
       m.medication_name         AS target,
       'Contains equivalent pharmaceutical ingredient - duplication risk' AS description,
       'HIGH'                     AS severity,
       a.active_ingredient + ' = ' + d.drug_name AS detail,
       'HIDDEN_PHARMA_EQUIVALENCE' AS pathway

UNION

// === PATH 4: Similar pharmacological effect ===
MATCH (s:Supplement)-[:HAS_SIMILAR_EFFECT_TO]->(c:Category)
      <-[:BELONGS_TO]-(d:Drug)<-[:CONTAINS_DRUG]-(m:Medication)
WHERE toLower(s.supplement_name) = toLower($supplement_name)
  AND toLower(m.medication_name) IN $medication_names_lower
RETURN s.supplement_name AS supplement,
       m.medication_name  AS target,
       'Similar pharmacological effect - additive or antagonistic risk' AS description,
       'MODERATE'          AS severity,
       c.category          AS detail,
       'SIMILAR_EFFECT'    AS pathway
"""
        return {
            'query': query.strip(),
            'parameters': {
                'supplement_name': supp,
                'medication_names_lower': [m.lower() for m in meds],
            },
            'explanation': (
                f"Comprehensive safety check: {supp} against "
                f"{', '.join(meds)} across all interaction pathways"
            ),
        }

    # ------------------------------------------------------------------
    # INFO / SIDE-EFFECT QUERIES
    # ------------------------------------------------------------------

    def _food_interactions(self, params: Dict) -> Dict:
        """
        Drug -[:HAS_FOOD_INTERACTION]-> FoodInteraction

        params: medication_name (single) or medication_names (list)
        """
        meds = self._ensure_list(
            params.get('medication_names', params.get('medication_name', []))
        )
        if not meds:
            return self._error("Need medication_name(s)")

        query = """
MATCH (m:Medication)-[:CONTAINS_DRUG]->(d:Drug)-[:HAS_FOOD_INTERACTION]->(fi:FoodInteraction)
WHERE toLower(m.medication_name) IN $medication_names_lower
RETURN m.medication_name  AS medication,
       d.drug_name        AS drug,
       fi.description     AS food_interaction,
       fi.food_interaction_id AS interaction_id
"""
        return {
            'query': query.strip(),
            'parameters': {
                'medication_names_lower': [m.lower() for m in meds],
            },
            'explanation': f"Checking food interactions for: {', '.join(meds)}",
        }

    def _supplement_side_effects(self, params: Dict) -> Dict:
        """
        Supplement -[:CAN_CAUSE]-> Symptom

        params: supplement_name
        """
        supp = params.get('supplement_name', '')
        if not supp:
            return self._error("Need supplement_name")

        query = """
MATCH (s:Supplement)-[:CAN_CAUSE]->(sym:Symptom)
WHERE toLower(s.supplement_name) = toLower($supplement_name)
RETURN s.supplement_name AS supplement,
       sym.symptom_id    AS symptom_id,
       sym.description   AS symptom
"""
        return {
            'query': query.strip(),
            'parameters': {'supplement_name': supp},
            'explanation': f"Finding potential side effects of {supp}",
        }

    # ------------------------------------------------------------------
    # RECOMMENDATION QUERIES
    # ------------------------------------------------------------------

    def _supplements_for_symptom(self, params: Dict) -> Dict:
        """
        Supplement -[:TREATS]-> Symptom

        params: symptom (keyword or description)
        """
        symptom = params.get('symptom', params.get('condition', ''))
        if not symptom:
            return self._error("Need symptom or condition keyword")

        query = """
MATCH (s:Supplement)-[:TREATS]->(sym:Symptom)
WHERE toLower(sym.description) CONTAINS toLower($symptom)
   OR toLower(sym.symptom_id)  CONTAINS toLower($symptom)
RETURN s.supplement_name  AS supplement,
       s.supplement_id    AS supplement_id,
       sym.description    AS symptom,
       s.safety_rating    AS safety_rating,
       s.description      AS supplement_description
"""
        return {
            'query': query.strip(),
            'parameters': {'symptom': symptom},
            'explanation': f"Finding supplements that may help with: {symptom}",
        }

    def _supplement_info(self, params: Dict) -> Dict:
        """
        Get detailed info about a supplement: what it contains,
        what it treats, what it can cause, what categories it overlaps with.

        params: supplement_name
        """
        supp = params.get('supplement_name', '')
        if not supp:
            return self._error("Need supplement_name")

        query = """
MATCH (s:Supplement)
WHERE toLower(s.supplement_name) = toLower($supplement_name)

// What active ingredients does it contain?
OPTIONAL MATCH (s)-[:CONTAINS]->(a:ActiveIngredient)
OPTIONAL MATCH (a)-[:EQUIVALENT_TO]->(d:Drug)

// What symptoms does it treat?
OPTIONAL MATCH (s)-[:TREATS]->(treats:Symptom)

// What side effects can it cause?
OPTIONAL MATCH (s)-[:CAN_CAUSE]->(causes:Symptom)

// What drug categories does it resemble?
OPTIONAL MATCH (s)-[:HAS_SIMILAR_EFFECT_TO]->(cat:Category)

RETURN s.supplement_name        AS supplement,
       s.supplement_id          AS supplement_id,
       s.description            AS description,
       s.safety_rating          AS safety_rating,
       collect(DISTINCT a.active_ingredient) AS active_ingredients,
       collect(DISTINCT d.drug_name)         AS equivalent_drugs,
       collect(DISTINCT treats.description)  AS treats_symptoms,
       collect(DISTINCT causes.description)  AS side_effects,
       collect(DISTINCT cat.category)        AS similar_effect_categories
"""
        return {
            'query': query.strip(),
            'parameters': {'supplement_name': supp},
            'explanation': f"Getting detailed information about {supp}",
        }

    # ------------------------------------------------------------------
    # LOOKUP / UTILITY QUERIES
    # ------------------------------------------------------------------

    def _find_supplement(self, params: Dict) -> Dict:
        """Fuzzy-find supplement by name."""
        name = params.get('supplement_name', params.get('name', ''))
        if not name:
            return self._error("Need supplement_name or name")

        query = """
MATCH (s:Supplement)
WHERE toLower(s.supplement_name) CONTAINS toLower($name)
RETURN s.supplement_id   AS supplement_id,
       s.supplement_name AS supplement_name,
       s.safety_rating   AS safety_rating,
       s.description     AS description
LIMIT 10
"""
        return {
            'query': query.strip(),
            'parameters': {'name': name},
            'explanation': f"Looking up supplement: {name}",
        }

    def _find_medication(self, params: Dict) -> Dict:
        """Fuzzy-find medication by name."""
        name = params.get('medication_name', params.get('name', ''))
        if not name:
            return self._error("Need medication_name or name")

        query = """
MATCH (m:Medication)
WHERE toLower(m.medication_name) CONTAINS toLower($name)
RETURN m.medication_id   AS medication_id,
       m.medication_name AS medication_name
LIMIT 10
"""
        return {
            'query': query.strip(),
            'parameters': {'name': name},
            'explanation': f"Looking up medication: {name}",
        }

    def _find_drug(self, params: Dict) -> Dict:
        """Fuzzy-find drug by name, brand name, or synonym."""
        name = params.get('drug_name', params.get('name', ''))
        if not name:
            return self._error("Need drug_name or name")

        query = """
// Direct drug name match
MATCH (d:Drug)
WHERE toLower(d.drug_name) CONTAINS toLower($name)
RETURN d.drug_id     AS drug_id,
       d.drug_name   AS drug_name,
       'drug_name'   AS match_type
LIMIT 5

UNION

// Brand name match
MATCH (b:BrandName)-[:CONTAINS_DRUG]->(d:Drug)
WHERE toLower(b.brand_name) CONTAINS toLower($name)
RETURN d.drug_id     AS drug_id,
       d.drug_name   AS drug_name,
       'brand_name'  AS match_type
LIMIT 5

UNION

// Synonym match
MATCH (d:Drug)-[:KNOWN_AS]->(syn:Synonym)
WHERE toLower(syn.synonym) CONTAINS toLower($name)
RETURN d.drug_id     AS drug_id,
       d.drug_name   AS drug_name,
       'synonym'     AS match_type
LIMIT 5
"""
        return {
            'query': query.strip(),
            'parameters': {'name': name},
            'explanation': f"Looking up drug (name/brand/synonym): {name}",
        }

    # ------------------------------------------------------------------
    # HELPERS
    # ------------------------------------------------------------------

    @staticmethod
    def _ensure_list(value) -> List[str]:
        """Normalise a value to a list of strings."""
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        return list(value)

    @staticmethod
    def _error(message: str) -> Dict:
        return {
            'query': None,
            'parameters': None,
            'explanation': message,
            'error': message,
        }


# ======================================================================
# Convenience functions for agents
# ======================================================================

def generate_safety_queries(
    supplement_name: str,
    medication_names: List[str],
) -> List[Dict]:
    """
    Generate the full set of safety queries for a supplement + medications.

    Returns a list of query dicts ready for QueryExecutor.execute_multiple().
    """
    gen = QueryGenerator()
    params = {
        'supplement_name': supplement_name,
        'medication_names': medication_names,
    }

    queries = []

    # 1. Direct supplement -> medication
    queries.append(gen.generate_query('supplement_medication_interaction', params))

    # 2. Supplement -> drug <- medication
    queries.append(gen.generate_query('supplement_drug_interaction', params))

    # 3. Hidden pharma (supplement -> active ingredient -> drug <- medication)
    queries.append(gen.generate_query('hidden_pharma_equivalence', params))

    # 4. Similar effects (supplement -> category <- drug <- medication)
    queries.append(gen.generate_query('similar_effect_overlap', params))

    # Filter out any that errored
    return [q for q in queries if q.get('query') is not None]


def generate_comprehensive_safety_query(
    supplement_name: str,
    medication_names: List[str],
) -> Dict:
    """
    Generate a single UNION query that checks ALL safety pathways at once.

    More efficient than running 4 separate queries.
    """
    gen = QueryGenerator()
    return gen.generate_query('comprehensive_safety', {
        'supplement_name': supplement_name,
        'medication_names': medication_names,
    })


def generate_supplement_info_query(supplement_name: str) -> Dict:
    """Quick helper to get full supplement details."""
    gen = QueryGenerator()
    return gen.generate_query('supplement_info', {
        'supplement_name': supplement_name,
    })


def generate_symptom_recommendation_query(symptom: str) -> Dict:
    """Quick helper to find supplements for a symptom."""
    gen = QueryGenerator()
    return gen.generate_query('supplements_for_symptom', {
        'symptom': symptom,
    })


# ======================================================================
# Quick self-test
# ======================================================================

if __name__ == "__main__":
    gen = QueryGenerator()

    print("=" * 60)
    print("QUERY GENERATOR - SELF TEST")
    print("=" * 60)

    # 1. Comprehensive safety
    print("\n--- Comprehensive Safety Query ---")
    result = gen.generate_query('comprehensive_safety', {
        'supplement_name': 'Fish Oil',
        'medication_names': ['Warfarin', 'Aspirin'],
    })
    print(f"Explanation: {result['explanation']}")
    print(f"Query:\n{result['query'][:300]}...")
    print(f"Params: {result['parameters']}")

    # 2. Hidden pharma
    print("\n--- Hidden Pharma Equivalence ---")
    result = gen.generate_query('hidden_pharma_equivalence', {
        'supplement_name': 'Red Yeast Rice',
        'medication_names': ['Lipitor'],
    })
    print(f"Explanation: {result['explanation']}")
    print(f"Query:\n{result['query'][:300]}...")

    # 3. Supplement info
    print("\n--- Supplement Info ---")
    result = gen.generate_query('supplement_info', {
        'supplement_name': "St. John's Wort",
    })
    print(f"Explanation: {result['explanation']}")
    print(f"Query:\n{result['query'][:300]}...")

    # 4. Find drug
    print("\n--- Find Drug ---")
    result = gen.generate_query('find_drug', {'name': 'Warfarin'})
    print(f"Explanation: {result['explanation']}")
    print(f"Query:\n{result['query'][:300]}...")

    # 5. Convenience function
    print("\n--- Safety Queries (convenience) ---")
    queries = generate_safety_queries('Fish Oil', ['Warfarin'])
    print(f"Generated {len(queries)} safety queries")
    for i, q in enumerate(queries):
        print(f"  {i+1}. {q['explanation']}")

    print("\n✅ All queries generated successfully!")
