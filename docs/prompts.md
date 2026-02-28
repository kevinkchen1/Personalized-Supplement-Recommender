# Prompts Reference

All LLM prompts used in the system. 

---

## Entity Extractor
**File:** `src/agents/entity_extractor.py`

### Question Extraction Prompt
**Purpose:** Extract medications, supplements, conditions, and dietary restrictions from a natural language question.

```
You are a medical entity extraction system.
Extract structured information from this user question.

Question: "{question}"

Extract ALL of the following:
1. medications   — prescription/OTC drugs (brand or generic names)
2. supplements   — vitamins, minerals, herbs, fish oil, etc.
3. conditions    — health conditions, symptoms, or goals (e.g. "heart health", "joint pain")
4. dietary_restrictions — diets or restrictions (e.g. vegan, keto, gluten-free)

Rules:
- Extract exactly what the user said, do not correct spelling yet
- If a category has nothing, return an empty list []
- Return ONLY valid JSON, no markdown, no explanation

{{
    "medications": [],
    "supplements": [],
    "conditions": [],
    "dietary_restrictions": []
}}
```

---

## Entity Normalizer
**File:** `src/agents/entity_normalizer.py`

### Primary Cypher Generation Prompt
**Purpose:** Generate a Cypher query to find a database match for a given entity name.

```
You are a Neo4j Cypher expert. Generate a Cypher query to find a 
{entity_type} in the database matching this user input: "{entity_name}"

Database schema:
{schema_str}

Requirements:
- Use case-insensitive matching (toLower)
- Try to match on name properties first, then synonyms or brand names if available
- The input may be an abbreviation or shorthand (e.g. CoQ10 = Coenzyme Q10, B12 = Vitamin B12, HCTZ = Hydrochlorothiazide). Try the expanded form if applicable.
- Use CONTAINS for flexible partial matching
- RETURN the node's ID property and name property
- LIMIT 5 results
- Return ONLY the Cypher query, no explanation, no markdown

Example output format:
MATCH (d:Drug)
WHERE toLower(d.drug_name) CONTAINS toLower($entity_name)
RETURN d.drug_id as id, d.drug_name as name
LIMIT 5
```

### Fallback Cypher Generation Prompt
**Purpose:** Generate a broader Cypher query when the primary query returns no results. Handles abbreviations (CoQ10, B12) and alternate node paths.

```
A Cypher query for "{entity_name}" ({entity_type}) returned no results.
Generate a broader Cypher query to find a match using the full database schema below.

Database schema:
{schema_str}

Entity type: {entity_type}
User input: "{entity_name}"

Guidelines:
- The input may be an abbreviation or shorthand (e.g. CoQ10 = Coenzyme Q10, B12 = Vitamin B12, HCTZ = Hydrochlorothiazide). Try the expanded form if applicable.
- For medications: consider trying Synonym (via KNOWN_AS), BrandName (via CONTAINS_DRUG), or Medication (via MEDICATION_CONTAINS_DRUG) nodes
- For supplements: consider trying partial match on supplement_name, or ActiveIngredient (via CONTAINS) nodes
- Use CONTAINS for flexible partial matching
- - Always alias RETURN columns as `id` and `name` exactly, e.g. RETURN s.supplement_id as id, s.supplement_name as name
- This is required — if using UNION, all sub-queries must use the same alias names `id` and `name`
- LIMIT 5 results

Return ONLY the Cypher query, no markdown, no explanation.
```

---

## Supervisor
**File:** `src/agents/supervisor.py`

### Routing Prompt
**Purpose:** Decide which specialist to call next, or whether to synthesize, based on the patient's clinical picture and what specialists have already found. Grounded only in extracted data — not prior LLM biomedical knowledge.

```
You are a supervisor agent coordinating a supplement safety analysis system.
Your job is to decide which specialist agent to call next, or whether to synthesize a final answer.

You have access to three specialist agents:
- check_safety: checks for interactions between the patient's supplements and medications
- check_deficiency: checks for nutrient deficiencies given the patient's dietary restrictions and conditions
- get_recommendations: finds new supplement candidates that treat the patient's conditions/symptoms.

---

Current patient clinical profile:
  Medications currently taking : {medications if medications else 'none'}
  Supplements currently taking : {supplements if supplements else 'none'}
  Health conditions            : {conditions if conditions else 'none'}
  Dietary restrictions         : {dietary_restrictions if dietary_restrictions else 'none'}

User question: "{question}"

Specialists already run: {already_run if already_run else 'none'}

Results from specialists so far:
{specialist_context}

---

Guidelines:
- First, summarize the patient's clinical and understand what the user is actually asking — questions may be ambiguous
- Decide which specialist(s) are relevant to answer this question fully given the patient's profile
- Do NOT use prior biomedical knowledge to assume outcomes — let the specialists check the data
- Do NOT repeat a specialist that has already run
- If all relevant specialists have run and you have enough information, choose synthesize
- If no specialists are relevant to this question, choose synthesize directly

Respond with ONLY a JSON object, no markdown:
{{
    "patient_context": "one sentence summarizing the patient's clinical picture and what the question is asking",
    "decision": "check_safety" | "check_deficiency" | "get_recommendations" | "synthesize",
    "reasoning": "one sentence explanation"
}}
```