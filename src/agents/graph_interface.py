"""
Neo4j Graph Database Interface for Supplement Safety Knowledge Graph

Provides simplified access to the supplement-drug interaction database.
"""

import logging
from typing import Any, Dict, List, Optional

from neo4j import GraphDatabase

logger = logging.getLogger(__name__)


class GraphInterface:
    """
    Thread-safe Neo4j database wrapper for supplement safety queries.
    
    Handles connections to the knowledge graph containing:
    - Supplements, ActiveIngredients, Medications, Drugs
    - Drug interactions, equivalence relationships, category similarities
    """

    def __init__(self, uri: str, user: str, password: str):
        """
        Initialize Neo4j connection.
        
        Args:
            uri: Neo4j connection URI (e.g., "bolt://localhost:7687")
            user: Database username (usually "neo4j")
            password: Database password
        """
        try:
            self.driver = GraphDatabase.driver(uri, auth=(user, password))
            # Test connection
            with self.driver.session() as session:
                session.run("RETURN 1")
            logger.info("Connected to Neo4j database")
        except Exception as e:
            logger.error("Failed to connect to Neo4j: %s", e)
            raise

    def close(self):
        """Close database connection."""
        if getattr(self, "driver", None):
            self.driver.close()
            logger.info("Neo4j connection closed")

    def execute_query(
        self, 
        cypher_query: str, 
        parameters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Execute a Cypher query and return results as list of dictionaries.
        
        Args:
            cypher_query: Cypher query string
            parameters: Optional parameters for the query
            
        Returns:
            List of result records as dictionaries
            
        Raises:
            Exception: If query execution fails
        """
        parameters = parameters or {}
        try:
            with self.driver.session() as session:
                result = session.run(cypher_query, parameters)
                return [record.data() for record in result]
        except Exception as e:
            logger.error("Query execution failed: %s", e)
            logger.debug("Cypher: %s", cypher_query)
            raise

    def get_schema_info(self) -> Dict[str, Any]:
        """
        Get database schema information.
        
        Returns:
            Dictionary with node labels, relationship types, and properties
        """
        node_labels = []
        relationship_types = []
        node_properties = {}
        relationship_properties = {}

        with self.driver.session() as session:
            try:
                labels_res = session.run("CALL db.labels() YIELD label RETURN collect(label) as labels").single()
                types_res = session.run(
                    "CALL db.relationshipTypes() YIELD relationshipType RETURN collect(relationshipType) as types"
                ).single()

                node_labels = labels_res["labels"] if labels_res else []
                relationship_types = types_res["types"] if types_res else []
            except Exception as e:
                logger.debug("Failed to fetch labels or relationship types: %s", e)

            for label in node_labels:
                try:
                    q = f"MATCH (n:{label}) RETURN keys(n) as props LIMIT 1"
                    r = session.run(q).single()
                    if r:
                        node_properties[label] = r["props"]
                except Exception:
                    continue

            for rel in relationship_types:
                try:
                    q = f"MATCH ()-[r:{rel}]->() RETURN keys(r) as props LIMIT 1"
                    r = session.run(q).single()
                    if r:
                        relationship_properties[rel] = r["props"]
                except Exception:
                    continue

        return {
            "node_labels": node_labels,
            "relationship_types": relationship_types,
            "node_properties": node_properties,
            "relationship_properties": relationship_properties,
        }

    def get_property_values(
        self, 
        label: str, 
        property_name: str, 
        limit: int = 20
    ) -> List[Any]:
        """
        Get distinct values for a property across nodes of a given label.
        
        Args:
            label: Node label (e.g., "Supplement", "Drug")
            property_name: Property to get values for
            limit: Maximum number of values to return
            
        Returns:
            List of distinct property values
        """
        try:
            query = (
                f"MATCH (n:{label}) WHERE n.{property_name} IS NOT NULL "
                f"RETURN DISTINCT n.{property_name} as value LIMIT {limit}"
            )
            with self.driver.session() as session:
                result = session.run(query)
                return [record["value"] for record in result]
        except Exception as e:
            logger.warning("Could not get property values for %s.%s: %s", label, property_name, e)
            return []

    def check_supplement_drug_interaction(
        self, 
        supplement_names: List[str], 
        medication_names: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Check for interactions between supplements and medications.
        
        This is a specialized query for the most common use case:
        detecting dangerous interactions.
        
        Args:
            supplement_names: List of supplement names
            medication_names: List of medication names
            
        Returns:
            List of interaction records with severity and details
        """
        query = """
        // Check for direct supplement-medication interactions
        MATCH (s:Supplement)-[i:SUPPLEMENT_INTERACTS_WITH]->(m:Medication)
        WHERE s.supplement_name IN $supplement_names
          AND m.medication_name IN $medication_names
        RETURN 
            s.supplement_name as supplement,
            m.medication_name as medication,
            i.interaction_description as description,
            'DIRECT' as interaction_type
        
        UNION
        
        // Check for drug equivalence (supplement contains same drug)
        MATCH (s:Supplement)-[:CONTAINS]->(a:ActiveIngredient)
              -[:EQUIVALENT_TO]->(d:Drug)<-[:MEDICATION_CONTAINS_DRUG]-(m:Medication)
        WHERE s.supplement_name IN $supplement_names
          AND m.medication_name IN $medication_names
        RETURN 
            s.supplement_name as supplement,
            m.medication_name as medication,
            'Contains equivalent drug - risk of double dosing' as description,
            'EQUIVALENCE' as interaction_type
        
        UNION
        
        // Check for similar pharmacological effects
        MATCH (s:Supplement)-[:HAS_SIMILAR_EFFECT_TO]->(c:Category)
              <-[:BELONGS_TO]-(d:Drug)<-[:MEDICATION_CONTAINS_DRUG]-(m:Medication)
        WHERE s.supplement_name IN $supplement_names
          AND m.medication_name IN $medication_names
        RETURN 
            s.supplement_name as supplement,
            m.medication_name as medication,
            'Has similar effects - may cause additive or antagonistic effects' as description,
            'SIMILAR_EFFECT' as interaction_type
        """
        
        return self.execute_query(query, {
            'supplement_names': supplement_names,
            'medication_names': medication_names
        })

    def validate_query(self, cypher_query: str) -> bool:
        """
        Validate Cypher query syntax without executing it.
        
        Args:
            cypher_query: Query to validate
            
        Returns:
            True if valid, False otherwise
        """
        try:
            with self.driver.session() as session:
                session.run(f"EXPLAIN {cypher_query}")
                return True
        except Exception as e:
            logger.warning(f"Query validation failed: {e}")
            return False