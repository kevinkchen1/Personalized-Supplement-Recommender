"""
Neo4j Biomedical Knowledge Graph Data Loader

This script populates a Neo4j graph database with structured biomedical data
including genes, proteins, diseases, drugs, and their complex relationships.
It creates a comprehensive knowledge graph suitable for AI-powered biomedical
query systems and research applications.

The script handles:
- Entity creation (genes, proteins, diseases, drugs)
- Relationship establishment (encodes, treats, targets, associations)
- Database constraints for data integrity
- Derived relationship computation (gene-disease links)
- Complete database rebuild with cleanup

Data Sources:
    Reads CSV files from the data/ directory:
    - genes.csv: Gene entities with chromosomal and functional information
    - proteins.csv: Protein entities with structural data
    - diseases.csv: Disease entities with prevalence and severity data
    - drugs.csv: Drug entities with approval status and mechanisms
    - protein_disease_associations.csv: Protein-disease relationships
    - drug_disease_treatments.csv: Drug treatment relationships
    - drug_protein_targets.csv: Drug-protein target interactions

Usage:
    python scripts/load_data.py

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


class Neo4jDataLoader:
    """
    A comprehensive data loader for populating Neo4j with biomedical knowledge
    graph data.

    This class manages the complete process of loading structured biomedical data
    into a Neo4j graph database. It handles entity creation, relationship establishment,
    constraint management, and data integrity verification.

    The loader creates a knowledge graph with the following schema:
    - Nodes: Gene, Protein, Disease, Drug
    - Relationships: ENCODES, ASSOCIATED_WITH, TREATS, TARGETS, LINKED_TO

    Features:
    - Transactional loading with proper error handling
    - Database constraint creation for performance optimization
    - Automated derived relationship computation
    - Complete database rebuilding capability
    - Progress logging throughout the loading process

    Example:
        >>> loader = Neo4jDataLoader("bolt://localhost:7687", "neo4j", "password")
        >>> loader.clear_database()
        >>> loader.create_constraints()
        >>> loader.load_genes(genes_df)
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
        - Prevent duplicate entities with the same ID
        - Create automatic indexes for fast lookups
        - Ensure data integrity during bulk loading
        - Improve query performance for relationship creation

        Constraints Created:
            - Gene.gene_id: Ensures unique gene identifiers
            - Protein.protein_id: Ensures unique protein identifiers
            - Disease.disease_id: Ensures unique disease identifiers
            - Drug.drug_id: Ensures unique drug identifiers
        """
        constraints = [
            "CREATE CONSTRAINT IF NOT EXISTS FOR (s:Supplement) "
            "REQUIRE s.supplement_id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (sy:Symptom) "
            "REQUIRE sy.symptom_id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (m:Medication) "
            "REQUIRE m.medication_id IS UNIQUE",
        ]

        with self.driver.session() as session:
            for constraint in constraints:
                session.run(constraint)
            logger.info("Created database constraints")

    def load_supplements(self, df: pd.DataFrame):
        """
        Load gene entities into the Neo4j database.

        Creates Gene nodes with comprehensive genomic information including
        chromosomal location, biological function, and expression levels.

        Args:
            df: DataFrame containing gene data with columns:
                - gene_id: Unique gene identifier
                - gene_name: Human-readable gene name/symbol
                - chromosome: Chromosomal location
                - function: Biological function description
                - expression_level: Gene expression level

        Node Properties Created:
            Each Gene node includes genomic metadata essential for
            biomedical research and pathway analysis.
        """
        with self.driver.session() as session:
            for _, row in df.iterrows():
                session.run(
                    """
                    CREATE (s:Supplement {
                        supplement_id: $supplement_id,
                        supplement_name: $supplement_name,
                        safety_level: $safety_level,
                        active_ingredient: $active_ingredient,
                    })
                    """,
                    supplement_id=row["supplement_id"],
                    supplement_name=row["supplement_name"],
                    safety_level=row["safety_level"],
                    active_ingredient=row["active_ingredient"],
                )
            logger.info(f"Loaded {len(df)} supplements")

    def load_symptoms(self, df: pd.DataFrame):
        """
        Load protein entities and establish gene-protein encoding relationships.

        Creates Protein nodes with structural information and simultaneously
        establishes ENCODES relationships from genes to proteins, representing
        the central dogma of molecular biology (DNA → RNA → Protein).

        Args:
            df: DataFrame containing protein data with columns:
                - protein_id: Unique protein identifier
                - protein_name: Human-readable protein name
                - molecular_weight: Protein molecular weight in kDa
                - structure_type: Protein structural classification
                - gene_id: Reference to encoding gene

        Creates:
            - Protein nodes with structural metadata
            - ENCODES relationships from genes to their encoded proteins

        Note:
            Requires genes to be loaded first since this creates relationships
            to existing Gene nodes.
        """
        with self.driver.session() as session:
            for _, row in df.iterrows():
                session.run(
                    """
                    CREATE (sy:Symptom {
                        symptom_id: $symptom_id,
                        symptom_name: $symptom_name,
                    })
                    """,
                    symptom_id=row["symptom_id"],
                    symptom_name=row["symptom_name"],
                )


    def load_medications(self, df: pd.DataFrame):
        """
        Load disease entities into the Neo4j database.

        Creates Disease nodes with epidemiological and clinical information
        including disease classification, population prevalence, and severity metrics.

        Args:
            df: DataFrame containing disease data with columns:
                - disease_id: Unique disease identifier
                - disease_name: Human-readable disease name
                - category: Disease classification (e.g., "metabolic", "neurological")
                - prevalence: Population prevalence rate
                - severity: Disease severity level

        Node Properties Created:
            Each Disease node includes clinical metadata essential for
            epidemiological analysis and treatment prioritization.
        """
        with self.driver.session() as session:
            for _, row in df.iterrows():
                session.run(
                    """
                    CREATE (m:Medication {
                        medication_id: $medication_id,
                        medication_name: $medication_name,
                    })
                    """,
                    medication_id=row["medication_id"],
                    medication_name=row["medication_name"],
                )
            logger.info(f"Loaded {len(df)} medications")


    def load_supplement_medication_interacts_with(self, df: pd.DataFrame):
        """
        Load drug-disease treatment relationships.

        Creates TREATS relationships between drugs and diseases,
        representing
        therapeutic interventions with clinical efficacy data and development
        stage information.

        Args:
            df: DataFrame containing treatment data with columns:
                - drug_id: Reference to existing drug
                - disease_id: Reference to existing disease
                - efficacy: Treatment efficacy level (e.g., "high", "medium", "low")
                - stage: Development stage (e.g., "approved", "phase_III",
                  "experimental")

        Relationship Properties:
            - efficacy: Clinical effectiveness of the treatment
            - stage: Regulatory approval or clinical trial stage

        Note:
            Requires both drugs and diseases to be loaded first.
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

    def load_supplement_symptom_can_cause(self, df: pd.DataFrame):
        """
        Load drug-protein target relationships.

        Creates TARGETS relationships between drugs and proteins, representing
        molecular interactions including binding affinity and interaction mechanisms.

        Args:
            df: DataFrame containing target data with columns:
                - drug_id: Reference to existing drug
                - protein_id: Reference to existing protein
                - interaction_type: Type of interaction (e.g., "inhibitor", "agonist")
                - affinity: Binding affinity strength

        Relationship Properties:
            - interaction_type: Mechanism of drug-protein interaction
            - affinity: Strength of molecular binding

        Note:
            Requires both drugs and proteins to be loaded first.
        """
        with self.driver.session() as session:
            for _, row in df.iterrows():
                session.run(
                    """
                    MATCH (s:Supplement {supplement_id: $supplement_id})
                    MATCH (sy:Symptom {symptom_id: $symptom_id})
                    CREATE (s)-[:CAN_CAUSE]->(sy)
                    """,
                    supplement_id=row["supplement_id"],
                    symptom_id=row["symptom_id"],
                )
            logger.info(f"Loaded {len(df)} supplement-symptom can cause relationships")
            
    def load_supplement_symptom_treats(self, df: pd.DataFrame):
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
            logger.info(f"Loaded {len(df)} supplement-symptom treats relationships")


def main():
    """
    Main entry point for loading biomedical knowledge graph data into Neo4j.

    This function orchestrates the complete data loading process:
    1. Establishes database connection using environment variables
    2. Clears existing data for fresh loading
    3. Creates database constraints for performance
    4. Loads all entity types (genes, proteins, diseases, drugs)
    5. Establishes all relationship types
    6. Computes derived relationships
    7. Handles errors gracefully with proper cleanup

    Environment Variables Required:
        NEO4J_PASSWORD: Database password (required)
        NEO4J_URI: Database URI (optional, defaults to bolt://localhost:7687)
        NEO4J_USER: Database username (optional, defaults to neo4j)

    Data Loading Order:
        The loading follows dependency order to ensure referential integrity:
        1. Entities: Genes → Proteins → Diseases → Drugs
        2. Direct relationships: Gene-Protein, Protein-Disease, Drug-Disease,
                                Drug-Protein
        3. Derived relationships: Gene-Disease links

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
    loader = Neo4jDataLoader(uri, user, password)

    try:
        # Phase 1: Database preparation
        logger.info("Starting database preparation...")
        loader.clear_database()
        loader.create_constraints()

        # Phase 2: Load entity data from CSV files
        data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
        logger.info("Loading entity data...")

        # Load primary entities in dependency order
        genes_df = pd.read_csv(os.path.join(data_dir, "genes.csv"))
        loader.load_genes(genes_df)

        proteins_df = pd.read_csv(os.path.join(data_dir, "proteins.csv"))
        loader.load_proteins(proteins_df)  # Also creates gene-protein relationships

        diseases_df = pd.read_csv(os.path.join(data_dir, "diseases.csv"))
        loader.load_diseases(diseases_df)

        drugs_df = pd.read_csv(os.path.join(data_dir, "drugs.csv"))
        loader.load_drugs(drugs_df)

        # Phase 3: Load relationship data
        logger.info("Loading relationship data...")

        protein_disease_df = pd.read_csv(
            os.path.join(data_dir, "protein_disease_associations.csv")
        )
        loader.load_protein_disease_associations(protein_disease_df)

        drug_disease_df = pd.read_csv(
            os.path.join(data_dir, "drug_disease_treatments.csv")
        )
        loader.load_drug_disease_treatments(drug_disease_df)

        drug_protein_df = pd.read_csv(
            os.path.join(data_dir, "drug_protein_targets.csv")
        )
        loader.load_drug_protein_targets(drug_protein_df)

        # Phase 4: Compute derived relationships
        logger.info("Computing derived relationships...")
        loader.create_gene_disease_links()

        logger.info("Data loading completed successfully!")

    except Exception as e:
        logger.error(f"Error loading data: {e}")
        raise
    finally:
        # Ensure database connection is properly closed
        loader.close()


if __name__ == "__main__":
    main()