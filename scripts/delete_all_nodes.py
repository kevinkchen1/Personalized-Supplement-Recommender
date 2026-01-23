#!/usr/bin/env python3
"""
Delete All Nodes
Removes all nodes from the Neo4j database.
Should only be run AFTER all relationships have been deleted.

Updated for Complete Knowledge Graph (DrugBank + Mayo Clinic)
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


class NodeDeleter:
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
    
    def check_relationships(self):
        """Check if any relationships still exist"""
        with self.driver.session() as session:
            result = session.run("MATCH ()-[r]->() RETURN count(r) as count")
            rel_count = result.single()["count"]
            
            if rel_count > 0:
                logger.error("=" * 70)
                logger.error("⚠️  ERROR: Relationships still exist in the database!")
                logger.error(f"Found {rel_count:,} relationships")
                logger.error("")
                logger.error("You must delete all relationships BEFORE deleting nodes.")
                logger.error("Run: python3 delete_all_relationships.py")
                logger.error("=" * 70)
                return False
            
            logger.info("✓ No relationships found. Safe to delete nodes.")
            return True
    
    def get_node_stats(self):
        """Get statistics for all nodes by label"""
        with self.driver.session() as session:
            result = session.run("CALL db.labels()")
            labels = sorted([record["label"] for record in result])
            
            logger.info("=" * 70)
            logger.info("NODE STATISTICS:")
            
            if not labels:
                logger.info("  No labeled nodes found!")
                result = session.run("MATCH (n) WHERE size(labels(n)) = 0 RETURN count(n) as count")
                unlabeled = result.single()["count"]
                if unlabeled > 0:
                    logger.info(f"  Unlabeled nodes: {unlabeled:,}")
                logger.info("=" * 70)
                return {}, unlabeled
            
            stats = {}
            total = 0
            
            # Define critical Mayo Clinic nodes
            critical_nodes = ['Supplement', 'ActiveIngredient', 'Medication']
            
            for label in labels:
                result = session.run(f"""
                    MATCH (n:`{label}`)
                    RETURN count(n) as count
                """)
                count = result.single()["count"]
                stats[label] = count
                total += count
                
                # Highlight critical Mayo Clinic nodes
                if label in critical_nodes:
                    logger.info(f"  🔥 {label}: {count:,} (Mayo Clinic)")
                else:
                    logger.info(f"  {label}: {count:,}")
            
            # Check for unlabeled nodes
            result = session.run("MATCH (n) WHERE size(labels(n)) = 0 RETURN count(n) as count")
            unlabeled = result.single()["count"]
            if unlabeled > 0:
                logger.info(f"  (unlabeled): {unlabeled:,}")
                total += unlabeled
            
            logger.info(f"\n  TOTAL NODES: {total:,}")
            logger.info("=" * 70)
            
            return stats, unlabeled
    
    def delete_nodes_by_label(self, label, batch_size=10000):
        """Delete nodes with a specific label in batches"""
        logger.info(f"\nDeleting {label} nodes...")
        
        with self.driver.session() as session:
            total_deleted = 0
            iteration = 0
            
            while True:
                iteration += 1
                start_time = time.time()
                
                result = session.run(f"""
                    MATCH (n:`{label}`)
                    WITH n LIMIT {batch_size}
                    DELETE n
                    RETURN count(n) as deleted
                """)
                
                deleted = result.single()["deleted"]
                total_deleted += deleted
                elapsed = time.time() - start_time
                
                if deleted == 0:
                    break
                
                if iteration % 10 == 0 or deleted < batch_size:
                    logger.info(f"  Iteration {iteration}: Deleted {deleted:,} | Total: {total_deleted:,} ({elapsed:.2f}s)")
            
            logger.info(f"✓ {label} deletion complete: {total_deleted:,} nodes deleted")
            return total_deleted
    
    def delete_unlabeled_nodes(self, batch_size=10000):
        """Delete nodes without any labels"""
        logger.info(f"\nDeleting unlabeled nodes...")
        
        with self.driver.session() as session:
            total_deleted = 0
            iteration = 0
            
            while True:
                iteration += 1
                start_time = time.time()
                
                result = session.run(f"""
                    MATCH (n)
                    WHERE size(labels(n)) = 0
                    WITH n LIMIT {batch_size}
                    DELETE n
                    RETURN count(n) as deleted
                """)
                
                deleted = result.single()["deleted"]
                total_deleted += deleted
                elapsed = time.time() - start_time
                
                if deleted == 0:
                    break
                
                logger.info(f"  Iteration {iteration}: Deleted {deleted:,} | Total: {total_deleted:,}")
            
            logger.info(f"✓ Unlabeled node deletion complete: {total_deleted:,} nodes deleted")
            return total_deleted
    
    def delete_all_nodes(self, batch_size=10000):
        """Delete all nodes from the database"""
        with self.driver.session() as session:
            result = session.run("CALL db.labels()")
            labels = sorted([record["label"] for record in result])
        
        deletion_summary = {}
        
        # Delete labeled nodes
        for i, label in enumerate(labels, 1):
            logger.info(f"\n[{i}/{len(labels)}]")
            deleted = self.delete_nodes_by_label(label, batch_size)
            deletion_summary[label] = deleted
        
        # Delete unlabeled nodes
        with self.driver.session() as session:
            result = session.run("MATCH (n) WHERE size(labels(n)) = 0 RETURN count(n) as count")
            unlabeled_count = result.single()["count"]
        
        if unlabeled_count > 0:
            logger.info(f"\n[{len(labels) + 1}/{len(labels) + 1}]")
            deleted = self.delete_unlabeled_nodes(batch_size)
            deletion_summary["(unlabeled)"] = deleted
        
        return deletion_summary
    
    def verify_deletion(self):
        """Verify that all nodes have been deleted"""
        logger.info("\n" + "=" * 70)
        logger.info("VERIFYING DELETION...")
        
        with self.driver.session() as session:
            result = session.run("MATCH (n) RETURN count(n) as count")
            node_count = result.single()["count"]
            
            result = session.run("MATCH ()-[r]->() RETURN count(r) as count")
            rel_count = result.single()["count"]
            
            if node_count == 0 and rel_count == 0:
                logger.info("✓✓✓ SUCCESS: Database is completely empty! ✓✓✓")
                logger.info("  Nodes: 0")
                logger.info("  Relationships: 0")
            else:
                logger.warning(f"⚠ WARNING: Database not empty:")
                logger.warning(f"  Nodes remaining: {node_count:,}")
                logger.warning(f"  Relationships remaining: {rel_count:,}")
                
                if node_count > 0:
                    logger.info("\nRemaining nodes by label:")
                    result = session.run("""
                        MATCH (n)
                        RETURN labels(n) as labels, count(n) as count
                        ORDER BY count DESC
                    """)
                    for record in result:
                        label_str = ":".join(record["labels"]) if record["labels"] else "(unlabeled)"
                        logger.info(f"  {label_str}: {record['count']:,}")
        
        logger.info("=" * 70)
    
    def run(self, batch_size=10000):
        """Execute the full node deletion process"""
        try:
            # Check for relationships first
            if not self.check_relationships():
                return
            
            # Show initial stats
            stats, unlabeled = self.get_node_stats()
            total_nodes = sum(stats.values()) + unlabeled
            
            if total_nodes == 0:
                logger.info("\n✓ No nodes found. Database is already empty.")
                return
            
            # Confirm with user
            logger.info("\n" + "=" * 70)
            response = input(f"⚠️  Delete ALL {total_nodes:,} nodes? This cannot be undone! (yes/no): ")
            if response.lower() != 'yes':
                logger.info("Deletion cancelled.")
                return
            
            logger.info("\n🗑️  Starting node deletion...\n")
            overall_start = time.time()
            
            # Delete all nodes
            deletion_summary = self.delete_all_nodes(batch_size)
            
            # Verify
            self.verify_deletion()
            
            # Summary
            elapsed = time.time() - overall_start
            total_deleted = sum(deletion_summary.values())
            
            logger.info("\n" + "=" * 70)
            logger.info("DELETION SUMMARY:")
            for label in sorted(deletion_summary.keys()):
                count = deletion_summary[label]
                logger.info(f"  {label}: {count:,}")
            logger.info(f"\n  TOTAL deleted: {total_deleted:,}")
            logger.info(f"  Time elapsed: {elapsed:.2f} seconds ({elapsed/60:.2f} minutes)")
            if elapsed > 0:
                logger.info(f"  Deletion rate: {total_deleted/elapsed:.0f} nodes/second")
            logger.info("=" * 70)
            
        except Exception as e:
            logger.error(f"❌ Error during deletion: {e}", exc_info=True)
        finally:
            self.close()


def main():
    """Main execution function"""
    logger.info("=" * 70)
    logger.info("DELETE ALL NODES")
    logger.info("=" * 70)
    logger.info("⚠️  WARNING: This will delete ALL nodes in the database!")
    logger.info("")
    logger.info("PREREQUISITE: All relationships must be deleted first.")
    logger.info("If relationships exist, this script will abort.")
    logger.info("")
    logger.info("Expected node types:")
    logger.info("  DrugBank: Drug, Category, BrandName, Synonym, Salt, FoodInteraction")
    logger.info("  🔥 Mayo Clinic: Supplement, ActiveIngredient, Medication, Symptom")
    logger.info("=" * 70)
    
    deleter = NodeDeleter()
    deleter.run(batch_size=10000)


if __name__ == "__main__":
    main()
