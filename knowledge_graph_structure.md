# Supplement Safety Knowledge Graph Structure

## Overview
This knowledge graph integrates DrugBank and Mayo Clinic data to identify dangerous interactions between supplements and medications.

---

## Node Types (Entities)

| Node Type | Count | Properties | Source |
|-----------|-------|------------|--------|
| **Supplement** | - | supplement_id, supplement_name, safety_rating | Mayo Clinic |
| **ActiveIngredient** | - | active_ingredient_id, active_ingredient | Mayo Clinic |
| **Medication** | - | medication_id, medication_name | Mayo Clinic |
| **Drug** | - | drug_id, drug_name, description, indication, type | DrugBank |
| **Category** | - | category_id, category | DrugBank |
| **Symptom** | - | symptom_id, symptom_name | Mayo Clinic |
| **BrandName** | - | brand_name_id, brand_name | DrugBank |
| **Salt** | - | salt_id, salt_name | DrugBank |
| **Synonym** | - | synonym_id, synonym | DrugBank |
| **FoodInteraction** | - | food_interaction_id, description | DrugBank |

**Total Nodes:** 329,820

---

## Relationship Types (Edges)

### Critical Safety Relationships (NEW - Curated)

| From | Relationship | To | Count | Properties |
|------|--------------|-----|-------|------------|
| Supplement | **CONTAINS** | ActiveIngredient | - | is_primary (boolean) |
| ActiveIngredient | **EQUIVALENT_TO** | Drug | - | equivalence_type, notes |
| Supplement | **HAS_SIMILAR_EFFECT_TO** | Category | - | confidence, notes |

### Mayo Clinic Relationships

| From | Relationship | To | Count |
|------|--------------|-----|-------|
| Supplement | INTERACTS_WITH | Medication | - |
| Supplement | CAN_CAUSE | Symptom | - |
| Supplement | TREATS | Symptom | - |
| Medication | CONTAINS_DRUG | Drug | - |

### DrugBank Relationships

| From | Relationship | To | Count |
|------|--------------|-----|-------|
| Drug | BELONGS_TO | Category | - |
| Drug | INTERACTS_WITH | Drug | - |
| BrandName | CONTAINS_DRUG | Drug | - |
| Drug | KNOWN_AS | Synonym | - |
| Drug | HAS_SALT_FORM | Salt | - |
| Drug | HAS_FOOD_INTERACTION | FoodInteraction | - |

**Total Edges:** 3,446,998

---

## Interaction Detection Pathways

### Pathway 1: Drug Equivalence (Chemical Identity)
```
User Query: "Does supplement contain the same drug I'm taking?"

(Supplement) -[:CONTAINS]-> (ActiveIngredient) -[:EQUIVALENT_TO]-> (Drug)
                                                                      ↓
                                                            [User's Medication]

Example:
Red yeast rice → Monacolin K → Lovastatin (statin drug)
⚠️ WARNING: Taking the SAME drug twice (double dose)
```

### Pathway 2: Similar Pharmacological Effects
```
User Query: "Does supplement affect the same category as my medication?"

(Supplement) -[:HAS_SIMILAR_EFFECT_TO]-> (Category) <-[:BELONGS_TO]- (Drug)
                                                                        ↑
                                                              [User's Medication]

Example:
Ginkgo → Anticoagulants ← Warfarin
⚠️ WARNING: Additive effects (increased bleeding risk)
```

### Pathway 3: Cascading Category Check
```
User Query: "Does supplement contain drug equivalent in same category as my meds?"

(Supplement) -[:CONTAINS]-> (ActiveIngredient) -[:EQUIVALENT_TO]-> (Drug) -[:BELONGS_TO]-> (Category)
                                                                                                 ↑
                                                                                                 |
                                                                         [User's Med] -[:BELONGS_TO]-┘

Example:
Red yeast rice → Monacolin K → Lovastatin → Statins category
User takes: Atorvastatin → Statins category
⚠️ WARNING: Both are statins (double statin dose)
```

---

## Complete Example Query

### Scenario
**User takes:**
- Warfarin (DB00682) - Anticoagulant
- Sertraline (DB01104) - Antidepressant

**User wants to add:**
- St. John's Wort (S20)
- Ginkgo (S10)
- Red yeast rice (S18)

### Cypher Query
```cypher
// User's current medications
WITH ['DB00682', 'DB01104'] as userMedications

// Supplements user wants to add
WITH ['S20', 'S10', 'S18'] as userSupplements, userMedications

// CHECK 1: Drug equivalence (contains same drug)
MATCH (s:Supplement)-[:CONTAINS]->(a:ActiveIngredient)
      -[eq:EQUIVALENT_TO {equivalence_type: 'identical'}]->(d1:Drug)
WHERE s.supplement_id IN userSupplements
  AND d1.drug_id IN userMedications
RETURN 
  "HIGH RISK" as severity,
  s.supplement_name as supplement,
  d1.drug_name as drug,
  "Contains the same drug you're already taking" as warning,
  eq.notes as details

UNION

// CHECK 2: Similar category effects
MATCH (s:Supplement)-[sim:HAS_SIMILAR_EFFECT_TO]->(c:Category)
      <-[:BELONGS_TO]-(d2:Drug)
WHERE s.supplement_id IN userSupplements
  AND d2.drug_id IN userMedications
RETURN 
  CASE sim.confidence 
    WHEN 'high' THEN 'HIGH RISK'
    WHEN 'medium' THEN 'MEDIUM RISK'
    ELSE 'LOW RISK'
  END as severity,
  s.supplement_name as supplement,
  d2.drug_name as drug,
  "Has similar effects to " + c.category as warning,
  sim.notes as details

UNION

// CHECK 3: Direct medication interaction
MATCH (s:Supplement)-[:INTERACTS_WITH]->(m:Medication)
      -[:CONTAINS_DRUG]->(d3:Drug)
WHERE s.supplement_id IN userSupplements
  AND d3.drug_id IN userMedications
RETURN 
  "HIGH RISK" as severity,
  s.supplement_name as supplement,
  d3.drug_name as drug,
  "Direct interaction documented" as warning,
  "" as details

ORDER BY severity DESC, supplement
```

### Expected Results
```
╔═══════════╦═════════════════╦═════════════╦═══════════════════════════════════════╗
║ Severity  ║   Supplement    ║    Drug     ║              Warning                  ║
╠═══════════╬═════════════════╬═════════════╬═══════════════════════════════════════╣
║ HIGH RISK ║ St. John's Wort ║ Sertraline  ║ Has similar effects to Antidepressants║
║           ║                 ║             ║ Details: CYP3A4 inducer (FDA warning) ║
╠═══════════╬═════════════════╬═════════════╬═══════════════════════════════════════╣
║MEDIUM RISK║ Ginkgo          ║ Warfarin    ║ Has similar effects to Anticoagulants ║
║           ║                 ║             ║ Details: Inhibits platelet aggregation║
╠═══════════╬═════════════════╬═════════════╬═══════════════════════════════════════╣
║   SAFE    ║ Red yeast rice  ║ (none)      ║ No interactions found                 ║
║           ║                 ║             ║ Note: Contains lovastatin (a statin)  ║
╚═══════════╩═════════════════╩═════════════╩═══════════════════════════════════════╝
```

---

## Handling Queries Beyond the Knowledge Graph

users may ask questions about:
- ❌ Supplements not in your database (Ashwagandha, Turmeric, etc.)
- ❌ Brand names you don't have (Tylenol, Advil, Motrin)
- ❌ Vague terms ("blood thinners", "herbs for anxiety")
- ❌ Complex scenarios requiring reasoning
- ❌ Dosage-specific questions

## Solution: Hybrid Architecture (Graph + LLM)
knowledge graph is the PRIMARY source, but LangGraph + LLM handle everything else

## Architecture Diagram

```
User Query (Natural Language)
        ↓
┌───────────────────────┐
│  LangGraph Agent      │
│  (Orchestrator)       │
└───────────────────────┘
        ↓
    ┌───┴───┬───────────┐
    ↓       ↓           ↓
┌────────┐ ┌─────┐ ┌─────────┐
│ Neo4j  │ │ LLM │ │   Web   │
│ Graph  │ │     │ │ Search  │
└────────┘ └─────┘ └─────────┘
    │       │           │
    └───┬───┴───────────┘
        ↓
  Synthesized Answer
  (with confidence)
```
### Query Processing Flow

```
1. Entity Extraction (LLM)
   └─> Extract medications, supplements, context from user query

2. Entity Normalization (LLM + Graph)
   └─> Map brand names → generic names → database IDs
   └─> Example: "Tylenol" → "Acetaminophen" → DB00316

3. Primary Check: Neo4j Graph Query
   ├─> Found? → Return HIGH CONFIDENCE result
   └─> Not found? → Proceed to step 4

4. Fallback Strategies (if graph incomplete):
   ├─> Web Search (for recent literature)
   ├─> LLM Reasoning (medical knowledge)
   └─> Combination of both

5. Synthesis (LLM)
   └─> Combine all sources with confidence scores
   └─> Format user-friendly response
```
---

## Implementation Priorities

### Phase 1: Graph-Only Queries
- Implement Neo4j queries for known entities
- Direct relationship traversal
- **Goal:** Handle 28 supplements × 55 medications perfectly

### Phase 2: Add LLM Orchestration
- Entity extraction and normalization
- Query planning and execution
- **Goal:** Understand natural language, map to graph

### Phase 3: Add Fallback Strategies
- Web search integration
- LLM reasoning for unknowns
- **Goal:** Handle ANY supplement/medication

### Phase 4: Confidence Scoring
- Source attribution
- Multi-source synthesis
- **Goal:** Transparent, trustworthy responses

---

## Key Principles

1. **Graph First, Always**
   - Always check graph before using LLM/web
   - Prioritize curated data for safety

2. **Transparent Confidence**
   - Always indicate source and confidence level
   - Never hide uncertainty

3. **Graceful Degradation**
   - Graph → Web → LLM → Admit uncertainty
   - Never fail silently

4. **User Safety**
   - Always recommend consulting healthcare provider
   - Multiple validation layers
   - Clear, actionable warnings

5. **Efficiency**
   - Fast path: Graph lookup (1-5ms)
   - Slow path: Only when necessary
   - Cache common queries

---