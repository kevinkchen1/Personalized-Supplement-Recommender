#!/usr/bin/env python3
"""
Neo4j Supplement Knowledge Graph Data Loader

This script populates a Neo4j graph database with structured supplement data
including supplements, medications, symptoms, and their relationships.

The script handles:
- Entity creation (supplements, medications, symptoms)
- Relationship establishment (interacts_with, could_cause, treats)
- Database constraints for data integrity
- Complete database rebuild with cleanup

Data Sources:
    Reads CSV files from the data/ directory:
    - supplements.csv: Supplement entities with safety ratings
    - medications.csv: Medication entities
    - symptoms.csv: Symptom entities
    - supplement_medication_interacts_with.csv: Supplement-medication interactions
    - supplement_symptom_can_cause.csv: Supplement-symptom adverse effects
    - supplement_symptom_treats.csv: Supplement-symptom treatment relationships

Usage:
    python load_supplement_data.py

Environment Variables:
    NEO4J_URI: Database connection URI (default: bolt://localhost:7687)
    NEO4J_USER: Database username (default: neo4j)
    NEO4J_PASSWORD: Database password (required)
"""

import logging
import os

import pandas as pd
from dotenv import load_dotenv
from neo4j import GraphDatabase

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class SupplementDataLoader:
    """
    A data loader for populating Neo4j with supplement knowledge graph data.

    This class manages the complete process of loading structured supplement data
    into a Neo4j graph database. It handles entity creation, relationship establishment,
    constraint management, and data integrity verification.

    The loader creates a knowledge graph with the following schema:
    - Nodes: Supplement, Medication, Symptom
    - Relationships: INTERACTS_WITH, COULD_CAUSE, TREATS

    Example:
        >>> loader = SupplementDataLoader("bolt://localhost:7687", "neo4j", "password")
        >>> loader.clear_database()
        >>> loader.create_constraints()
        >>> loader.load_supplements(supplements_df)
        >>> loader.close()
    """

    def __init__(self, uri: str, user: str, password: str):
        """
        Initialize the data loader with Neo4j database connection.

        Args:
            uri: Neo4j connection URI (e.g., "bolt://localhost:7687")
            user: Database username (typically "neo4j")
            password: Database password

        Raises:
            Exception: If connection to Neo4j fails
        """
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        logger.info("Connected to Neo4j database")

    def close(self):
        """
        Close the database connection and release resources.

        Should be called when data loading is complete to ensure proper
        cleanup of database connections.
        """
        self.driver.close()

    def clear_database(self):
        """
        Clear all existing data from the database.

        This method removes all nodes and relationships from the Neo4j database,
        providing a clean slate for fresh data loading. Use with caution as this
        operation is irreversible.

        Warning:
            This will permanently delete ALL data in the database.
            Ensure you have backups if needed before running.
        """
        with self.driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
            logger.info("Cleared existing database")

    def create_constraints(self):
        """
        Create uniqueness constraints for optimal database performance.

        Establishes unique constraints on primary identifier fields for each
        node type. These constraints:
        - Prevent duplicate entities with the same name
        - Create automatic indexes for fast lookups
        - Ensure data integrity during bulk loading
        - Improve query performance for relationship creation

        Constraints Created:
            - Supplement.name: Ensures unique supplement names
            - Medication.name: Ensures unique medication names
            - Symptom.name: Ensures unique symptom names
        """
        constraints = [
            "CREATE CONSTRAINT IF NOT EXISTS FOR (s:Supplement) "
            "REQUIRE s.name IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (m:Medication) "
            "REQUIRE m.name IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (sy:Symptom) "
            "REQUIRE sy.name IS UNIQUE",
        ]

        with self.driver.session() as session:
            for constraint in constraints:
                session.run(constraint)
            logger.info("Created database constraints")

    def load_supplements(self, df: pd.DataFrame):
        """
        Load supplement entities into the Neo4j database.

        Creates Supplement nodes with safety information and active ingredients.

        Args:
            df: DataFrame containing supplement data with columns:
                - supplement_id: Supplement ID
                - supplement_name: Supplement name (unique identifier)
                - safety_rating: Safety rating of the supplement
                - active_ingredient: Active ingredients in the supplement

        Node Properties Created:
            Each Supplement node includes safety and composition metadata.
        """
        with self.driver.session() as session:
            for _, row in df.iterrows():
                session.run(
                    """
                    CREATE (s:Supplement {
                        supplement_id: $supplement_id,
                        name: $name,
                        safety_rating: $safety_rating,
                        active_ingredients: $active_ingredients
                    })
                    """,
                    supplement_id=row["supplement_id"],
                    name=row["supplement_name"],
                    safety_rating=row["safety_rating"],
                    active_ingredients=row["active_ingredient"],
                )
            logger.info(f"Loaded {len(df)} supplements")

    def load_medications(self, df: pd.DataFrame):
        """
        Load medication entities into the Neo4j database.

        Creates Medication nodes.

        Args:
            df: DataFrame containing medication data with columns:
                - medication_id: Medication ID
                - medication_name: Medication name (unique identifier)

        Node Properties Created:
            Each Medication node includes ID and name.
        """
        with self.driver.session() as session:
            for _, row in df.iterrows():
                session.run(
                    """
                    CREATE (m:Medication {
                        medication_id: $medication_id,
                        name: $name
                    })
                    """,
                    medication_id=row["medication_id"],
                    name=row["medication_name"],
                )
            logger.info(f"Loaded {len(df)} medications")

    def load_symptoms(self, df: pd.DataFrame):
        """
        Load symptom entities into the Neo4j database.

        Creates Symptom nodes.

        Args:
            df: DataFrame containing symptom data with columns:
                - symptom_id: Symptom ID
                - symptom_name: Symptom name (unique identifier)

        Node Properties Created:
            Each Symptom node includes ID and name.
        """
        with self.driver.session() as session:
            for _, row in df.iterrows():
                session.run(
                    """
                    CREATE (sy:Symptom {
                        symptom_id: $symptom_id,
                        name: $name
                    })
                    """,
                    symptom_id=row["symptom_id"],
                    name=row["symptom_name"],
                )
            logger.info(f"Loaded {len(df)} symptoms")

    def load_supplement_medication_interactions(self, df: pd.DataFrame):
        """
        Load supplement-medication interaction relationships.

        Creates INTERACTS_WITH relationships between supplements and medications,
        representing potential drug-supplement interactions.

        Args:
            df: DataFrame containing interaction data with columns:
                - supplement_id: Reference to existing supplement
                - medication_id: Reference to existing medication

        Note:
            Requires both supplements and medications to be loaded first.
        """
        with self.driver.session() as session:
            for _, row in df.iterrows():
                session.run(
                    """
                    MATCH (s:Supplement {supplement_id: $supplement_id})
                    MATCH (m:Medication {medication_id: $medication_id})
                    CREATE (s)-[:INTERACTS_WITH]->(m)
                    """,
                    supplement_id=row["supplement_id"],
                    medication_id=row["medication_id"],
                )
            logger.info(f"Loaded {len(df)} supplement-medication interactions")

    def load_supplement_symptom_causes(self, df: pd.DataFrame):
        """
        Load supplement-symptom adverse effect relationships.

        Creates COULD_CAUSE relationships between supplements and symptoms,
        representing potential adverse effects.

        Args:
            df: DataFrame containing adverse effect data with columns:
                - supplement_id: Reference to existing supplement
                - symptom_id: Reference to existing symptom

        Note:
            Requires both supplements and symptoms to be loaded first.
        """
        with self.driver.session() as session:
            for _, row in df.iterrows():
                session.run(
                    """
                    MATCH (s:Supplement {supplement_id: $supplement_id})
                    MATCH (sy:Symptom {symptom_id: $symptom_id})
                    CREATE (s)-[:COULD_CAUSE]->(sy)
                    """,
                    supplement_id=row["supplement_id"],
                    symptom_id=row["symptom_id"],
                )
            logger.info(f"Loaded {len(df)} supplement-symptom adverse effects")

    def load_supplement_symptom_treatments(self, df: pd.DataFrame):
        """
        Load supplement-symptom treatment relationships.

        Creates TREATS relationships between supplements and symptoms,
        representing therapeutic uses of supplements.

        Args:
            df: DataFrame containing treatment data with columns:
                - supplement_id: Reference to existing supplement
                - symptom_id: Reference to existing symptom

        Note:
            Requires both supplements and symptoms to be loaded first.
        """
        with self.driver.session() as session:
            for _, row in df.iterrows():
                session.run(
                    """
                    MATCH (s:Supplement {supplement_id: $supplement_id})
                    MATCH (sy:Symptom {symptom_id: $symptom_id})
                    CREATE (s)-[:TREATS]->(sy)
                    """,
                    supplement_id=row["supplement_id"],
                    symptom_id=row["symptom_id"],
                )
            logger.info(f"Loaded {len(df)} supplement-symptom treatments")


def main():
    """
    Main entry point for loading supplement knowledge graph data into Neo4j.

    This function orchestrates the complete data loading process:
    1. Establishes database connection using environment variables
    2. Clears existing data for fresh loading
    3. Creates database constraints for performance
    4. Loads all entity types (supplements, medications, symptoms)
    5. Establishes all relationship types
    6. Handles errors gracefully with proper cleanup

    Environment Variables Required:
        NEO4J_PASSWORD: Database password (required)
        NEO4J_URI: Database URI (optional, defaults to bolt://localhost:7687)
        NEO4J_USER: Database username (optional, defaults to neo4j)

    Data Loading Order:
        The loading follows dependency order to ensure referential integrity:
        1. Entities: Supplements, Medications, Symptoms
        2. Relationships: Interactions, Adverse Effects, Treatments

    Raises:
        ValueError: If required environment variables are missing
        Exception: If database connection or data loading fails
    """
    # Get database credentials from environment
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD")

    if not password:
        raise ValueError("NEO4J_PASSWORD environment variable not set")

    # Initialize data loader
    loader = SupplementDataLoader(uri, user, password)

    try:
        # Phase 1: Database preparation
        logger.info("Starting database preparation...")
        loader.clear_database()
        loader.create_constraints()

        # Phase 2: Load entity data from CSV files
        # Use relative path from script location
        script_dir = os.path.dirname(os.path.abspath(__file__))
        data_dir = os.path.join(script_dir, "data")
        logger.info("Loading entity data...")

        # Load primary entities
        supplements_df = pd.read_csv(os.path.join(data_dir, "supplements.csv"))
        loader.load_supplements(supplements_df)

        medications_df = pd.read_csv(os.path.join(data_dir, "medications.csv"))
        loader.load_medications(medications_df)

        symptoms_df = pd.read_csv(os.path.join(data_dir, "symptoms.csv"))
        loader.load_symptoms(symptoms_df)

        # Phase 3: Load relationship data
        logger.info("Loading relationship data...")

        interactions_df = pd.read_csv(
            os.path.join(data_dir, "supplement_medication_interacts_with.csv")
        )
        loader.load_supplement_medication_interactions(interactions_df)

        causes_df = pd.read_csv(
            os.path.join(data_dir, "supplement_symptom_can_cause.csv")
        )
        loader.load_supplement_symptom_causes(causes_df)

        treatments_df = pd.read_csv(
            os.path.join(data_dir, "supplement_symptom_treats.csv")
        )
        loader.load_supplement_symptom_treatments(treatments_df)

        logger.info("Data loading completed successfully!")

    except Exception as e:
        logger.error(f"Error loading data: {e}")
        raise
    finally:
        # Ensure database connection is properly closed
        loader.close()


if __name__ == "__main__":
    main()