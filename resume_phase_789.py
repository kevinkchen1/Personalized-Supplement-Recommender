#!/usr/bin/env python3
"""
Resume DrugBank Loading - Clear Phase 7 in Batches and Load 7-9
Clears ONLY Phase 7 (CONTAINS relationships) in small batches to avoid memory errors.
Then loads phases 7, 8, 9.
"""

import logging
import os
from pathlib import Path
import time

import pandas as pd
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Import the loader class
from load_drugbank_data import DrugBankDataLoader

def clear_phase_7_in_batches(loader, batch_size=10000):
    """
    Clear Phase 7 data (CONTAINS relationships) in small batches.
    This prevents Neo4j from running out of transaction memory.
    """
    logger.info("\n⚠️  Clearing Phase 7 data (CONTAINS relationships) in batches...")
    
    with loader.driver.session() as session:
        # Count total relationships
        result = session.run("MATCH ()-[r:CONTAINS]->() RETURN count(r) as count").single()
        total_count = result["count"] if result else 0
        logger.info(f"   Total CONTAINS relationships to delete: {total_count:,}")
        
        if total_count == 0:
            logger.info("   ✅ No CONTAINS relationships to delete")
            return
        
        deleted_count = 0
        batch_num = 1
        
        # Delete in batches until all are gone
        while True:
            # Delete one batch
            result = session.run(f"""
                MATCH ()-[r:CONTAINS]->()
                WITH r LIMIT {batch_size}
                DELETE r
                RETURN count(r) as deleted
            """).single()
            
            batch_deleted = result["deleted"] if result else 0
            
            if batch_deleted == 0:
                break
            
            deleted_count += batch_deleted
            percent = (deleted_count / total_count) * 100
            
            logger.info(f"   Batch {batch_num}: Deleted {batch_deleted:,} relationships "
                       f"(Total: {deleted_count:,}/{total_count:,} = {percent:.1f}%)")
            
            batch_num += 1
            time.sleep(0.1)  # Small pause between batches
        
        logger.info(f"   ✅ Deleted all {deleted_count:,} CONTAINS relationships in {batch_num-1} batches")

def verify_existing_data(loader):
    """Verify that phases 1-6 data is intact."""
    logger.info("\n🔍 Verifying existing data...")
    
    with loader.driver.session() as session:
        result = session.run("""
            MATCH (n)
            RETURN labels(n)[0] AS NodeType, count(n) AS Count
            ORDER BY Count DESC
        """)
        
        logger.info("   Current nodes:")
        for record in result:
            logger.info(f"     {record['NodeType']}: {record['Count']:,}")
        
        result = session.run("""
            MATCH ()-[r]->()
            RETURN type(r) AS RelType, count(r) AS Count
            ORDER BY Count DESC
        """)
        
        logger.info("   Current relationships:")
        for record in result:
            logger.info(f"     {record['RelType']}: {record['Count']:,}")

def main():
    uri = os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD")

    if not password:
        raise ValueError("NEO4J_PASSWORD environment variable not set")

    data_dir = os.getenv("DRUGBANK_DATA_DIR", "drugbank_data")
    data_path = Path(data_dir)

    loader = DrugBankDataLoader(uri, user, password)

    try:
        logger.info("=" * 70)
        logger.info("Resume DrugBank Loading - Phases 7, 8, 9 (Batched Deletion)")
        logger.info("=" * 70)

        # Step 1: Verify existing data
        verify_existing_data(loader)

        # Step 2: Clear Phase 7 data in batches
        user_input = input(
            "\n⚠️  This will DELETE Phase 7 data (CONTAINS relationships) in batches\n"
            "and then reload phases 7-9.\n"
            "Phases 1-6 will NOT be affected.\n"
            "Continue? (yes/no): "
        )
        
        if user_input.lower() not in ["yes", "y"]:
            logger.info("❌ Operation cancelled")
            return

        # Delete in batches of 10,000 relationships at a time
        clear_phase_7_in_batches(loader, batch_size=10000)

        # Step 3: Load Phase 7 - Product Ingredients
        logger.info("\n📦 Phase 7: Loading product ingredients...")
        try:
            # Use the CLEAN CSV file
            ingredients_df = pd.read_csv(data_path / "product_ingredients_clean.csv")
            logger.info(f"   Found {len(ingredients_df):,} product ingredient records (from cleaned file)")
            
            # Load in batches to avoid memory issues
            logger.info("   Loading in batches...")
            batch_size = 1000
            for i in range(0, len(ingredients_df), batch_size):
                batch = ingredients_df.iloc[i:i+batch_size]
                
                for _, row in batch.iterrows():
                    with loader.driver.session() as session:
                        session.run(
                            """
                            MATCH (dp:DrugProduct {product_name: $product_name})
                            MERGE (ai:Drug {drugbank_id: $active_ingredient_id})
                            ON CREATE SET ai.name = $active_ingredient_name
                            MERGE (dp)-[r:CONTAINS]->(ai)
                            ON CREATE SET r.strength = $strength
                            """,
                            product_name=row["product_name"],
                            active_ingredient_id=row["active_ingredient_id"],
                            active_ingredient_name=row["active_ingredient_name"],
                            strength=row.get("strength", ""),
                        )
                
                logger.info(f"   Loaded batch {i//batch_size + 1} "
                           f"({min(i+batch_size, len(ingredients_df)):,}/{len(ingredients_df):,})")
            
            logger.info("   ✅ Phase 7 complete!")
        except FileNotFoundError:
            logger.error("   ❌ product_ingredients_clean.csv not found!")
            logger.error("   Please run: python3 clean_product_ingredients.py first")
            return
        except Exception as e:
            logger.error(f"   ❌ Phase 7 failed: {e}")
            raise

        # Step 4: Load Phase 8 - Salts
        logger.info("\n🧪 Phase 8: Loading salt relationships...")
        try:
            salts_df = pd.read_csv(data_path / "salts.csv")
            logger.info(f"   Found {len(salts_df):,} salt records")
            loader.load_salts(salts_df)
            logger.info("   ✅ Phase 8 complete!")
        except FileNotFoundError:
            logger.warning("   ⚠️  salts.csv not found, skipping")
        except Exception as e:
            logger.error(f"   ❌ Phase 8 failed: {e}")

        # Step 5: Load Phase 9 - Toxicity
        logger.info("\n⚠️  Phase 9: Loading toxicity and contraindications...")
        try:
            toxicity_df = pd.read_csv(data_path / "toxicity_contraindications.csv")
            logger.info(f"   Found {len(toxicity_df):,} toxicity records")
            loader.load_toxicity_contraindications(toxicity_df)
            logger.info("   ✅ Phase 9 complete!")
        except FileNotFoundError:
            logger.warning("   ⚠️  toxicity_contraindications.csv not found, skipping")
        except Exception as e:
            logger.error(f"   ❌ Phase 9 failed: {e}")

        # Step 6: Final verification
        logger.info("\n" + "=" * 70)
        logger.info("🎉 Loading Complete! Final Summary:")
        logger.info("=" * 70)
        
        verify_existing_data(loader)
        
        logger.info("\n✨ Your DrugBank knowledge graph is ready!")
        logger.info("Next step: Add Mayo Clinic supplement data")

    except Exception as e:
        logger.error(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        loader.close()

if __name__ == "__main__":
    main()