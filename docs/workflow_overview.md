# Supplement Safety Recommender — Workflow Overview

An AI-powered supplement safety system using a Neo4j knowledge graph, LangGraph, and Claude.
Identifies dangerous drug-supplement interactions, nutrient deficiency risks, and personalized supplement recommendations.

---

## Workflow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│  INPUT: user_question + patient_profile                         │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
              ┌──────────────────┐
              │ entity_extractor │  LLM (question) + parsing (profile)
              └────────┬─────────┘
                       │  extracted_entities
                       ▼
              ┌──────────────────┐
              │entity_normalizer │  LLM → Cypher → Neo4j
              └────────┬─────────┘
                       │  medications_list, supplements_list,
                       │  dietary_restrictions_list, conditions_list
                       ▼
              ┌──────────────────┐  ◄──────────────────────────┐
              │    supervisor    │  LLM routing decision        │
              └────────┬─────────┘                             │
                       │                                       │
          ┌────────────┼─────────────┐                        │
          │            │             │                         │
          ▼            ▼             ▼                         │
  ┌──────────────┐ ┌──────────┐ ┌────────────────┐            │
  │ safety_check │ │deficiency│ │ recommendation │            │
  │              │ │  _check  │ │                │            │
  └──────┬───────┘ └────┬─────┘ └───────┬────────┘            │
         │              │               │                      │
         └──────────────┴───────────────┘                      │
                        │ specialist results                    │
                        └──────────────────────────────────────┘
                                    │ synthesize
                                    ▼
                           ┌─────────────────┐
                           │    synthesis    │  ← TODO
                           └────────┬────────┘
                                    │
                                    ▼
                            final_answer
```

**Flow summary:**
1. Entity extractor pulls entities from question + profile
2. Entity normalizer maps names to DB IDs via LLM-generated Cypher
3. Supervisor loops — calls specialists one at a time, reads their results+question+patient profile, decides next step
4. Each specialist runs DB query, writes a compact summary back to state
5. Supervisor routes to `synthesize` when all relevant specialists have run
6. Synthesis generates the final answer from all specialist findings

---

## Agents and Tools

See → [Agents & Tools Reference](agents_and_tools.md) for full detail on each.

| Component | File | Type | Role |
|---|---|---|---|
| `entity_extractor` | `src/agents/entity_extractor.py` | **Hybrid** | LLM extracts from question; deterministic parsing for profile |
| `entity_normalizer` | `src/agents/entity_normalizer.py` | **Agent** | LLM generates Cypher to map names → DB IDs |
| `supervisor` | `src/agents/supervisor.py` | **Agent** | LLM routing — decides which specialist to call next |
| `safety_check` | `src/tools/safety_check.py` | **Specialist Agent** | LLM generates Cypher to check safety interaction pathways |
| `deficiency_check` | `src/tools/deficiency_check.py` | **Specialist Tool** | Hardcoded Cypher — checks 3 deficiency pathways |
| `recommendation` | `src/tools/recommendation.py` | **Specialist Tool** | Hardcoded Cypher — finds supplement candidates for conditions |
| `synthesis` | `src/agents/synthesis.py` | **Agent** | Generates final answer from all specialist results |

**Type definitions:**
- **Agent** — LLM-driven, makes decisions or generates queries dynamically
- **Hybrid** — partially LLM (unstructured input), partially deterministic (structured input)
- **Tool** — fully deterministic, hardcoded Cypher queries, no LLM

## Prompts

See → [Prompts Reference](prompts.md) for all LLM prompts with inline comments.

---
