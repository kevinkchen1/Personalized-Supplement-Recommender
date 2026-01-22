#!/usr/bin/env python3
"""
Delete All Relationships
Removes ALL relationships from the Neo4j database.
Keeps all nodes intact.

Updated for Complete Knowledge Graph (DrugBank + Mayo Clinic + Bridges)
"""

from neo4j import GraphDatabase
import logging
import time
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AllRelationshipsDeleter:
    def __init__(self):
        """Initialize connection to Neo4j using .env credentials"""
        uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
        user = os.getenv("NEO4J_USER", "neo4j")
        password = os.getenv("NEO4J_PASSWORD")
        
        if not password:
            raise ValueError(
                "NEO4J_PASSWORD not set. Please create .env file with NEO4J_PASSWORD=your_password"
            )
        
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        logger.info(f"✓ Connected to Neo4j at {uri}")
    
    def close(self):
        """Close the Neo4j driver"""
        self.driver.close()
    
    def get_all_relationship_types(self):
        """Get all relationship types in the database"""
        with self.driver.session() as session:
            result = session.run("CALL db.relationshipTypes()")
            all_types = [record["relationshipType"] for record in result]
            return sorted(all_types)
    
    def get_relationship_stats(self):
        """Get statistics for all relationships"""
        all_types = self.get_all_relationship_types()
        
        logger.info("=" * 70)
        logger.info("RELATIONSHIP STATISTICS:")
        
        if not all_types:
            logger.info("  No relationships found!")
            logger.info("=" * 70)
            return {}, 0
        
        with self.driver.session() as session:
            stats = {}
            total = 0
            
            for rel_type in all_types:
                result = session.run(f"""
                    MATCH ()-[r:`{rel_type}`]->()
                    RETURN count(r) as count
                """)
                count = result.single()["count"]
                stats[rel_type] = count
                total += count
                
                # Highlight critical bridge relationships
                if rel_type in ['EQUIVALENT_TO', 'HAS_SIMILAR_EFFECT_TO', 'CONTAINS']:
                    logger.info(f"  🔥 {rel_type}: {count:,} (CRITICAL)")
                else:
                    logger.info(f"  {rel_type}: {count:,}")
            
            logger.info(f"\n  TOTAL: {total:,} relationships")
            
        logger.info("=" * 70)
        return stats, total
    
    def delete_relationship_type(self, rel_type, batch_size=5000):
        """Delete a specific relationship type in batches"""
        logger.info(f"\nDeleting {rel_type} relationships...")
        
        with self.driver.session() as session:
            total_deleted = 0
            iteration = 0
            
            while True:
                iteration += 1
                start_time = time.time()
                
                result = session.run(f"""
                    MATCH ()-[r:`{rel_type}`]->()
                    WITH r LIMIT {batch_size}
                    DELETE r
                    RETURN count(r) as deleted
                """)
                
                deleted = result.single()["deleted"]
                total_deleted += deleted
                elapsed = time.time() - start_time
                
                if deleted == 0:
                    break
                
                if iteration % 10 == 0 or deleted < batch_size:
                    logger.info(f"  Iteration {iteration}: Deleted {deleted:,} | Total: {total_deleted:,} ({elapsed:.2f}s)")
            
            logger.info(f"✓ {rel_type} deletion complete: {total_deleted:,} relationships deleted")
            return total_deleted
    
    def delete_all_relationships(self, batch_size=5000):
        """Delete all relationships from the database"""
        all_types = self.get_all_relationship_types()
        
        if not all_types:
            logger.info("No relationships to delete.")
            return {}
        
        deletion_summary = {}
        
        for i, rel_type in enumerate(all_types, 1):
            logger.info(f"\n[{i}/{len(all_types)}]")
            deleted = self.delete_relationship_type(rel_type, batch_size)
            deletion_summary[rel_type] = deleted
        
        return deletion_summary
    
    def verify_deletion(self):
        """Verify that all relationships have been deleted"""
        logger.info("\n" + "=" * 70)
        logger.info("VERIFYING DELETION...")
        
        with self.driver.session() as session:
            result = session.run("MATCH ()-[r]->() RETURN count(r) as count")
            total = result.single()["count"]
            
            if total == 0:
                logger.info("✓✓✓ SUCCESS: ALL relationships deleted! ✓✓✓")
                logger.info("  Database now has 0 relationships")
            else:
                logger.warning(f"⚠ WARNING: {total:,} relationships remain:")
                
                result = session.run("""
                    MATCH ()-[r]->()
                    RETURN type(r) as rel_type, count(r) as count
                    ORDER BY count DESC
                """)
                
                for record in result:
                    logger.warning(f"  {record['rel_type']}: {record['count']:,}")
            
            # Show node count (should still exist)
            result = session.run("MATCH (n) RETURN count(n) as count")
            node_count = result.single()["count"]
            logger.info(f"\nNodes remaining (unchanged): {node_count:,}")
            
        logger.info("=" * 70)
    
    def run(self, batch_size=10000):
        """Execute the full relationship deletion process"""
        try:
            # Show initial stats
            stats, total = self.get_relationship_stats()
            
            if total == 0:
                logger.info("\n✓ No relationships found. Nothing to delete.")
                return
            
            # Confirm with user
            logger.info("\n" + "=" * 70)
            response = input(f"⚠️  Delete ALL {total:,} relationships? (yes/no): ")
            if response.lower() != 'yes':
                logger.info("Deletion cancelled.")
                return
            
            logger.info("\n🗑️  Starting relationship deletion...\n")
            overall_start = time.time()
            
            # Delete all relationships
            deletion_summary = self.delete_all_relationships(batch_size)
            
            # Verify
            self.verify_deletion()
            
            # Summary
            elapsed = time.time() - overall_start
            total_deleted = sum(deletion_summary.values())
            
            logger.info("\n" + "=" * 70)
            logger.info("DELETION SUMMARY:")
            for rel_type in sorted(deletion_summary.keys()):
                count = deletion_summary[rel_type]
                logger.info(f"  {rel_type}: {count:,}")
            
            logger.info(f"\n  TOTAL: {total_deleted:,}")
            logger.info(f"  Time elapsed: {elapsed:.2f} seconds ({elapsed/60:.2f} minutes)")
            if elapsed > 0:
                logger.info(f"  Deletion rate: {total_deleted/elapsed:.0f} relationships/second")
            logger.info("=" * 70)
            
        except Exception as e:
            logger.error(f"❌ Error during deletion: {e}", exc_info=True)
        finally:
            self.close()


def main():
    """Main execution function"""
    logger.info("=" * 70)
    logger.info("DELETE ALL RELATIONSHIPS")
    logger.info("=" * 70)
    logger.info("This will delete ALL relationships in the database.")
    logger.info("All nodes will remain intact.")
    logger.info("")
    logger.info("Expected relationship types:")
    logger.info("  DrugBank: INTERACTS_WITH, CONTAINS_DRUG, BELONGS_TO, etc.")
    logger.info("  Mayo Clinic: CAN_CAUSE, TREATS, INTERACTS_WITH")
    logger.info("  🔥 CRITICAL: EQUIVALENT_TO, HAS_SIMILAR_EFFECT_TO, CONTAINS")
    logger.info("=" * 70)
    
    deleter = AllRelationshipsDeleter()
    deleter.run(batch_size=10000)


if __name__ == "__main__":
    main()
