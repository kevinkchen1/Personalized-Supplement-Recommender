# Supplement Safety Knowledge Graph Structure

## Overview
This knowledge graph integrates DrugBank and Mayo Clinic data to identify dangerous interactions between supplements and medications.

---

## Node Types (Entities)

| Node Type | Count | Properties | Source |
|-----------|-------|------------|--------|
| **Supplement** | 28 | supplement_id, supplement_name, safety_rating | Mayo Clinic |
| **ActiveIngredient** | 71 | active_ingredient_id, active_ingredient | Mayo Clinic |
| **Medication** | 55 | medication_id, medication_name | Mayo Clinic |
| **Drug** | 19,830 | drug_id, drug_name, description, indication, type | DrugBank |
| **Category** | 4,649 | category_id, category | DrugBank |
| **Symptom** | 288 | symptom_id, symptom_name | Mayo Clinic |
| **BrandName** | 248,483 | brand_name_id, brand_name | DrugBank |
| **Salt** | 2,960 | salt_id, salt_name | DrugBank |
| **Synonym** | 52,027 | synonym_id, synonym | DrugBank |
| **FoodInteraction** | 1,429 | food_interaction_id, description | DrugBank |

**Total Nodes:** 329,820

---

## Relationship Types (Edges)

### Critical Safety Relationships (NEW - Curated)

| From | Relationship | To | Count | Properties |
|------|--------------|-----|-------|------------|
| Supplement | **CONTAINS** | ActiveIngredient | 71 | is_primary (boolean) |
| ActiveIngredient | **EQUIVALENT_TO** | Drug | 39 | equivalence_type, notes |
| Supplement | **HAS_SIMILAR_EFFECT_TO** | Category | ~50+ | confidence, notes |

### Mayo Clinic Relationships

| From | Relationship | To | Count |
|------|--------------|-----|-------|
| Supplement | SUPPLEMENT_INTERACTS_WITH | Medication | ~50+ |
| Supplement | CAN_CAUSE | Symptom | 224 |
| Supplement | TREATS | Symptom | 128 |
| Medication | MEDICATION_CONTAINS_DRUG | Drug | 55 |

### DrugBank Relationships

| From | Relationship | To | Count |
|------|--------------|-----|-------|
| Drug | BELONGS_TO | Category | 107,361 |
| Drug | INTERACTS_WITH | Drug | 2,909,540 |
| BrandName | CONTAINS_DRUG | Drug | 248,483 |
| Drug | KNOWN_AS | Synonym | 52,027 |
| Drug | HAS_SALT_FORM | Salt | 2,960 |
| Drug | HAS_FOOD_INTERACTION | FoodInteraction | 2,549 |

**Total Edges:** 3,446,998

---
