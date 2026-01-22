#!/usr/bin/env python3
"""
Delete All Data from Neo4j Database
Removes ALL relationships and nodes in the correct order:
  1. Delete all relationships first
  2. Delete all nodes second
Leaves you with a completely empty database.
"""

from neo4j import GraphDatabase
import logging
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class CompleteDataDeleter:
    def __init__(self, uri="bolt://localhost:7687", user="neo4j", password="supplements"):
        """Initialize connection to Neo4j"""
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        logger.info(f"Connected to Neo4j at {uri}")
    
    def close(self):
        """Close the Neo4j driver"""
        self.driver.close()
    
    # ==================== RELATIONSHIP DELETION ====================
    
    def get_all_relationship_types(self):
        """Get all relationship types in the database"""
        with self.driver.session() as session:
            result = session.run("CALL db.relationshipTypes()")
            all_types = [record["relationshipType"] for record in result]
            return all_types
    
    def get_relationship_stats(self):
        """Get statistics for all relationships"""
        all_types = self.get_all_relationship_types()
        
        if not all_types:
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
            
        return stats, total
    
    def delete_relationship_type(self, rel_type, batch_size=5000):
        """Delete a specific relationship type in batches"""
        logger.info(f"  Deleting {rel_type} relationships...")
        
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
                
                logger.info(f"    Iteration {iteration}: Deleted {deleted:,} ({elapsed:.2f}s) | Total: {total_deleted:,}")
            
            logger.info(f"  ✓ {rel_type}: {total_deleted:,} deleted")
            return total_deleted
    
    def delete_all_relationships(self, batch_size=5000):
        """Delete all relationships from the database"""
        logger.info("\n" + "="*60)
        logger.info("STEP 1: DELETING ALL RELATIONSHIPS")
        logger.info("="*60)
        
        all_types = self.get_all_relationship_types()
        
        if not all_types:
            logger.info("✓ No relationships found. Skipping to nodes.")
            return {}
        
        # Show what will be deleted
        stats, total = self.get_relationship_stats()
        logger.info(f"\nFound {len(all_types)} relationship types ({total:,} total):")
        for rel_type, count in sorted(stats.items()):
            logger.info(f"  {rel_type}: {count:,}")
        
        logger.info(f"\nDeleting {total:,} relationships in batches of {batch_size:,}...\n")
        
        deletion_summary = {}
        sorted_types = sorted(all_types)
        
        for i, rel_type in enumerate(sorted_types, 1):
            logger.info(f"[{i}/{len(sorted_types)}]")
            deleted = self.delete_relationship_type(rel_type, batch_size)
            deletion_summary[rel_type] = deleted
        
        return deletion_summary
    
    # ==================== NODE DELETION ====================
    
    def get_node_stats(self):
        """Get statistics for all nodes by label"""
        with self.driver.session() as session:
            # Get all node labels
            result = session.run("CALL db.labels()")
            labels = [record["label"] for record in result]
            
            if not labels:
                # Check for unlabeled nodes
                result = session.run("MATCH (n) WHERE size(labels(n)) = 0 RETURN count(n) as count")
                unlabeled = result.single()["count"]
                return {}, unlabeled
            
            stats = {}
            total = 0
            
            for label in labels:
                result = session.run(f"""
                    MATCH (n:`{label}`)
                    RETURN count(n) as count
                """)
                count = result.single()["count"]
                stats[label] = count
                total += count
            
            # Check for unlabeled nodes
            result = session.run("MATCH (n) WHERE size(labels(n)) = 0 RETURN count(n) as count")
            unlabeled = result.single()["count"]
            
            return stats, unlabeled
    
    def delete_nodes_by_label(self, label, batch_size=5000):
        """Delete nodes with a specific label in batches"""
        logger.info(f"  Deleting {label} nodes...")
        
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
                
                logger.info(f"    Iteration {iteration}: Deleted {deleted:,} ({elapsed:.2f}s) | Total: {total_deleted:,}")
            
            logger.info(f"  ✓ {label}: {total_deleted:,} deleted")
            return total_deleted
    
    def delete_unlabeled_nodes(self, batch_size=5000):
        """Delete nodes without any labels"""
        logger.info(f"  Deleting unlabeled nodes...")
        
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
                
                logger.info(f"    Iteration {iteration}: Deleted {deleted:,} ({elapsed:.2f}s) | Total: {total_deleted:,}")
            
            logger.info(f"  ✓ Unlabeled nodes: {total_deleted:,} deleted")
            return total_deleted
    
    def delete_all_nodes(self, batch_size=5000):
        """Delete all nodes from the database"""
        logger.info("\n" + "="*60)
        logger.info("STEP 2: DELETING ALL NODES")
        logger.info("="*60)
        
        stats, unlabeled = self.get_node_stats()
        total_nodes = sum(stats.values()) + unlabeled
        
        if total_nodes == 0:
            logger.info("✓ No nodes found. Database already empty.")
            return {}
        
        # Show what will be deleted
        logger.info(f"\nFound {len(stats)} node labels ({total_nodes:,} total):")
        for label, count in sorted(stats.items()):
            logger.info(f"  {label}: {count:,}")
        if unlabeled > 0:
            logger.info(f"  (unlabeled): {unlabeled:,}")
        
        logger.info(f"\nDeleting {total_nodes:,} nodes in batches of {batch_size:,}...\n")
        
        deletion_summary = {}
        
        # Get node labels
        with self.driver.session() as session:
            result = session.run("CALL db.labels()")
            labels = [record["label"] for record in result]
        
        # Delete labeled nodes
        for i, label in enumerate(sorted(labels), 1):
            logger.info(f"[{i}/{len(labels)}]")
            deleted = self.delete_nodes_by_label(label, batch_size)
            deletion_summary[label] = deleted
        
        # Delete unlabeled nodes
        if unlabeled > 0:
            logger.info(f"[{len(labels) + 1}/{len(labels) + 1}]")
            deleted = self.delete_unlabeled_nodes(batch_size)
            deletion_summary["(unlabeled)"] = deleted
        
        return deletion_summary
    
    # ==================== VERIFICATION ====================
    
    def verify_deletion(self):
        """Verify that database is completely empty"""
        logger.info("\n" + "="*60)
        logger.info("VERIFICATION")
        logger.info("="*60)
        
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
                logger.warning(f"⚠ WARNING: Database not completely empty:")
                logger.warning(f"  Nodes remaining: {node_count:,}")
                logger.warning(f"  Relationships remaining: {rel_count:,}")
        
        logger.info("="*60)
    
    # ==================== MAIN EXECUTION ====================
    
    def run(self, batch_size=5000):
        """Execute the complete deletion process"""
        try:
            # Show initial database state
            logger.info("\n" + "="*60)
            logger.info("CURRENT DATABASE STATE")
            logger.info("="*60)
            
            rel_stats, total_rels = self.get_relationship_stats()
            node_stats, unlabeled = self.get_node_stats()
            total_nodes = sum(node_stats.values()) + unlabeled
            
            logger.info(f"Relationships: {total_rels:,}")
            logger.info(f"Nodes: {total_nodes:,}")
            
            if total_rels == 0 and total_nodes == 0:
                logger.info("\n✓ Database is already empty. Nothing to delete.")
                return
            
            # Confirm with user
            logger.info("\n" + "="*60)
            response = input(
                f"⚠️  WARNING: Delete ALL data from Neo4j?\n"
                f"   - {total_rels:,} relationships\n"
                f"   - {total_nodes:,} nodes\n"
                f"   This CANNOT be undone!\n"
                f"\nType 'yes' to continue: "
            )
            
            if response.lower() != 'yes':
                logger.info("Deletion cancelled by user.")
                return
            
            logger.info("\n🗑️  Starting complete database deletion...\n")
            overall_start = time.time()
            
            # Step 1: Delete all relationships
            rel_summary = self.delete_all_relationships(batch_size)
            
            # Step 2: Delete all nodes
            node_summary = self.delete_all_nodes(batch_size)
            
            # Verify
            self.verify_deletion()
            
            # Final summary
            elapsed = time.time() - overall_start
            total_rel_deleted = sum(rel_summary.values())
            total_node_deleted = sum(node_summary.values())
            
            logger.info("\n" + "="*60)
            logger.info("DELETION SUMMARY")
            logger.info("="*60)
            
            logger.info("\nRelationships deleted:")
            for rel_type, count in sorted(rel_summary.items()):
                logger.info(f"  {rel_type}: {count:,}")
            logger.info(f"  Subtotal: {total_rel_deleted:,}")
            
            logger.info("\nNodes deleted:")
            for label, count in sorted(node_summary.items()):
                logger.info(f"  {label}: {count:,}")
            logger.info(f"  Subtotal: {total_node_deleted:,}")
            
            logger.info(f"\n  GRAND TOTAL: {total_rel_deleted + total_node_deleted:,} items deleted")
            logger.info(f"  Time elapsed: {elapsed:.2f} seconds ({elapsed/60:.2f} minutes)")
            if elapsed > 0:
                logger.info(f"  Deletion rate: {(total_rel_deleted + total_node_deleted)/elapsed:.0f} items/second")
            logger.info("="*60)
            
        except Exception as e:
            logger.error(f"❌ Error during deletion: {e}", exc_info=True)
        finally:
            self.close()


def main():
    """Main execution function"""
    logger.info("="*60)
    logger.info("COMPLETE DATABASE DELETION")
    logger.info("="*60)
    logger.info("This script will:")
    logger.info("  1. Delete ALL relationships")
    logger.info("  2. Delete ALL nodes")
    logger.info("  3. Leave you with a completely empty database")
    logger.info("="*60)
    
    deleter = CompleteDataDeleter()
    deleter.run(batch_size=5000)


if __name__ == "__main__":
    main()