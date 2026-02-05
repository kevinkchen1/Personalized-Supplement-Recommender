"""
Test script for query_generator.py + query_executor.py

Run from the src/ directory:
    cd Personalized-Supplement-Recommender/src
    python tests/test_tools.py

Requires:
    - Neo4j running at bolt://localhost:7687
    - .env file with NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD
"""

import os
import sys
import time
from pathlib import Path

# Ensure src/ is on the path
src_dir = Path(__file__).parent.parent
sys.path.insert(0, str(src_dir))

from dotenv import load_dotenv
load_dotenv()

from graph.graph_interface import GraphInterface
from tools.query_generator import (
    QueryGenerator,
    QueryType,
    generate_safety_queries,
    generate_comprehensive_safety_query,
    generate_supplement_info_query,
    generate_symptom_recommendation_query,
)
from tools.query_executor import (
    QueryExecutor,
    run_safety_check,
    run_comprehensive_safety,
    run_supplement_info,
)


# ======================================================================
# Setup
# ======================================================================

def connect():
    """Connect to Neo4j and return (graph, executor, generator)."""
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "")

    print(f"Connecting to {uri} as {user}...")
    graph = GraphInterface(uri, user, password)
    print("✅ Connected!\n")

    return graph, QueryExecutor(graph), QueryGenerator()


# ======================================================================
# Tests
# ======================================================================

def test_database_basics(executor):
    """Verify the database has expected node types and counts."""
    print("=" * 60)
    print("TEST 1: Database basics")
    print("=" * 60)

    labels = [
        "Supplement", "Medication", "Drug", "ActiveIngredient",
        "Category", "BrandName", "Synonym", "Salt",
        "FoodInteraction", "Symptom",
    ]

    for label in labels:
        r = executor.execute(f"MATCH (n:{label}) RETURN count(n) AS cnt")
        if r['success'] and r['data']:
            print(f"  {label:25s} → {r['data'][0]['cnt']:>8,} nodes")
        else:
            print(f"  {label:25s} → ❌ {r.get('error', 'no data')}")

    # Relationship counts
    print()
    rels = [
        "INTERACTS_WITH", "CONTAINS", "EQUIVALENT_TO", "CONTAINS_DRUG",
        "BELONGS_TO", "HAS_SIMILAR_EFFECT_TO", "TREATS", "CAN_CAUSE",
        "HAS_FOOD_INTERACTION", "HAS_SALT_FORM", "KNOWN_AS",
    ]
    for rel in rels:
        r = executor.execute(f"MATCH ()-[r:{rel}]->() RETURN count(r) AS cnt")
        if r['success'] and r['data']:
            print(f"  {rel:30s} → {r['data'][0]['cnt']:>8,} relationships")
        else:
            print(f"  {rel:30s} → ❌ {r.get('error', 'no data')}")

    print()


def test_sample_data(executor):
    """Show some sample data so we know what names to use in queries."""
    print("=" * 60)
    print("TEST 2: Sample data")
    print("=" * 60)

    print("\n  Sample Supplements:")
    r = executor.execute(
        "MATCH (s:Supplement) RETURN s.supplement_name AS name, "
        "s.supplement_id AS id LIMIT 10"
    )
    if r['success']:
        for row in r['data']:
            print(f"    [{row['id']}] {row['name']}")

    print("\n  Sample Medications:")
    r = executor.execute(
        "MATCH (m:Medication) RETURN m.medication_name AS name, "
        "m.medication_id AS id LIMIT 10"
    )
    if r['success']:
        for row in r['data']:
            print(f"    [{row['id']}] {row['name']}")

    print("\n  Sample Supplement→ActiveIngredient→Drug chains:")
    r = executor.execute("""
        MATCH (s:Supplement)-[:CONTAINS]->(a:ActiveIngredient)-[:EQUIVALENT_TO]->(d:Drug)
        RETURN s.supplement_name AS supplement,
               a.active_ingredient AS ingredient,
               d.drug_name AS drug
        LIMIT 5
    """)
    if r['success']:
        for row in r['data']:
            print(f"    {row['supplement']} → {row['ingredient']} ≡ {row['drug']}")

    print("\n  Sample Supplement→INTERACTS_WITH relationships:")
    r = executor.execute("""
        MATCH (s:Supplement)-[r:INTERACTS_WITH]->(target)
        RETURN s.supplement_name AS supplement,
               labels(target)[0] AS target_type,
               COALESCE(target.medication_name, target.drug_name) AS target_name
        LIMIT 10
    """)
    if r['success']:
        for row in r['data']:
            print(f"    {row['supplement']} → [{row['target_type']}] {row['target_name']}")

    print()


def test_query_generator(gen):
    """Test that all query types generate valid queries."""
    print("=" * 60)
    print("TEST 3: QueryGenerator - all query types")
    print("=" * 60)

    test_cases = [
        ('supplement_medication_interaction', {
            'supplement_name': 'Fish Oil',
            'medication_names': ['Warfarin'],
        }),
        ('supplement_drug_interaction', {
            'supplement_name': 'Fish Oil',
            'medication_names': ['Warfarin'],
        }),
        ('hidden_pharma_equivalence', {
            'supplement_name': 'Red Yeast Rice',
            'medication_names': ['Lipitor'],
        }),
        ('similar_effect_overlap', {
            'supplement_name': 'Fish Oil',
            'medication_names': ['Warfarin'],
        }),
        ('drug_drug_interaction', {
            'medication_names': ['Warfarin', 'Aspirin'],
        }),
        ('comprehensive_safety', {
            'supplement_name': 'Fish Oil',
            'medication_names': ['Warfarin'],
        }),
        ('food_interactions', {
            'medication_names': ['Warfarin'],
        }),
        ('supplement_side_effects', {
            'supplement_name': 'Fish Oil',
        }),
        ('supplements_for_symptom', {
            'symptom': 'blood pressure',
        }),
        ('supplement_info', {
            'supplement_name': 'Fish Oil',
        }),
        ('find_supplement', {'name': 'Fish'}),
        ('find_medication', {'name': 'War'}),
        ('find_drug', {'name': 'Warfarin'}),
    ]

    all_ok = True
    for query_type, params in test_cases:
        result = gen.generate_query(query_type, params)
        has_query = result.get('query') is not None
        has_error = result.get('error') is not None
        status = "✅" if has_query else "❌"
        print(f"  {status} {query_type:45s} → query={'yes' if has_query else 'NO'}")
        if has_error:
            print(f"     Error: {result['error']}")
            all_ok = False

    # Test error handling
    print("\n  Error handling:")
    r = gen.generate_query('bogus_type', {})
    print(f"  {'✅' if r.get('error') else '❌'} Invalid type → error='{r.get('error', '')[:50]}'")
    r = gen.generate_query('comprehensive_safety', {'supplement_name': 'X'})
    print(f"  {'✅' if r.get('error') else '❌'} Missing params → error='{r.get('error', '')[:50]}'")

    print()
    return all_ok


def test_execute_generated_queries(executor, gen):
    """Generate queries and execute them against the live database."""
    print("=" * 60)
    print("TEST 4: Generate + Execute against live DB")
    print("=" * 60)

    test_cases = [
        ("Find supplements matching 'Fish'", 'find_supplement', {'name': 'Fish'}),
        ("Find medications matching 'War'", 'find_medication', {'name': 'War'}),
        ("Supplement info for Fish Oil", 'supplement_info', {'supplement_name': 'Fish Oil'}),
        ("Side effects of St. John's Wort", 'supplement_side_effects', {'supplement_name': "St. John's Wort"}),
        ("Comprehensive: Fish Oil vs Warfarin", 'comprehensive_safety', {
            'supplement_name': 'Fish Oil',
            'medication_names': ['Warfarin'],
        }),
        ("Hidden pharma: Red Yeast Rice", 'hidden_pharma_equivalence', {
            'supplement_name': 'Red Yeast Rice',
            'medication_names': [],
        }),
    ]

    for label, query_type, params in test_cases:
        print(f"\n  --- {label} ---")
        q = gen.generate_query(query_type, params)

        if not q.get('query'):
            print(f"  ⚠️  No query generated: {q.get('error')}")
            continue

        r = executor.execute_query_dict(q)
        print(f"  Success: {r['success']} | Results: {r['count']} | Time: {r['execution_time']:.3f}s")

        if r['success'] and r['data']:
            # Show first 3 rows
            for i, row in enumerate(r['data'][:3]):
                print(f"    Row {i+1}: {row}")
            if r['count'] > 3:
                print(f"    ... and {r['count'] - 3} more")
        elif r['error']:
            print(f"  Error: {r['error']}")

    print()


def test_convenience_functions(graph):
    """Test the one-call convenience functions."""
    print("=" * 60)
    print("TEST 5: Convenience functions")
    print("=" * 60)

    # run_safety_check (4 separate queries)
    print("\n  --- run_safety_check ---")
    result = run_safety_check(graph, 'Fish Oil', ['Warfarin'])
    print(f"  Total interactions: {result['count']}")
    print(f"  Queries: {result['queries_succeeded']}/{result['queries_run']} succeeded")
    if result['by_query_type']:
        for qt, rows in result['by_query_type'].items():
            print(f"    {qt}: {len(rows)} results")

    # run_comprehensive_safety (1 UNION query)
    print("\n  --- run_comprehensive_safety ---")
    result = run_comprehensive_safety(graph, 'Fish Oil', ['Warfarin'])
    print(f"  Interactions: {result['count']}")
    if result['data']:
        pathways = {}
        for row in result['data']:
            p = row.get('pathway', '?')
            pathways[p] = pathways.get(p, 0) + 1
        for p, n in pathways.items():
            print(f"    {p}: {n}")

    # run_supplement_info
    print("\n  --- run_supplement_info ---")
    result = run_supplement_info(graph, 'Fish Oil')
    print(f"  Success: {result['success']}, Results: {result['count']}")
    if result['data']:
        info = result['data'][0]
        print(f"    Name: {info.get('supplement')}")
        print(f"    Active ingredients: {info.get('active_ingredients')}")
        print(f"    Equivalent drugs: {info.get('equivalent_drugs')}")
        print(f"    Treats: {info.get('treats_symptoms')}")
        print(f"    Side effects: {info.get('side_effects')}")
        print(f"    Similar to categories: {info.get('similar_effect_categories')}")

    print()


def test_query_history(executor):
    """Verify query history tracking works."""
    print("=" * 60)
    print("TEST 6: Query history")
    print("=" * 60)

    history = executor.get_query_history(limit=5)
    print(f"  Tracked {len(history)} recent queries:")
    for h in history:
        status = h.get('status', '?')
        t = h.get('execution_time', 0)
        q = h['query'][:70].replace('\n', ' ').strip()
        count = h.get('count', '?')
        print(f"    [{status:7s}] {q}... → {count} rows ({t:.3f}s)")

    print()


# ======================================================================
# Main
# ======================================================================

def main():
    print("\n" + "🧪" * 30)
    print("  QUERY GENERATOR + EXECUTOR TEST SUITE")
    print("🧪" * 30 + "\n")

    graph, executor, gen = connect()

    try:
        test_database_basics(executor)
        test_sample_data(executor)
        test_query_generator(gen)
        test_execute_generated_queries(executor, gen)
        test_convenience_functions(graph)
        test_query_history(executor)

        print("=" * 60)
        print("🎉 ALL TESTS COMPLETE!")
        print("=" * 60)

    except Exception as e:
        print(f"\n💥 Test failed with error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        graph.close()
        print("Connection closed.\n")


if __name__ == "__main__":
    main()
