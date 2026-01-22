#!/usr/bin/env python3
"""
COMPLETE Neo4j Knowledge Graph Data Loader
Loads DrugBank + Mayo Clinic + Bridge Relationships

Data Structure:
- data/drugbank_data/       (12 files)
- data/mayo_clinic_data/    (10 files)

Total: 22 CSV files → Complete supplement safety knowledge graph
"""

import logging
import os
from pathlib import Path
import pandas as pd
from dotenv import load_dotenv
from neo4j import GraphDatabase
from tqdm import tqdm

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Suppress Neo4j informational messages about existing constraints/indexes
logging.getLogger("neo4j").setLevel(logging.WARNING)


class CompleteKnowledgeGraphLoader:
    """
    Complete data loader for supplement safety knowledge graph.
    
    Loads:
    1. DrugBank data (drugs, categories, interactions, etc.)
    2. Mayo Clinic data (supplements, medications, symptoms)
    3. Bridge relationships (ingredient equivalence, category similarity)
    """

    def __init__(self, uri: str, user: str, password: str):
        """Initialize with optimized driver settings"""
        self.driver = GraphDatabase.driver(
            uri,
            auth=(user, password),
            max_connection_lifetime=3600,
            max_connection_pool_size=50,
            connection_acquisition_timeout=120
        )
        logger.info("✓ Connected to Neo4j with optimized settings")

    def close(self):
        """Close database connection"""
        self.driver.close()
        logger.info("✓ Closed Neo4j connection")

    def clear_database(self):
        """
        Clear all existing data by calling the optimized delete scripts.
        Shows minimal output - just overall progress.
        """
        import sys
        import io
        import importlib.util
        
        logger.info("\n🗑️  Clearing existing database...")
        
        # Check if delete scripts exist in scripts/ folder
        delete_scripts_path = Path("scripts")
        if not delete_scripts_path.exists():
            self._fallback_clear_database()
            return
        
        relationships_script = delete_scripts_path / "delete_all_relationships.py"
        nodes_script = delete_scripts_path / "delete_all_nodes.py"
        
        if not relationships_script.exists() or not nodes_script.exists():
            self._fallback_clear_database()
            return
        
        try:
            # Suppress all output from delete scripts
            old_stdout = sys.stdout
            old_stderr = sys.stderr
            sys.stdout = io.StringIO()
            sys.stderr = io.StringIO()
            
            # Temporarily disable logging from delete scripts
            old_level = logging.getLogger().level
            logging.getLogger().setLevel(logging.CRITICAL)
            
            try:
                # Step 1: Delete relationships
                logger.setLevel(logging.INFO)  # Keep our logger active
                logger.info("  Deleting all relationships and nodes...")
                logger.setLevel(logging.CRITICAL)
                
                spec = importlib.util.spec_from_file_location("delete_rels", relationships_script)
                delete_rels = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(delete_rels)
                
                deleter_rels = delete_rels.AllRelationshipsDeleter()
                stats, total = deleter_rels.get_relationship_stats()
                
                if total > 0:
                    deleter_rels.delete_all_relationships(batch_size=10000)
                
                deleter_rels.close()
                
                # Step 2: Delete nodes
                spec = importlib.util.spec_from_file_location("delete_nodes", nodes_script)
                delete_nodes = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(delete_nodes)
                
                deleter_nodes = delete_nodes.NodeDeleter()
                stats, unlabeled = deleter_nodes.get_node_stats()
                total_nodes = sum(stats.values()) + unlabeled
                
                if total_nodes > 0:
                    deleter_nodes.delete_all_nodes(batch_size=10000)
                
                deleter_nodes.close()
                
            finally:
                # Restore output and logging
                sys.stdout = old_stdout
                sys.stderr = old_stderr
                logging.getLogger().setLevel(old_level)
                logger.setLevel(logging.INFO)
            
            logger.info("✓ Database cleared successfully")
            
        except Exception as e:
            # Restore output in case of error
            sys.stdout = old_stdout
            sys.stderr = old_stderr
            logging.getLogger().setLevel(old_level)
            logger.setLevel(logging.INFO)
            
            logger.error(f"❌ Error using delete scripts: {e}")
            logger.info("  Falling back to batch deletion...")
            self._fallback_clear_database()
    
    def _fallback_clear_database(self):
        """
        Fallback method: Clear database using direct batch deletion.
        Used if delete scripts are not available.
        """
        with self.driver.session() as session:
            # Count what we have
            result = session.run("MATCH (n) RETURN count(n) as node_count")
            node_count = result.single()["node_count"]
            
            result = session.run("MATCH ()-[r]->() RETURN count(r) as rel_count")
            rel_count = result.single()["rel_count"]
            
            if node_count == 0 and rel_count == 0:
                logger.info("  ✓ Database already empty")
                return
            
            logger.info(f"  Deleting {node_count:,} nodes and {rel_count:,} relationships...")
            
            # Delete in batches
            batch_size = 10000
            total_deleted = 0
            
            # Use tqdm for a single progress bar
            from tqdm import tqdm
            with tqdm(total=node_count, desc="  Clearing database", unit="nodes") as pbar:
                while True:
                    result = session.run(f"""
                        MATCH (n)
                        WITH n LIMIT {batch_size}
                        DETACH DELETE n
                        RETURN count(n) as deleted
                    """)
                    deleted = result.single()["deleted"]
                    
                    if deleted == 0:
                        break
                    
                    total_deleted += deleted
                    pbar.update(deleted)
            
            logger.info(f"✓ Deleted {total_deleted:,} nodes and all relationships")

    def create_constraints_and_indexes(self):
        """
        Create ALL constraints and indexes for entire knowledge graph.
        This must be done BEFORE loading any data for optimal performance.
        """
        constraints_and_indexes = [
            # ========== DRUGBANK NODES ==========
            "CREATE CONSTRAINT drug_id_unique IF NOT EXISTS "
            "FOR (d:Drug) REQUIRE d.drug_id IS UNIQUE",
            
            "CREATE CONSTRAINT category_id_unique IF NOT EXISTS "
            "FOR (c:Category) REQUIRE c.category_id IS UNIQUE",
            
            "CREATE CONSTRAINT brand_name_id_unique IF NOT EXISTS "
            "FOR (b:BrandName) REQUIRE b.brand_name_id IS UNIQUE",
            
            "CREATE CONSTRAINT synonym_id_unique IF NOT EXISTS "
            "FOR (s:Synonym) REQUIRE s.synonym_id IS UNIQUE",
            
            "CREATE CONSTRAINT salt_id_unique IF NOT EXISTS "
            "FOR (s:Salt) REQUIRE s.salt_id IS UNIQUE",
            
            "CREATE CONSTRAINT food_interaction_id_unique IF NOT EXISTS "
            "FOR (f:FoodInteraction) REQUIRE f.food_interaction_id IS UNIQUE",
            
            # ========== MAYO CLINIC NODES ==========
            "CREATE CONSTRAINT supplement_id_unique IF NOT EXISTS "
            "FOR (s:Supplement) REQUIRE s.supplement_id IS UNIQUE",
            
            "CREATE CONSTRAINT active_ingredient_id_unique IF NOT EXISTS "
            "FOR (a:ActiveIngredient) REQUIRE a.active_ingredient_id IS UNIQUE",
            
            "CREATE CONSTRAINT medication_id_unique IF NOT EXISTS "
            "FOR (m:Medication) REQUIRE m.medication_id IS UNIQUE",
            
            "CREATE CONSTRAINT symptom_id_unique IF NOT EXISTS "
            "FOR (s:Symptom) REQUIRE s.symptom_id IS UNIQUE",
            
            # ========== INDEXES FOR FAST LOOKUPS ==========
            "CREATE INDEX drug_name_idx IF NOT EXISTS "
            "FOR (d:Drug) ON (d.drug_name)",
            
            "CREATE INDEX supplement_name_idx IF NOT EXISTS "
            "FOR (s:Supplement) ON (s.supplement_name)",
            
            "CREATE INDEX medication_name_idx IF NOT EXISTS "
            "FOR (m:Medication) ON (m.medication_name)",
            
            "CREATE INDEX active_ingredient_name_idx IF NOT EXISTS "
            "FOR (a:ActiveIngredient) ON (a.active_ingredient)",
            
            "CREATE INDEX category_name_idx IF NOT EXISTS "
            "FOR (c:Category) ON (c.category)",
        ]

        with self.driver.session() as session:
            for constraint in constraints_and_indexes:
                try:
                    session.run(constraint)
                except Exception as e:
                    logger.warning(f"Constraint/index may already exist: {str(e)[:100]}")

        logger.info("✓ Created all constraints and indexes")

    def batch_execute(self, query: str, data: list, batch_size: int = 5000, desc: str = "Processing"):
        """
        Execute Cypher query in batches using UNWIND for optimal performance.
        
        Args:
            query: Cypher query containing UNWIND $batch
            data: List of dictionaries to process
            batch_size: Records per batch
            desc: Description for progress bar
        """
        total = len(data)
        
        with tqdm(total=total, desc=desc, unit="records") as pbar:
            for i in range(0, total, batch_size):
                batch = data[i:i + batch_size]
                
                with self.driver.session() as session:
                    session.run(query, batch=batch)
                
                pbar.update(len(batch))

    # ========================================================================
    # PHASE 1: DRUGBANK CORE ENTITIES
    # ========================================================================
    
    def load_drugs(self, df: pd.DataFrame):
        """Load Drug nodes from drugs.csv"""
        logger.info(f"Loading {len(df):,} drugs...")
        
        drugs_data = df.fillna("").to_dict('records')
        
        query = """
        UNWIND $batch AS row
        CREATE (d:Drug {
            drug_id: row.drug_id,
            drug_name: row.drug_name,
            description: row.description,
            indication: row.indication,
            type: row.type
        })
        """
        
        self.batch_execute(query, drugs_data, batch_size=5000, desc="Loading drugs")
        logger.info(f"✓ Loaded {len(df):,} drugs")

    def load_categories(self, df: pd.DataFrame):
        """Load Category nodes from categories.csv"""
        logger.info(f"Loading {len(df):,} categories...")
        
        categories_data = df.fillna("").to_dict('records')
        
        query = """
        UNWIND $batch AS row
        CREATE (c:Category {
            category_id: row.category_id,
            category: row.category
        })
        """
        
        self.batch_execute(query, categories_data, batch_size=5000, desc="Loading categories")
        logger.info(f"✓ Loaded {len(df):,} categories")

    def load_brand_names(self, df: pd.DataFrame):
        """Load BrandName nodes from brand_names.csv"""
        logger.info(f"Loading {len(df):,} brand names...")
        
        brand_data = df.fillna("").to_dict('records')
        
        query = """
        UNWIND $batch AS row
        CREATE (b:BrandName {
            brand_name_id: row.brand_name_id,
            brand_name: row.brand_name
        })
        """
        
        self.batch_execute(query, brand_data, batch_size=5000, desc="Loading brand names")
        logger.info(f"✓ Loaded {len(df):,} brand names")

    def load_synonyms(self, df: pd.DataFrame):
        """Load Synonym nodes from synonyms.csv"""
        logger.info(f"Loading {len(df):,} synonyms...")
        
        synonym_data = df.fillna("").to_dict('records')
        
        query = """
        UNWIND $batch AS row
        CREATE (s:Synonym {
            synonym_id: row.synonym_id,
            synonym: row.synonym
        })
        """
        
        self.batch_execute(query, synonym_data, batch_size=5000, desc="Loading synonyms")
        logger.info(f"✓ Loaded {len(df):,} synonyms")

    def load_salts(self, df: pd.DataFrame):
        """Load Salt nodes from salts.csv"""
        logger.info(f"Loading {len(df):,} salts...")
        
        salt_data = df.fillna("").to_dict('records')
        
        query = """
        UNWIND $batch AS row
        CREATE (s:Salt {
            salt_id: row.salt_id,
            salt_name: row.salt_name
        })
        """
        
        self.batch_execute(query, salt_data, batch_size=5000, desc="Loading salts")
        logger.info(f"✓ Loaded {len(df):,} salts")

    def load_food_interactions(self, df: pd.DataFrame):
        """Load FoodInteraction nodes from food_interactions.csv"""
        logger.info(f"Loading {len(df):,} food interactions...")
        
        food_data = df.fillna("").to_dict('records')
        
        query = """
        UNWIND $batch AS row
        CREATE (f:FoodInteraction {
            food_interaction_id: row.food_interaction_id,
            description: row.description
        })
        """
        
        self.batch_execute(query, food_data, batch_size=5000, desc="Loading food interactions")
        logger.info(f"✓ Loaded {len(df):,} food interactions")

    # ========================================================================
    # PHASE 2: DRUGBANK RELATIONSHIPS
    # ========================================================================
    
    def load_drug_category_belongs_to(self, df: pd.DataFrame):
        """Load Drug -[:BELONGS_TO]-> Category relationships"""
        logger.info(f"Loading {len(df):,} drug-category relationships...")
        
        rel_data = df.fillna("").to_dict('records')
        
        query = """
        UNWIND $batch AS row
        MATCH (d:Drug {drug_id: row.drug_id})
        MATCH (c:Category {category_id: row.category_id})
        CREATE (d)-[:BELONGS_TO]->(c)
        """
        
        self.batch_execute(query, rel_data, batch_size=10000, desc="Drug → Category")
        logger.info(f"✓ Loaded {len(df):,} drug-category relationships")

    def load_drug_drug_interactions(self, df: pd.DataFrame):
        """Load Drug -[:INTERACTS_WITH]-> Drug relationships"""
        logger.info(f"Loading {len(df):,} drug-drug interactions...")
        
        interaction_data = df.fillna("").to_dict('records')
        
        query = """
        UNWIND $batch AS row
        MATCH (d1:Drug {drug_id: row.drug_id})
        MATCH (d2:Drug {drug_id: row.interacting_drug_id})
        CREATE (d1)-[:INTERACTS_WITH {
            description: row.description
        }]->(d2)
        """
        
        self.batch_execute(query, interaction_data, batch_size=10000, desc="Drug ↔ Drug interactions")
        logger.info(f"✓ Loaded {len(df):,} drug-drug interactions")

    def load_brand_name_contains_drug(self, df: pd.DataFrame):
        """Load BrandName -[:CONTAINS_DRUG]-> Drug relationships"""
        logger.info(f"Loading {len(df):,} brand name-drug relationships...")
        
        rel_data = df.fillna("").to_dict('records')
        
        query = """
        UNWIND $batch AS row
        MATCH (b:BrandName {brand_name_id: row.brand_name_id})
        MATCH (d:Drug {drug_id: row.drug_id})
        CREATE (b)-[:CONTAINS_DRUG]->(d)
        """
        
        self.batch_execute(query, rel_data, batch_size=5000, desc="BrandName → Drug")
        logger.info(f"✓ Loaded {len(df):,} brand name-drug relationships")

    def load_drug_synonym_known_as(self, df: pd.DataFrame):
        """Load Drug -[:KNOWN_AS]-> Synonym relationships"""
        logger.info(f"Loading {len(df):,} drug-synonym relationships...")
        
        rel_data = df.fillna("").to_dict('records')
        
        query = """
        UNWIND $batch AS row
        MATCH (d:Drug {drug_id: row.drug_id})
        MATCH (s:Synonym {synonym_id: row.synonym_id})
        CREATE (d)-[:KNOWN_AS]->(s)
        """
        
        self.batch_execute(query, rel_data, batch_size=5000, desc="Drug → Synonym")
        logger.info(f"✓ Loaded {len(df):,} drug-synonym relationships")

    def load_drug_salt_has_salt_form(self, df: pd.DataFrame):
        """Load Drug -[:HAS_SALT_FORM]-> Salt relationships"""
        logger.info(f"Loading {len(df):,} drug-salt relationships...")
        
        rel_data = df.fillna("").to_dict('records')
        
        query = """
        UNWIND $batch AS row
        MATCH (d:Drug {drug_id: row.drug_id})
        MATCH (s:Salt {salt_id: row.salt_id})
        CREATE (d)-[:HAS_SALT_FORM]->(s)
        """
        
        self.batch_execute(query, rel_data, batch_size=5000, desc="Drug → Salt")
        logger.info(f"✓ Loaded {len(df):,} drug-salt relationships")

    def load_drug_food_interaction_has(self, df: pd.DataFrame):
        """Load Drug -[:HAS_FOOD_INTERACTION]-> FoodInteraction relationships"""
        logger.info(f"Loading {len(df):,} drug-food interaction relationships...")
        
        rel_data = df.fillna("").to_dict('records')
        
        query = """
        UNWIND $batch AS row
        MATCH (d:Drug {drug_id: row.drug_id})
        MATCH (f:FoodInteraction {food_interaction_id: row.food_interaction_id})
        CREATE (d)-[:HAS_FOOD_INTERACTION]->(f)
        """
        
        self.batch_execute(query, rel_data, batch_size=5000, desc="Drug → FoodInteraction")
        logger.info(f"✓ Loaded {len(df):,} drug-food interaction relationships")

    # ========================================================================
    # PHASE 3: MAYO CLINIC CORE ENTITIES
    # ========================================================================
    
    def load_supplements(self, df: pd.DataFrame):
        """Load Supplement nodes from supplements.csv"""
        logger.info(f"Loading {len(df):,} supplements...")
        
        supplement_data = df.fillna("").to_dict('records')
        
        query = """
        UNWIND $batch AS row
        CREATE (s:Supplement {
            supplement_id: row.supplement_id,
            supplement_name: row.supplement_name,
            safety_rating: row.safety_rating
        })
        """
        
        self.batch_execute(query, supplement_data, batch_size=1000, desc="Loading supplements")
        logger.info(f"✓ Loaded {len(df):,} supplements")

    def load_active_ingredients(self, df: pd.DataFrame):
        """Load ActiveIngredient nodes from active_ingredients.csv"""
        logger.info(f"Loading {len(df):,} active ingredients...")
        
        ingredient_data = df.fillna("").to_dict('records')
        
        query = """
        UNWIND $batch AS row
        CREATE (a:ActiveIngredient {
            active_ingredient_id: row.active_ingredient_id,
            active_ingredient: row.active_ingredient
        })
        """
        
        self.batch_execute(query, ingredient_data, batch_size=1000, desc="Loading active ingredients")
        logger.info(f"✓ Loaded {len(df):,} active ingredients")

    def load_medications(self, df: pd.DataFrame):
        """Load Medication nodes from medications.csv"""
        logger.info(f"Loading {len(df):,} medications...")
        
        medication_data = df.fillna("").to_dict('records')
        
        query = """
        UNWIND $batch AS row
        CREATE (m:Medication {
            medication_id: row.medication_id,
            medication_name: row.medication_name
        })
        """
        
        self.batch_execute(query, medication_data, batch_size=1000, desc="Loading medications")
        logger.info(f"✓ Loaded {len(df):,} medications")

    def load_symptoms(self, df: pd.DataFrame):
        """Load Symptom nodes from symptoms.csv (if exists)"""
        if df is None or len(df) == 0:
            logger.info("No symptoms file found or empty, skipping...")
            return
            
        logger.info(f"Loading {len(df):,} symptoms...")
        
        symptom_data = df.fillna("").to_dict('records')
        
        query = """
        UNWIND $batch AS row
        CREATE (s:Symptom {
            symptom_id: row.symptom_id,
            symptom_name: row.symptom_name
        })
        """
        
        self.batch_execute(query, symptom_data, batch_size=1000, desc="Loading symptoms")
        logger.info(f"✓ Loaded {len(df):,} symptoms")

    # ========================================================================
    # PHASE 4: MAYO CLINIC RELATIONSHIPS
    # ========================================================================
    
    def load_supplement_contains(self, df: pd.DataFrame):
        """Load Supplement -[:CONTAINS]-> ActiveIngredient relationships"""
        logger.info(f"Loading {len(df):,} supplement-ingredient relationships...")
        
        rel_data = df.fillna("").to_dict('records')
        
        query = """
        UNWIND $batch AS row
        MATCH (s:Supplement {supplement_id: row.supplement_id})
        MATCH (a:ActiveIngredient {active_ingredient_id: row.active_ingredient_id})
        CREATE (s)-[:CONTAINS {
            is_primary: row.is_primary
        }]->(a)
        """
        
        self.batch_execute(query, rel_data, batch_size=1000, desc="Supplement → ActiveIngredient")
        logger.info(f"✓ Loaded {len(df):,} supplement-ingredient relationships")

    def load_medication_drug_contains(self, df: pd.DataFrame):
        """Load Medication -[:CONTAINS_DRUG]-> Drug relationships"""
        logger.info(f"Loading {len(df):,} medication-drug relationships...")
        
        rel_data = df.fillna("").to_dict('records')
        
        query = """
        UNWIND $batch AS row
        MATCH (m:Medication {medication_id: row.medication_id})
        MATCH (d:Drug {drug_id: row.drug_id})
        CREATE (m)-[:CONTAINS_DRUG]->(d)
        """
        
        self.batch_execute(query, rel_data, batch_size=1000, desc="Medication → Drug")
        logger.info(f"✓ Loaded {len(df):,} medication-drug relationships")

    def load_supplement_medication_interacts_with(self, df: pd.DataFrame):
        """Load Supplement -[:SUPPLEMENT_INTERACTS_WITH]-> Medication relationships"""
        logger.info(f"Loading {len(df):,} supplement-medication interactions...")
        
        interaction_data = df.fillna("").to_dict('records')
        
        query = """
        UNWIND $batch AS row
        MATCH (s:Supplement {supplement_id: row.supplement_id})
        MATCH (m:Medication {medication_id: row.medication_id})
        CREATE (s)-[:SUPPLEMENT_INTERACTS_WITH {
            interaction_description: row.interaction_description
        }]->(m)
        """
        
        self.batch_execute(query, interaction_data, batch_size=1000, desc="Supplement ↔ Medication")
        logger.info(f"✓ Loaded {len(df):,} supplement-medication interactions")

    def load_supplement_symptom_can_cause(self, df: pd.DataFrame):
        """Load Supplement -[:CAN_CAUSE]-> Symptom relationships"""
        logger.info(f"Loading {len(df):,} supplement-symptom (can cause) relationships...")
        
        rel_data = df.fillna("").to_dict('records')
        
        query = """
        UNWIND $batch AS row
        MATCH (s:Supplement {supplement_id: row.supplement_id})
        MATCH (sym:Symptom {symptom_id: row.symptom_id})
        CREATE (s)-[:CAN_CAUSE]->(sym)
        """
        
        self.batch_execute(query, rel_data, batch_size=1000, desc="Supplement → Symptom (causes)")
        logger.info(f"✓ Loaded {len(df):,} can cause relationships")

    def load_supplement_symptom_treats(self, df: pd.DataFrame):
        """Load Supplement -[:TREATS]-> Symptom relationships"""
        logger.info(f"Loading {len(df):,} supplement-symptom (treats) relationships...")
        
        rel_data = df.fillna("").to_dict('records')
        
        query = """
        UNWIND $batch AS row
        MATCH (s:Supplement {supplement_id: row.supplement_id})
        MATCH (sym:Symptom {symptom_id: row.symptom_id})
        CREATE (s)-[:TREATS]->(sym)
        """
        
        self.batch_execute(query, rel_data, batch_size=1000, desc="Supplement → Symptom (treats)")
        logger.info(f"✓ Loaded {len(df):,} treats relationships")

    # ========================================================================
    # PHASE 5: BRIDGE RELATIONSHIPS (CRITICAL FOR SAFETY CHECKS!)
    # ========================================================================
    
    def load_active_ingredient_drug_equivalent(self, df: pd.DataFrame):
        """
        Load ActiveIngredient -[:EQUIVALENT_TO]-> Drug relationships
        
        This is CRITICAL RELATIONSHIP #1: Chemical equivalence
        Example: Monacolin K (in Red yeast rice) = Lovastatin
        """
        logger.info(f"🔥 Loading {len(df):,} ingredient-drug equivalence relationships...")
        
        equiv_data = df.fillna("").to_dict('records')
        
        query = """
        UNWIND $batch AS row
        MATCH (a:ActiveIngredient {active_ingredient_id: row.active_ingredient_id})
        MATCH (d:Drug {drug_id: row.drug_id})
        CREATE (a)-[:EQUIVALENT_TO {
            equivalence_type: row.equivalence_type,
            notes: row.notes
        }]->(d)
        """
        
        self.batch_execute(query, equiv_data, batch_size=500, 
                          desc="🔥 ActiveIngredient → Drug (EQUIVALENT)")
        logger.info(f"✓ Loaded {len(df):,} CRITICAL equivalence relationships")

    def load_supplement_category_similar_effect(self, df: pd.DataFrame):
        """
        Load Supplement -[:HAS_SIMILAR_EFFECT_TO]-> Category relationships
        
        This is CRITICAL RELATIONSHIP #2: Pharmacological similarity
        Example: Ginkgo has similar effects to Anticoagulants category
        """
        logger.info(f"🔥 Loading {len(df):,} supplement-category similarity relationships...")
        
        similar_data = df.fillna("").to_dict('records')
        
        query = """
        UNWIND $batch AS row
        MATCH (s:Supplement {supplement_id: row.supplement_id})
        MATCH (c:Category {category_id: row.category_id})
        CREATE (s)-[:HAS_SIMILAR_EFFECT_TO {
            confidence: row.confidence,
            notes: row.notes
        }]->(c)
        """
        
        self.batch_execute(query, similar_data, batch_size=500,
                          desc="🔥 Supplement → Category (SIMILAR EFFECT)")
        logger.info(f"✓ Loaded {len(df):,} CRITICAL similarity relationships")

    # ========================================================================
    # MAIN LOADING ORCHESTRATION
    # ========================================================================
    
    def load_all_data(self, data_dir: str):
        """
        Load ALL data for complete knowledge graph.
        
        Order matters! Nodes must exist before relationships.
        """
        drugbank_path = Path(data_dir) / "drugbank_data"
        mayo_path = Path(data_dir) / "mayo_clinic_data"

        # ====================================================================
        # PHASE 1: DrugBank Core Entities
        # ====================================================================
        logger.info("\n" + "="*70)
        logger.info("PHASE 1: Loading DrugBank Core Entities")
        logger.info("="*70)
        
        self.load_drugs(pd.read_csv(drugbank_path / "drugs.csv"))
        self.load_categories(pd.read_csv(drugbank_path / "categories.csv"))
        self.load_brand_names(pd.read_csv(drugbank_path / "brand_names.csv"))
        self.load_synonyms(pd.read_csv(drugbank_path / "synonyms.csv"))
        self.load_salts(pd.read_csv(drugbank_path / "salts.csv"))
        self.load_food_interactions(pd.read_csv(drugbank_path / "food_interactions.csv"))

        # ====================================================================
        # PHASE 2: DrugBank Relationships
        # ====================================================================
        logger.info("\n" + "="*70)
        logger.info("PHASE 2: Loading DrugBank Relationships")
        logger.info("="*70)
        
        self.load_drug_category_belongs_to(pd.read_csv(drugbank_path / "drug_category_belongs_to.csv"))
        self.load_drug_drug_interactions(pd.read_csv(drugbank_path / "drug_drug_interacts_with.csv"))
        self.load_brand_name_contains_drug(pd.read_csv(drugbank_path / "brand_name_drug_contains.csv"))
        self.load_drug_synonym_known_as(pd.read_csv(drugbank_path / "drug_synonym_known_as.csv"))
        self.load_drug_salt_has_salt_form(pd.read_csv(drugbank_path / "drug_salt_has_salt_form.csv"))
        self.load_drug_food_interaction_has(pd.read_csv(drugbank_path / "drug_food_interaction_has_food_interaction.csv"))

        # ====================================================================
        # PHASE 3: Mayo Clinic Core Entities
        # ====================================================================
        logger.info("\n" + "="*70)
        logger.info("PHASE 3: Loading Mayo Clinic Core Entities")
        logger.info("="*70)
        
        self.load_supplements(pd.read_csv(mayo_path / "supplements.csv"))
        self.load_active_ingredients(pd.read_csv(mayo_path / "active_ingredients.csv"))
        self.load_medications(pd.read_csv(mayo_path / "medications.csv"))
        
        # Symptoms file may not exist yet
        try:
            symptoms_df = pd.read_csv(mayo_path / "symptoms.csv")
            self.load_symptoms(symptoms_df)
        except FileNotFoundError:
            logger.info("No symptoms.csv found, skipping...")

        # ====================================================================
        # PHASE 4: Mayo Clinic Relationships
        # ====================================================================
        logger.info("\n" + "="*70)
        logger.info("PHASE 4: Loading Mayo Clinic Relationships")
        logger.info("="*70)
        
        self.load_supplement_contains(pd.read_csv(mayo_path / "supplement_contains.csv"))
        self.load_medication_drug_contains(pd.read_csv(mayo_path / "medication_drug_contains.csv"))
        self.load_supplement_medication_interacts_with(pd.read_csv(mayo_path / "supplement_medication_interacts_with.csv"))
        
        # Symptom relationships may not exist yet
        try:
            self.load_supplement_symptom_can_cause(pd.read_csv(mayo_path / "supplement_symptom_can_cause.csv"))
            self.load_supplement_symptom_treats(pd.read_csv(mayo_path / "supplement_symptom_treats.csv"))
        except FileNotFoundError:
            logger.info("No symptom relationship files found, skipping...")

        # ====================================================================
        # PHASE 5: Bridge Relationships (CRITICAL!)
        # ====================================================================
        logger.info("\n" + "="*70)
        logger.info("🔥 PHASE 5: Loading CRITICAL Bridge Relationships")
        logger.info("="*70)
        
        self.load_active_ingredient_drug_equivalent(
            pd.read_csv(mayo_path / "active_ingredient_equivalent_to_drug.csv"))
        self.load_supplement_category_similar_effect(
            pd.read_csv(mayo_path / "supplement_category_similar_effect.csv"))

        logger.info("\n" + "="*70)
        logger.info("✅ ALL DATA LOADED SUCCESSFULLY!")
        logger.info("="*70)


def main():
    """Main entry point"""
    # Get database credentials
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD")

    if not password:
        raise ValueError(
            "NEO4J_PASSWORD environment variable not set. "
            "Please create a .env file with NEO4J_PASSWORD=your_password"
        )

    # Data directory (should contain drugbank_data/ and mayo_clinic_data/)
    data_dir = os.getenv("DATA_DIR", "data")
    if not os.path.exists(data_dir):
        raise FileNotFoundError(
            f"Could not find data directory: {data_dir}\n"
            f"Please ensure directory structure:\n"
            f"  {data_dir}/\n"
            f"    ├── drugbank_data/\n"
            f"    └── mayo_clinic_data/"
        )

    logger.info(f"Using data directory: {data_dir}")

    # Initialize loader
    loader = CompleteKnowledgeGraphLoader(uri, user, password)

    try:
        logger.info("=" * 70)
        logger.info("🚀 Starting COMPLETE Knowledge Graph Import")
        logger.info("=" * 70)

        user_input = input(
            "\n⚠️  WARNING: This will DELETE ALL existing data and reload!\n"
            "Do you want to continue? (yes/no): "
        )

        if user_input.lower() not in ["yes", "y"]:
            logger.info("Import cancelled by user")
            return

        logger.info("\nClearing database...")
        loader.clear_database()
        
        logger.info("\nCreating constraints and indexes...")
        loader.create_constraints_and_indexes()

        # Load all data
        import time
        start_time = time.time()
        
        loader.load_all_data(data_dir)
        
        elapsed = time.time() - start_time
        minutes = int(elapsed // 60)
        seconds = int(elapsed % 60)

        # Summary
        logger.info("\n" + "=" * 70)
        logger.info("🎉 COMPLETE KNOWLEDGE GRAPH IMPORT SUCCESSFUL!")
        logger.info("=" * 70)
        logger.info(f"⏱️  Total time: {minutes} minutes {seconds} seconds")
        logger.info("\nYour supplement safety knowledge graph is ready!")


    except Exception as e:
        logger.error(f"\n❌ Error loading data: {e}")
        raise
    finally:
        loader.close()


if __name__ == "__main__":
    main()
