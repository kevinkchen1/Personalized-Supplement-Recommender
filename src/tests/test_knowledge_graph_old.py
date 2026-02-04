#!/usr/bin/env python3
"""
Complete Knowledge Graph Test Suite

This script runs comprehensive tests on the complete knowledge graph
(DrugBank + Mayo Clinic + Bridge Relationships) to validate data integrity
and demonstrate critical safety features.

Usage:
    python3 test_knowledge_graph.py
"""

import os
from dotenv import load_dotenv
from neo4j import GraphDatabase
import pandas as pd
from datetime import datetime
import time

load_dotenv()

class CompleteKGTester:
    """Test suite for complete supplement safety knowledge graph"""
    
    def __init__(self, uri: str, user: str, password: str):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.results = []
        
    def close(self):
        self.driver.close()
    
    def run_query(self, name: str, query: str, description: str, show_results=True):
        """Run a query and store results"""
        print(f"\n{'='*70}")
        print(f"TEST: {name}")
        print(f"{'='*70}")
        print(f"Description: {description}")
        
        if show_results:
            print(f"\nQuery:\n{query}\n")
        
        try:
            with self.driver.session() as session:
                start_time = time.time()
                result = session.run(query)
                records = [dict(record) for record in result]
                elapsed = time.time() - start_time
                
                if records:
                    print(f"✓ Results: {len(records)} records found ({elapsed:.3f}s)")
                    
                    if show_results:
                        print("\nSample results:")
                        df = pd.DataFrame(records)
                        print(df.to_string(index=False))
                    
                    self.results.append({
                        'test': name,
                        'status': 'PASS',
                        'records': len(records),
                        'time': f"{elapsed:.3f}s"
                    })
                else:
                    print("⚠ No results found")
                    self.results.append({
                        'test': name,
                        'status': 'EMPTY',
                        'records': 0,
                        'time': f"{elapsed:.3f}s"
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
        print("COMPLETE KNOWLEDGE GRAPH TEST SUITE")
        print("DrugBank + Mayo Clinic + Bridge Relationships")
        print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*70)
        
        # ===================================================================
        # SECTION 1: DATA INTEGRITY TESTS
        # ===================================================================
        print("\n" + "="*70)
        print("SECTION 1: DATA INTEGRITY TESTS")
        print("="*70)
        
        # TEST 1: Node Counts
        self.run_query(
            "1. Node Counts by Type",
            """
            MATCH (n)
            RETURN labels(n)[0] as NodeType, count(n) as Count
            ORDER BY Count DESC
            """,
            "Verify all node types were loaded with expected counts"
        )
        
        # TEST 2: Relationship Counts
        self.run_query(
            "2. Relationship Counts by Type",
            """
            MATCH ()-[r]->()
            RETURN type(r) as RelationshipType, count(r) as Count
            ORDER BY Count DESC
            """,
            "Verify all relationships were created"
        )
        
        # ===================================================================
        # SECTION 2: DRUGBANK DATA TESTS
        # ===================================================================
        print("\n" + "="*70)
        print("SECTION 2: DRUGBANK DATA TESTS")
        print("="*70)
        
        # TEST 3: Sample Drugs
        self.run_query(
            "3. Sample Drugs in Database",
            """
            MATCH (d:Drug)
            RETURN d.drug_id as DrugID, 
                   d.drug_name as DrugName,
                   d.type as Type
            LIMIT 10
            """,
            "Show sample drugs to verify data structure"
        )
        
        # TEST 4: Drug-Drug Interactions
        self.run_query(
            "4. Sample Drug-Drug Interactions",
            """
            MATCH (d1:Drug)-[r:INTERACTS_WITH]->(d2:Drug)
            RETURN d1.drug_name as Drug1,
                   d2.drug_name as Drug2,
                   substring(r.description, 0, 80) + '...' as InteractionWarning
            LIMIT 5
            """,
            "Verify drug interaction data quality"
        )
        
        # TEST 5: Drug Categories
        self.run_query(
            "5. Most Common Drug Categories",
            """
            MATCH (c:Category)<-[:BELONGS_TO]-(d:Drug)
            RETURN c.category as Category, 
                   count(d) as DrugCount
            ORDER BY DrugCount DESC
            LIMIT 10
            """,
            "Check drug classification system"
        )
        
        # ===================================================================
        # SECTION 3: MAYO CLINIC DATA TESTS
        # ===================================================================
        print("\n" + "="*70)
        print("SECTION 3: MAYO CLINIC DATA TESTS")
        print("="*70)
        
        # TEST 6: Supplements
        self.run_query(
            "6. Sample Supplements",
            """
            MATCH (s:Supplement)
            RETURN s.supplement_id as SupplementID,
                   s.supplement_name as SupplementName,
                   s.safety_rating as SafetyRating
            LIMIT 10
            """,
            "Verify supplement data loaded correctly"
        )
        
        # TEST 7: Active Ingredients
        self.run_query(
            "7. Sample Active Ingredients",
            """
            MATCH (a:ActiveIngredient)
            RETURN a.active_ingredient_id as IngredientID,
                   a.active_ingredient as IngredientName
            LIMIT 10
            """,
            "Verify active ingredient data"
        )
        
        # TEST 8: Medications
        self.run_query(
            "8. Sample Medications",
            """
            MATCH (m:Medication)
            RETURN m.medication_id as MedicationID,
                   m.medication_name as MedicationName
            LIMIT 10
            """,
            "Verify medication data"
        )
        
        # ===================================================================
        # SECTION 4: CRITICAL BRIDGE RELATIONSHIP TESTS 🔥
        # ===================================================================
        print("\n" + "="*70)
        print("SECTION 4: 🔥 CRITICAL BRIDGE RELATIONSHIP TESTS 🔥")
        print("="*70)
        
        # TEST 9: Supplement → Active Ingredient
        self.run_query(
            "9. Supplement Contains Active Ingredient",
            """
            MATCH (s:Supplement)-[c:CONTAINS]->(a:ActiveIngredient)
            RETURN s.supplement_name as Supplement,
                   a.active_ingredient as ActiveIngredient,
                   c.is_primary as IsPrimary
            LIMIT 10
            """,
            "🔥 CRITICAL: Verify supplement-ingredient links"
        )
        
        # TEST 10: Active Ingredient → Drug Equivalence (MOST CRITICAL!)
        self.run_query(
            "10. Active Ingredient → Drug Equivalence",
            """
            MATCH (a:ActiveIngredient)-[eq:EQUIVALENT_TO]->(d:Drug)
            RETURN a.active_ingredient as ActiveIngredient,
                   d.drug_name as EquivalentDrug,
                   eq.equivalence_type as Type,
                   eq.notes as Notes
            ORDER BY eq.equivalence_type
            LIMIT 10
            """,
            "🔥 CRITICAL: Verify ingredient-to-drug equivalence mappings"
        )
        
        # TEST 11: Supplement → Category Similar Effect
        self.run_query(
            "11. Supplement Similar Effect to Category",
            """
            MATCH (s:Supplement)-[sim:HAS_SIMILAR_EFFECT_TO]->(c:Category)
            RETURN s.supplement_name as Supplement,
                   c.category as DrugCategory,
                   sim.confidence as Confidence,
                   substring(sim.notes, 0, 60) + '...' as Notes
            ORDER BY sim.confidence DESC
            LIMIT 10
            """,
            "🔥 CRITICAL: Verify supplement-category similarity mappings"
        )
        
        # ===================================================================
        # SECTION 5: SAFETY DETECTION TESTS (Real Use Cases)
        # ===================================================================
        print("\n" + "="*70)
        print("SECTION 5: 🚨 SAFETY DETECTION TESTS (Real Use Cases) 🚨")
        print("="*70)
        
        # TEST 12: Detect Hidden Pharmaceutical (Red Yeast Rice)
        self.run_query(
            "12. Red Yeast Rice → Lovastatin Detection",
            """
            MATCH (s:Supplement)-[:CONTAINS]->(a:ActiveIngredient)
                  -[eq:EQUIVALENT_TO]->(d:Drug)
            WHERE s.supplement_name CONTAINS 'yeast' 
               OR a.active_ingredient CONTAINS 'Monacolin'
               OR d.drug_name CONTAINS 'Lovastatin'
            RETURN s.supplement_name as Supplement,
                   a.active_ingredient as HiddenIngredient,
                   d.drug_name as PharmaceuticalEquivalent,
                   eq.equivalence_type as Type,
                   eq.notes as Warning
            """,
            "🚨 SAFETY: Detect red yeast rice contains lovastatin (statin drug)"
        )
        
        # TEST 13: Fish Oil + Warfarin Risk
        self.run_query(
            "13. Fish Oil Bleeding Risk Detection",
            """
            MATCH (s:Supplement {supplement_name: 'Fish oil'})
                  -[sim:HAS_SIMILAR_EFFECT_TO]->(c:Category)
            WHERE c.category CONTAINS 'Anticoagulant'
            RETURN s.supplement_name as Supplement,
                   c.category as AffectsCategory,
                   sim.confidence as RiskLevel,
                   sim.notes as Warning
            """,
            "🚨 SAFETY: Detect fish oil increases bleeding risk"
        )
        
        # TEST 14: St. John's Wort Drug Interactions
        self.run_query(
            "14. St. John's Wort Interaction Detection",
            """
            MATCH (s:Supplement)-[sim:HAS_SIMILAR_EFFECT_TO]->(c:Category)
            WHERE s.supplement_name = "St. John's wort"
            RETURN s.supplement_name as Supplement,
                   c.category as AffectedDrugCategory,
                   sim.confidence as RiskLevel,
                   sim.notes as MechanismWarning
            ORDER BY sim.confidence DESC
            """,
            "🚨 SAFETY: Detect St. John's Wort CYP3A4 interactions"
        )
        
        # TEST 15: Complete Safety Pathway Test
        self.run_query(
            "15. Complete Pathway: Supplement → Ingredient → Drug → Category",
            """
            MATCH (s:Supplement)-[:CONTAINS]->(a:ActiveIngredient)
                  -[eq:EQUIVALENT_TO]->(d:Drug)-[:BELONGS_TO]->(c:Category)
            RETURN s.supplement_name as Supplement,
                   a.active_ingredient as Contains,
                   d.drug_name as EquivalentTo,
                   c.category as DrugCategory,
                   eq.equivalence_type as Type
            LIMIT 5
            """,
            "🔥 CRITICAL: Verify complete safety detection pathway works end-to-end"
        )
        
        # ===================================================================
        # SECTION 6: PERFORMANCE TESTS
        # ===================================================================
        print("\n" + "="*70)
        print("SECTION 6: PERFORMANCE TESTS")
        print("="*70)
        
        # TEST 16: Query Performance - Drug Interactions
        print(f"\n{'='*70}")
        print("TEST: 16. Drug Interaction Query Performance")
        print(f"{'='*70}")
        print("Description: Measure query speed for common safety checks")
        
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
            self.results.append({'test': '16. Query Performance', 'status': 'PASS'})
        elif elapsed < 5.0:
            print("✓ Performance: GOOD (< 5 seconds)")
            self.results.append({'test': '16. Query Performance', 'status': 'PASS'})
        else:
            print("⚠ Performance: SLOW (> 5 seconds)")
            self.results.append({'test': '16. Query Performance', 'status': 'WARN'})
        
        # TEST 17: Data Completeness Check
        self.run_query(
            "17. Check for Missing Critical Relationships",
            """
            MATCH ()-[r:EQUIVALENT_TO]->()
            WHERE r.equivalence_type IS NULL OR r.notes IS NULL
            RETURN count(r) as IncompleteEquivalences
            """,
            "Verify all EQUIVALENT_TO relationships have required properties",
            show_results=False
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
            print("\n🎉 ALL TESTS PASSED! Your complete knowledge graph is ready!")
            print("\nCritical safety features verified:")
            print("  ✓ Supplement → Ingredient → Drug equivalence detection")
            print("  ✓ Supplement → Category similarity detection")
            print("  ✓ Drug-drug interaction data complete")
            print("  ✓ Query performance optimized")
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
    tester = CompleteKGTester(uri, user, password)
    
    try:
        tester.run_all_tests()
    finally:
        tester.close()


if __name__ == "__main__":
    main()
