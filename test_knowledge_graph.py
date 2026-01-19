#!/usr/bin/env python3
"""
Neo4j Knowledge Graph Test Suite

This script runs comprehensive tests on your DrugBank knowledge graph
to validate data integrity and demonstrate query capabilities.

Usage:
    python3 test_knowledge_graph.py
"""

import os
from dotenv import load_dotenv
from neo4j import GraphDatabase
import pandas as pd
from datetime import datetime

load_dotenv()

class KnowledgeGraphTester:
    """Test suite for DrugBank knowledge graph"""
    
    def __init__(self, uri: str, user: str, password: str):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.results = []
        
    def close(self):
        self.driver.close()
    
    def run_query(self, name: str, query: str, description: str):
        """Run a query and store results"""
        print(f"\n{'='*70}")
        print(f"TEST: {name}")
        print(f"{'='*70}")
        print(f"Description: {description}")
        print(f"\nQuery:\n{query}\n")
        
        try:
            with self.driver.session() as session:
                result = session.run(query)
                records = [dict(record) for record in result]
                
                if records:
                    print(f"✓ Results: {len(records)} records found")
                    print("\nSample results:")
                    
                    # Display as table
                    df = pd.DataFrame(records)
                    print(df.to_string(index=False))
                    
                    self.results.append({
                        'test': name,
                        'status': 'PASS',
                        'records': len(records)
                    })
                else:
                    print("⚠ No results found")
                    self.results.append({
                        'test': name,
                        'status': 'EMPTY',
                        'records': 0
                    })
                    
        except Exception as e:
            print(f"❌ Error: {e}")
            self.results.append({
                'test': name,
                'status': 'FAIL',
                'error': str(e)
            })
    
    def run_all_tests(self):
        """Run comprehensive test suite"""
        
        print("\n" + "="*70)
        print("DRUGBANK KNOWLEDGE GRAPH TEST SUITE")
        print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*70)
        
        # ===================================================================
        # TEST 1: Node Counts
        # ===================================================================
        self.run_query(
            "1. Node Counts by Type",
            """
            MATCH (n)
            RETURN labels(n)[0] as NodeType, count(n) as Count
            ORDER BY Count DESC
            """,
            "Verify all node types were loaded with expected counts"
        )
        
        # ===================================================================
        # TEST 2: Relationship Counts
        # ===================================================================
        self.run_query(
            "2. Relationship Counts by Type",
            """
            MATCH ()-[r]->()
            RETURN type(r) as RelationshipType, count(r) as Count
            ORDER BY Count DESC
            """,
            "Verify all relationships were created (expect ~2.9M INTERACTS_WITH)"
        )
        
        # ===================================================================
        # TEST 3: Sample Drugs
        # ===================================================================
        self.run_query(
            "3. Sample Drugs in Database",
            """
            MATCH (d:Drug)
            RETURN d.drugbank_id as DrugBankID, 
                   d.name as DrugName,
                   d.type as Type
            LIMIT 10
            """,
            "Show sample drugs to verify data structure"
        )
        
        # ===================================================================
        # TEST 4: Find Drugs with Most Interactions
        # ===================================================================
        self.run_query(
            "4. Drugs with Most Interactions",
            """
            MATCH (d:Drug)-[r:INTERACTS_WITH]->()
            RETURN d.name as Drug, 
                   count(r) as InteractionCount
            ORDER BY InteractionCount DESC
            LIMIT 10
            """,
            "Identify highly-connected drugs (useful for testing queries)"
        )
        
        # ===================================================================
        # TEST 5: Sample Drug Interactions
        # ===================================================================
        self.run_query(
            "5. Sample Drug-Drug Interactions",
            """
            MATCH (d1:Drug)-[r:INTERACTS_WITH]->(d2:Drug)
            RETURN d1.name as Drug1,
                   d2.name as Drug2,
                   substring(r.description, 0, 100) + '...' as InteractionWarning
            LIMIT 10
            """,
            "Verify interaction descriptions are present"
        )
        
        # ===================================================================
        # TEST 6: Drug Categories
        # ===================================================================
        self.run_query(
            "6. Most Common Drug Categories",
            """
            MATCH (c:DrugCategory)<-[:BELONGS_TO_CATEGORY]-(d:Drug)
            RETURN c.category as Category, 
                   count(d) as DrugCount
            ORDER BY DrugCount DESC
            LIMIT 10
            """,
            "Check drug classification system"
        )
        
        # ===================================================================
        # TEST 7: Product-Ingredient Relationships (Critical for Supplements!)
        # ===================================================================
        self.run_query(
            "7. Sample Products and Their Ingredients",
            """
            MATCH (p:DrugProduct)-[r:CONTAINS]->(d:Drug)
            RETURN p.product_name as Product,
                   d.name as ActiveIngredient,
                   r.strength as Strength
            LIMIT 10
            """,
            "Verify product-ingredient links (critical for supplement safety)"
        )
        
        # ===================================================================
        # TEST 8: Drug Synonyms
        # ===================================================================
        self.run_query(
            "8. Drugs with Alternative Names",
            """
            MATCH (d:Drug)-[:KNOWN_AS]->(s:Synonym)
            WITH d, collect(s.name) as Synonyms
            RETURN d.name as OfficialName,
                   size(Synonyms) as NumberOfSynonyms,
                   Synonyms[0..3] as SampleSynonyms
            ORDER BY NumberOfSynonyms DESC
            LIMIT 10
            """,
            "Check alternative name mapping for flexible search"
        )
        
        # ===================================================================
        # TEST 9: Food Interactions
        # ===================================================================
        self.run_query(
            "9. Sample Drug-Food Interactions",
            """
            MATCH (d:Drug)-[r:HAS_FOOD_INTERACTION]->(f:FoodInteraction)
            RETURN d.name as Drug,
                   substring(f.text, 0, 80) + '...' as FoodWarning
            LIMIT 10
            """,
            "Verify dietary guidance is available"
        )
        
        # ===================================================================
        # TEST 10: Salt Forms
        # ===================================================================
        self.run_query(
            "10. Sample Salt Form Relationships",
            """
            MATCH (parent:Drug)-[r:HAS_SALT_FORM]->(salt:Drug)
            RETURN parent.name as ParentDrug,
                   salt.name as SaltForm,
                   r.salt_name as SaltName
            LIMIT 10
            """,
            "Check drug salt form mappings"
        )
        
        # ===================================================================
        # TEST 11: Multi-Hop Query - Find Indirect Interactions
        # ===================================================================
        self.run_query(
            "11. Find Drugs That Share Interaction Partners",
            """
            MATCH (d1:Drug)-[:INTERACTS_WITH]->(common:Drug)<-[:INTERACTS_WITH]-(d2:Drug)
            WHERE d1.name < d2.name
            RETURN d1.name as Drug1,
                   d2.name as Drug2,
                   common.name as CommonInteractor,
                   'Both interact with ' + common.name as Note
            LIMIT 10
            """,
            "Test multi-hop reasoning capability"
        )
        
        # ===================================================================
        # TEST 12: Query Performance Check
        # ===================================================================
        print(f"\n{'='*70}")
        print("TEST: 12. Query Performance Check")
        print(f"{'='*70}")
        print("Description: Measure query execution time")
        
        import time
        start = time.time()
        
        with self.driver.session() as session:
            result = session.run("""
                MATCH (d:Drug)-[r:INTERACTS_WITH]->()
                RETURN count(r) as total
            """)
            count = result.single()['total']
            
        elapsed = time.time() - start
        print(f"\nCounted {count:,} interactions in {elapsed:.3f} seconds")
        
        if elapsed < 1.0:
            print("✓ Performance: EXCELLENT (< 1 second)")
            self.results.append({'test': '12. Query Performance', 'status': 'PASS'})
        elif elapsed < 5.0:
            print("✓ Performance: GOOD (< 5 seconds)")
            self.results.append({'test': '12. Query Performance', 'status': 'PASS'})
        else:
            print("⚠ Performance: SLOW (> 5 seconds) - consider adding more indexes")
            self.results.append({'test': '12. Query Performance', 'status': 'WARN'})
        
        # ===================================================================
        # TEST 13: Data Integrity Checks
        # ===================================================================
        self.run_query(
    "13. Check for Orphaned Relationships",
    """
    MATCH ()-[r:INTERACTS_WITH]->()
    WHERE r.description IS NULL
    RETURN count(r) as OrphanedInteractions
    """,
    "Verify all interactions have descriptions"
)
        
        # ===================================================================
        # SUMMARY
        # ===================================================================
        self.print_summary()
    
    def print_summary(self):
        """Print test summary"""
        print("\n" + "="*70)
        print("TEST SUMMARY")
        print("="*70)
        
        df = pd.DataFrame(self.results)
        print(df.to_string(index=False))
        
        pass_count = len([r for r in self.results if r['status'] == 'PASS'])
        total_count = len(self.results)
        
        print(f"\n{'='*70}")
        print(f"PASSED: {pass_count}/{total_count} tests")
        print(f"Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*70}")
        
        if pass_count == total_count:
            print("\n🎉 ALL TESTS PASSED! Your knowledge graph is ready!")
        else:
            print("\n⚠ Some tests had issues. Review results above.")


def main():
    """Run the test suite"""
    
    # Get database credentials
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD")
    
    if not password:
        print("❌ Error: NEO4J_PASSWORD not set in .env file")
        return
    
    # Run tests
    tester = KnowledgeGraphTester(uri, user, password)
    
    try:
        tester.run_all_tests()
    finally:
        tester.close()


if __name__ == "__main__":
    main()
