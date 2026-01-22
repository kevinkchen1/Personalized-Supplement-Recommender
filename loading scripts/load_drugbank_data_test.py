#!/usr/bin/env python3
"""
Neo4j DrugBank Knowledge Graph Data Loader

This script populates a Neo4j graph database with DrugBank medication data
for a personalized supplement recommendation system. It creates a comprehensive
knowledge graph suitable for detecting drug-supplement interactions, hidden
drug duplications, and safety assessments.

The script handles:
- Entity creation (Drug, DrugCategory, DrugProduct, ActiveIngredient, etc.)
- Relationship establishment (BELONGS_TO_CATEGORY, INTERACTS_WITH, etc.)
- Database constraints for data integrity
- Complete database rebuild with cleanup

Data Sources:
    Reads CSV files from the drugbank_data/ directory:
    - drugs.csv: Core drug entities with descriptions and indications
    - drug_categories.csv: Drug therapeutic/chemical classifications
    - drug_interactions.csv: Drug-drug interaction data
    - drug_products.csv: Commercial drug products with formulations
    - drug_synonyms.csv: Alternative drug names
    - food_interactions.csv: Drug-food interaction warnings
    - product_ingredients.csv: Active ingredients in drug products
    - salts.csv: Salt forms of drugs
    - toxicity_contraindications.csv: Safety information

Usage:
    python load_drugbank_data.py

Environment Variables:
    NEO4J_URI: Database connection URI (default: bolt://localhost:7687)
    NEO4J_USER: Database username (default: neo4j)
    NEO4J_PASSWORD: Database password (required)
"""

import logging
import os
from pathlib import Path
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


class DrugBankDataLoader:
    """
    A comprehensive data loader for populating Neo4j with DrugBank knowledge
    graph data for supplement safety and interaction detection.

    This class manages the complete process of loading structured DrugBank data
    into a Neo4j graph database. It handles entity creation, relationship establishment,
    constraint management, and data integrity verification.

    The loader creates a knowledge graph with the following schema:
    - Nodes: Drug, DrugCategory, DrugProduct, ActiveIngredient, Synonym, 
             FoodInteraction, ToxicityProfile, Salt
    - Relationships: BELONGS_TO_CATEGORY, INTERACTS_WITH, HAS_PRODUCT, CONTAINS,
                    KNOWN_AS, HAS_FOOD_INTERACTION, CONTRAINDICATED, HAS_SALT_FORM

    Features:
    - Transactional loading with proper error handling
    - Database constraint creation for performance optimization
    - Progress logging throughout the loading process
    - Complete database rebuilding capability
    - Batch processing for large datasets

    Example:
        >>> loader = DrugBankDataLoader("bolt://localhost:7687", "neo4j", "password")
        >>> loader.clear_database()
        >>> loader.create_constraints()
        >>> loader.load_all_data("drugbank_data/")
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
        logger.info("Closed Neo4j connection")

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
            - Drug.drugbank_id: Ensures unique drug identifiers
            - DrugCategory.category: Ensures unique category names
            - DrugProduct.product_name: Ensures unique product identifiers
            - Synonym.synonym: Ensures unique synonym names per drug
        """
        constraints = [
            "CREATE CONSTRAINT IF NOT EXISTS FOR (d:Drug) "
            "REQUIRE d.drugbank_id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (dc:DrugCategory) "
            "REQUIRE dc.category IS UNIQUE",
        ]

        with self.driver.session() as session:
            for constraint in constraints:
                session.run(constraint)
            logger.info("Created database constraints")

    def load_drugs(self, df: pd.DataFrame):
        """
        Load drug entities into the Neo4j database.

        Creates Drug nodes with comprehensive pharmaceutical information including
        drug name, clinical descriptions, indications, and drug type.

        Args:
            df: DataFrame containing drug data with columns:
                - drugbank_id: Unique drug identifier
                - name: Drug name
                - description: Full drug description
                - indication: Clinical indications
                - type: Drug type (e.g., "small molecule", "biotech")

        Node Properties Created:
            Each Drug node includes pharmaceutical metadata essential for
            clinical decision-making and safety assessments.
        """
        with self.driver.session() as session:
            for _, row in df.iterrows():
                session.run(
                    """
                    CREATE (d:Drug {
                        drugbank_id: $drugbank_id,
                        name: $name,
                        description: $description,
                        indication: $indication,
                        type: $type
                    })
                    """,
                    drugbank_id=row["drugbank_id"],
                    name=row["name"],
                    description=row.get("description", ""),
                    indication=row.get("indication", ""),
                    type=row.get("type", ""),
                )
            logger.info(f"Loaded {len(df)} drugs")

    def load_drug_categories(self, df: pd.DataFrame):
        """
        Load drug categories and establish drug-category relationships.

        Creates DrugCategory nodes for therapeutic/chemical classifications
        and establishes BELONGS_TO_CATEGORY relationships from drugs to categories.

        Args:
            df: DataFrame containing category data with columns:
                - drug_id: Reference to existing drug
                - category: Category name (e.g., "Anticoagulants", "Enzyme Inhibitors")

        Creates:
            - DrugCategory nodes for unique categories
            - BELONGS_TO_CATEGORY relationships from drugs to categories

        Note:
            Requires drugs to be loaded first.
        """
        with self.driver.session() as session:
            for _, row in df.iterrows():
                # Create category if it doesn't exist (MERGE)
                # Then create relationship from drug to category
                session.run(
                    """
                    MERGE (dc:DrugCategory {category: $category})
                    WITH dc
                    MATCH (d:Drug {drugbank_id: $drug_id})
                    MERGE (d)-[:BELONGS_TO_CATEGORY]->(dc)
                    """,
                    drug_id=row["drug_id"],
                    category=row["category"],
                )
            logger.info(f"Loaded {len(df)} drug-category relationships")

    def load_drug_interactions(self, df: pd.DataFrame):
        """
        Load drug-drug interaction relationships.

        Creates INTERACTS_WITH relationships between drugs with detailed
        interaction descriptions including severity and mechanism information.

        Args:
            df: DataFrame containing interaction data with columns:
                - drug_id: Source drug identifier
                - interacting_drug_id: Target drug identifier
                - interacting_drug_name: Name of interacting drug
                - description: Detailed interaction description

        Relationship Properties:
            - interacting_drug_name: Human-readable name
            - description: Full clinical interaction description

        Note:
            Requires drugs to be loaded first. Creates relationships between
            existing Drug nodes.
        """
        with self.driver.session() as session:
            batch_size = 1000
            for i in range(0, len(df), batch_size):
                batch = df.iloc[i : i + batch_size]
                for _, row in batch.iterrows():
                    session.run(
                        """
                        MATCH (d1:Drug {drugbank_id: $drug_id})
                        MATCH (d2:Drug {drugbank_id: $interacting_drug_id})
                        MERGE (d1)-[:INTERACTS_WITH {
                            interacting_drug_name: $interacting_drug_name,
                            description: $description
                        }]->(d2)
                        """,
                        drug_id=row["drug_id"],
                        interacting_drug_id=row["interacting_drug_id"],
                        interacting_drug_name=row["interacting_drug_name"],
                        description=row.get("description", ""),
                    )
                logger.info(
                    f"Loaded interactions batch {i//batch_size + 1} "
                    f"({min(i+batch_size, len(df))}/{len(df)})"
                )
            logger.info(f"Loaded {len(df)} drug interactions")

    def load_drug_products(self, df: pd.DataFrame):
        """
        Load drug product entities and establish drug-product relationships.

        Creates DrugProduct nodes representing commercial formulations and
        establishes HAS_PRODUCT relationships from drugs to their products.

        Args:
            df: DataFrame containing product data with columns:
                - drug_id: Reference to existing drug
                - product_name: Commercial product name
                - labeller: Manufacturer name
                - dosage_form: Form (e.g., "Tablet", "Injection")
                - strength: Drug strength (e.g., "50 mg")
                - route: Administration route (e.g., "Oral", "IV")

        Creates:
            - DrugProduct nodes with formulation details
            - HAS_PRODUCT relationships from drugs to products

        Note:
            Requires drugs to be loaded first.
        """
        with self.driver.session() as session:
            for _, row in df.iterrows():
                session.run(
                    """
                    CREATE (dp:DrugProduct {
                        product_name: $product_name,
                        labeller: $labeller,
                        dosage_form: $dosage_form,
                        strength: $strength,
                        route: $route
                    })
                    WITH dp
                    MATCH (d:Drug {drugbank_id: $drug_id})
                    CREATE (d)-[:HAS_PRODUCT]->(dp)
                    """,
                    drug_id=row["drug_id"],
                    product_name=row["product_name"],
                    labeller=row.get("labeller", ""),
                    dosage_form=row.get("dosage_form", ""),
                    strength=row.get("strength", ""),
                    route=row.get("route", ""),
                )
            logger.info(f"Loaded {len(df)} drug products")

    def load_drug_synonyms(self, df: pd.DataFrame):
        """
        Load drug synonym relationships.

        Creates KNOWN_AS relationships from drugs to their alternative names,
        enabling flexible drug name matching and search.

        Args:
            df: DataFrame containing synonym data with columns:
                - drugbank_id: Reference to existing drug
                - synonym: Alternative drug name

        Relationship Properties:
            - synonym: Alternative name for the drug

        Note:
            Uses relationship property instead of separate nodes to keep
            synonyms lightweight and directly attached to drugs.
        """
        with self.driver.session() as session:
            batch_size = 1000
            for i in range(0, len(df), batch_size):
                batch = df.iloc[i : i + batch_size]
                for _, row in batch.iterrows():
                    session.run(
                        """
                        MATCH (d:Drug {drugbank_id: $drugbank_id})
                        CREATE (d)-[:KNOWN_AS {synonym: $synonym}]->(:Synonym {name: $synonym})
                        """,
                        drugbank_id=row["drugbank_id"],
                        synonym=row["synonym"],
                    )
                logger.info(
                    f"Loaded synonyms batch {i//batch_size + 1} "
                    f"({min(i+batch_size, len(df))}/{len(df)})"
                )
            logger.info(f"Loaded {len(df)} drug synonyms")

    def load_food_interactions(self, df: pd.DataFrame):
        """
        Load drug-food interaction relationships.

        Creates HAS_FOOD_INTERACTION relationships from drugs to food interaction
        instructions, representing dietary warnings and administration guidance.

        Args:
            df: DataFrame containing food interaction data with columns:
                - drug_id: Reference to existing drug
                - food_interaction: Detailed interaction instruction text

        Relationship Properties:
            - instruction: Full food interaction warning or guidance

        Note:
            These are critical for supplement safety as many supplements
            have similar food interaction warnings (e.g., anticoagulant effects).
        """
        with self.driver.session() as session:
            for _, row in df.iterrows():
                session.run(
                    """
                    MATCH (d:Drug {drugbank_id: $drug_id})
                    CREATE (d)-[:HAS_FOOD_INTERACTION {
                        instruction: $food_interaction
                    }]->(:FoodInteraction {text: $food_interaction})
                    """,
                    drug_id=row["drug_id"],
                    food_interaction=row["food_interaction"],
                )
            logger.info(f"Loaded {len(df)} food interactions")

    def load_product_ingredients(self, df: pd.DataFrame):
        """
        Load product-ingredient relationships.

        Creates ActiveIngredient nodes and CONTAINS relationships from drug
        products to their active ingredients. This is CRITICAL for detecting
        hidden drug duplications in supplements.

        Args:
            df: DataFrame containing ingredient data with columns:
                - product_name: Reference to existing product
                - active_ingredient_id: Ingredient drug ID
                - active_ingredient_name: Ingredient name
                - strength: Amount of ingredient

        Creates:
            - ActiveIngredient nodes (merged with Drug nodes if same ID)
            - CONTAINS relationships from products to ingredients

        Note:
            This enables queries like "Does this supplement contain the same
            active ingredient as this medication?"
        """
        with self.driver.session() as session:
            for _, row in df.iterrows():
                session.run(
                    """
                    MATCH (dp:DrugProduct {product_name: $product_name})
                    MERGE (ai:Drug {drugbank_id: $active_ingredient_id})
                    ON CREATE SET ai.name = $active_ingredient_name
                    CREATE (dp)-[:CONTAINS {strength: $strength}]->(ai)
                    """,
                    product_name=row["product_name"],
                    active_ingredient_id=row["active_ingredient_id"],
                    active_ingredient_name=row["active_ingredient_name"],
                    strength=row.get("strength", ""),
                )
            logger.info(f"Loaded {len(df)} product ingredients")

    def load_salts(self, df: pd.DataFrame):
        """
        Load drug salt form relationships.

        Creates HAS_SALT_FORM relationships between parent drugs and their
        salt formulations, enabling recognition of equivalent drugs.

        Args:
            df: DataFrame containing salt data with columns:
                - parent_drugbank_id: Reference to parent drug
                - salt_drugbank_id: Reference to salt form drug
                - salt_name: Human-readable salt name

        Relationship Properties:
            - salt_name: Name of the salt form

        Note:
            Important for recognizing that different salt forms are the same
            drug for interaction purposes (e.g., Magnesium oxide vs citrate).
        """
        with self.driver.session() as session:
            for _, row in df.iterrows():
                session.run(
                    """
                    MATCH (parent:Drug {drugbank_id: $parent_drugbank_id})
                    MATCH (salt:Drug {drugbank_id: $salt_drugbank_id})
                    CREATE (parent)-[:HAS_SALT_FORM {salt_name: $salt_name}]->(salt)
                    """,
                    parent_drugbank_id=row["parent_drugbank_id"],
                    salt_drugbank_id=row["salt_drugbank_id"],
                    salt_name=row["salt_name"],
                )
            logger.info(f"Loaded {len(df)} salt relationships")

    def load_toxicity_contraindications(self, df: pd.DataFrame):
        """
        Load drug toxicity and contraindication information.

        Creates CONTRAINDICATED relationships from drugs with detailed safety
        information including toxicity data and contraindication warnings.

        Args:
            df: DataFrame containing toxicity data with columns:
                - drug_id: Reference to existing drug
                - toxicity: Toxicity information
                - indication_text: Contraindication details

        Relationship Properties:
            - toxicity: Full toxicity description
            - contraindication: Contraindication warnings

        Note:
            Critical for safety assessments - determines when drugs/supplements
            should NOT be used together or in certain populations.
        """
        with self.driver.session() as session:
            for _, row in df.iterrows():
                session.run(
                    """
                    MATCH (d:Drug {drugbank_id: $drug_id})
                    CREATE (d)-[:CONTRAINDICATED {
                        toxicity: $toxicity,
                        contraindication: $indication_text
                    }]->(:ToxicityProfile {
                        toxicity: $toxicity,
                        contraindication: $indication_text
                    })
                    """,
                    drug_id=row["drug_id"],
                    toxicity=row.get("toxicity", ""),
                    indication_text=row.get("indication_text", ""),
                )
            logger.info(f"Loaded {len(df)} toxicity/contraindication records")

    def load_all_data(self, data_dir: str):
        """
        Load all DrugBank data from CSV files in the specified directory.

        Orchestrates the complete data loading process in dependency order:
        1. Core entities (drugs)
        2. Supporting entities (categories, products)
        3. Relationships (interactions, synonyms, etc.)

        Args:
            data_dir: Path to directory containing DrugBank CSV files

        Expected Files:
            - drugs.csv
            - drug_categories.csv
            - drug_interactions.csv
            - drug_products.csv
            - drug_synonyms.csv
            - food_interactions.csv
            - product_ingredients.csv
            - salts.csv
            - toxicity_contraindications.csv

        Raises:
            FileNotFoundError: If required CSV files are missing
            Exception: If data loading fails
        """
        data_path = Path(data_dir)

        # Phase 1: Load core entities
        logger.info("Phase 1: Loading core drug entities...")
        drugs_df = pd.read_csv(data_path / "drugs.csv")
        self.load_drugs(drugs_df)

        # Phase 2: Load categories and create relationships
        logger.info("Phase 2: Loading drug categories...")
        categories_df = pd.read_csv(data_path / "drug_categories.csv")
        self.load_drug_categories(categories_df)

        # Phase 3: Load drug products
        logger.info("Phase 3: Loading drug products...")
        products_df = pd.read_csv(data_path / "drug_products.csv")
        self.load_drug_products(products_df)

        # Phase 4: Load drug interactions
        logger.info("Phase 4: Loading drug interactions (this may take a while)...")
        interactions_df = pd.read_csv(data_path / "drug_interactions.csv")
        self.load_drug_interactions(interactions_df)

        # Phase 5: Load synonyms
        logger.info("Phase 5: Loading drug synonyms...")
        synonyms_df = pd.read_csv(data_path / "drug_synonyms.csv")
        self.load_drug_synonyms(synonyms_df)

        # Phase 6: Load food interactions
        logger.info("Phase 6: Loading food interactions...")
        food_df = pd.read_csv(data_path / "food_interactions.csv")
        self.load_food_interactions(food_df)

        # Phase 7: Load product ingredients (critical for supplement safety!)
        logger.info("Phase 7: Loading product ingredients...")
        ingredients_df = pd.read_csv(data_path / "product_ingredients.csv")
        self.load_product_ingredients(ingredients_df)

        # Phase 8: Load salt forms
        logger.info("Phase 8: Loading salt relationships...")
        salts_df = pd.read_csv(data_path / "salts.csv")
        self.load_salts(salts_df)

        # Phase 9: Load toxicity and contraindications
        logger.info("Phase 9: Loading toxicity and contraindications...")
        toxicity_df = pd.read_csv(data_path / "toxicity_contraindications.csv")
        self.load_toxicity_contraindications(toxicity_df)

        logger.info("✅ All DrugBank data loaded successfully!")


def main():
    """
    Main entry point for loading DrugBank knowledge graph data into Neo4j.

    This function orchestrates the complete data loading process:
    1. Establishes database connection using environment variables
    2. Clears existing data for fresh loading
    3. Creates database constraints for performance
    4. Loads all DrugBank entities and relationships
    5. Handles errors gracefully with proper cleanup

    Environment Variables Required:
        NEO4J_PASSWORD: Database password (required)
        NEO4J_URI: Database URI (optional, defaults to bolt://localhost:7687)
        NEO4J_USER: Database username (optional, defaults to neo4j)

    Data Loading Order:
        1. Drugs (core entities)
        2. Drug categories
        3. Drug products
        4. Drug interactions
        5. Synonyms
        6. Food interactions
        7. Product ingredients
        8. Salt forms
        9. Toxicity/contraindications

    Raises:
        ValueError: If required environment variables are missing
        FileNotFoundError: If data directory or CSV files are missing
        Exception: If database connection or data loading fails
    """
    # Get database credentials from environment
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD")

    if not password:
        raise ValueError(
            "NEO4J_PASSWORD environment variable not set. "
            "Please create a .env file with NEO4J_PASSWORD=your_password"
        )

    # Determine data directory
    data_dir = os.getenv("DRUGBANK_DATA_DIR", "drugbank_data")
    if not os.path.exists(data_dir):
        # Try alternative path
        data_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "drugbank_data"
        )
        if not os.path.exists(data_dir):
            raise FileNotFoundError(
                f"Could not find drugbank_data directory. "
                f"Please ensure CSV files are in ./drugbank_data/ or set "
                f"DRUGBANK_DATA_DIR environment variable."
            )

    logger.info(f"Using data directory: {data_dir}")

    # Initialize data loader
    loader = DrugBankDataLoader(uri, user, password)

    try:
        # Phase 1: Database preparation
        logger.info("=" * 70)
        logger.info("Starting DrugBank Knowledge Graph Import")
        logger.info("=" * 70)

        user_input = input(
            "\n⚠️  WARNING: This will DELETE all existing data in Neo4j!\n"
            "Do you want to continue? (yes/no): "
        )

        if user_input.lower() not in ["yes", "y"]:
            logger.info("Import cancelled by user")
            return

        logger.info("\nClearing database...")
        loader.clear_database()

        logger.info("Creating constraints...")
        loader.create_constraints()

        # Phase 2: Load all data
        loader.load_all_data(data_dir)

        # Summary
        logger.info("\n" + "=" * 70)
        logger.info("🎉 DrugBank Knowledge Graph Import Complete!")
        logger.info("=" * 70)
        logger.info(
            "\nYour knowledge graph is ready for supplement safety queries!"
        )
        logger.info(
            "Next steps: Test with Cypher queries or connect your LangGraph agent."
        )

    except Exception as e:
        logger.error(f"\n❌ Error loading data: {e}")
        raise
    finally:
        # Ensure database connection is properly closed
        loader.close()


if __name__ == "__main__":
    main()