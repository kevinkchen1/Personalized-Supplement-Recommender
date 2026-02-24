# 💊 Personalized Supplement Safety Advisor

An AI-powered system that detects dangerous supplement-medication interactions, identifies nutrient deficiencies, and provides personalized supplement recommendations using a biomedical knowledge graph and multi-agent architecture.

Built with **Neo4j** (knowledge graph), **LangGraph** (multi-agent orchestration), **Claude API** (reasoning), and **Streamlit** (web interface).

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Setup](#setup)
- [Running the Application](#running-the-application)
- [Testing](#testing)
- [Project Structure](#project-structure)

---

## Overview

Millions of people take dietary supplements without knowing they can dangerously interact with prescription medications. This system solves that by:

- **Safety Checks** — Detecting supplement-drug interactions across 4 pathways (direct, drug-drug, hidden pharma equivalence, similar effects)
- **Deficiency Analysis** — Identifying nutrient gaps from diet, supplements, and medications
- **Personalized Recommendations** — Suggesting safe supplements for conditions/symptoms, filtered against your medication profile

The system uses multi-hop reasoning over a Neo4j knowledge graph built from **DrugBank** and **Mayo Clinic** data, with a supervisor agent dynamically routing queries to specialist tools.

---

## Architecture

```
User Question
    ↓
Entity Extractor  (LLM: extract meds, supplements, conditions from question + profile)
    ↓
Entity Normalizer (LLM: generate Cypher to map names → database IDs using live schema)
    ↓
Supervisor        (LLM: decide which specialist to call next)
    ↓                         ↑
    ├─→ Safety Check ─────────┘  (hardcoded Cypher: 4-pathway UNION query)
    ├─→ Deficiency Check ─────┘  (hardcoded Cypher: diet + medication + supplement depletion)
    ├─→ Recommendation ───────┘  (hardcoded Cypher: TREATS relationships + keyword fallback)
    ↓
Supervisor → synthesize → END
```

**Key design decisions:**
- **Agents** (LLM-driven): Entity Extractor, Entity Normalizer, Supervisor — these handle ambiguity, typos, and dynamic planning
- **Tools** (hardcoded Cypher): Safety Check, Deficiency Check, Recommendation — these run deterministic queries for reproducibility and speed
- **Module-level singletons** (`connections.py`): GraphInterface and SchemaProvider are initialized once at import time, shared across all nodes without passing through state
- **Schema-aware normalization**: The Entity Normalizer reads live database schema via `SchemaProvider.to_prompt_string()` so the LLM generates valid Cypher against the actual graph structure

---

## Prerequisites

| Dependency | Version | Purpose |
|---|---|---|
| **Python** | 3.12+ (< 3.14) | Runtime |
| **PDM** | Latest | Package management |
| **Neo4j** | 5.x | Knowledge graph database |
| **Anthropic API Key** | — | Claude LLM (entity extraction, normalization, supervisor) |
| **LangSmith API Key** | — | *(Optional)* LangGraph Studio tracing |

### Install PDM

```bash
# macOS
brew install pdm

# Or via pip
pip install pdm
```

### Install and Start Neo4j

You need a running Neo4j instance:

**Neo4j Desktop** (recommended for local dev)
1. Download from [neo4j.com/download](https://neo4j.com/download/)
2. Create a new project and local DBMS
3. Set a password (you'll need this for `.env`)
4. Start the database


---

## Setup

### 1. Clone the Repository

```bash
git clone https://github.com/<your-org>/Personalized-Supplement-Recommender.git
cd Personalized-Supplement-Recommender
```

### 2. Install Dependencies

```bash
pdm install
```

This reads `pyproject.toml` and installs all dependencies into a virtual environment managed by PDM. If PDM creates a new virtualenv (e.g., downloading a compatible Python version), this is expected.

### 3. Configure Environment Variables

Create a `.env` file in the project root:

```bash
# .env

# Required — Claude API for LLM reasoning
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxxxxxxx

# Required — Neo4j connection
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_neo4j_password

# Optional — LangSmith tracing (needed for LangGraph Studio)
LANGSMITH_API_KEY=lsv2_xxxxxxxxxxxxxxxxxxxxx
```


### 4. Load the Knowledge Graph

Before using the system, populate Neo4j with the biomedical data:

```bash
pdm run python scripts/load_data.py
```

This loads DrugBank and Mayo Clinic data (22 CSV files) into the knowledge graph, creating nodes for Drugs, Supplements, Medications, Nutrients, Symptoms, DietaryRestrictions, and their relationships.

---

## Running the Application

### LangGraph Studio (Recommended)

LangGraph Studio provides a visual interface for running queries and inspecting the agent workflow step-by-step.

**1. Install LangGraph CLI** (if not already in your lock file):

```bash
pdm add "langgraph-cli[inmem]>=0.4.12"
```

If your `pdm.lock` already includes it, just run `pdm install`.

**2. Launch Studio:**

```bash
pdm run studio
```

This starts the LangGraph development server. Open the URL printed in your terminal to access the Studio UI. You can:

- Submit questions with patient profiles as `InputState` (just `user_question` and `patient_profile`)
- Watch the workflow route through Entity Extractor → Normalizer → Supervisor → Specialists in real time
- Inspect state at each node to see extracted entities, normalized IDs, and specialist results
- Replay and debug individual executions

> **Note:** LangGraph Studio requires `LANGSMITH_API_KEY` in your `.env`. Get one at [smith.langchain.com](https://smith.langchain.com/).

### Streamlit Web App

```bash
pdm run streamlit run src/web/app.py
```

Opens at `http://localhost:8501`. Enter medications, supplements, conditions, and diet in the sidebar, then ask questions like *"Is Fish Oil safe with Warfarin?"*

---

## Testing

Run these steps in order to verify each component of the system is working.

### 1. Verify Neo4j Connection

```bash
pdm run python -c "
from dotenv import load_dotenv; import os; load_dotenv()
from src.graph.graph_interface import GraphInterface
g = GraphInterface(os.getenv('NEO4J_URI','bolt://localhost:7687'), os.getenv('NEO4J_USER','neo4j'), os.getenv('NEO4J_PASSWORD'))
print('✅ Neo4j connected')
schema = g.get_schema_info()
print(f'   Node labels: {schema[\"node_labels\"]}')
print(f'   Relationship types: {len(schema[\"relationship_types\"])} types')
g.close()
"
```

### 2. Verify Knowledge Graph Data

```bash
pdm run python -c "
from dotenv import load_dotenv; import os; load_dotenv()
from src.graph.graph_interface import GraphInterface
g = GraphInterface(os.getenv('NEO4J_URI','bolt://localhost:7687'), os.getenv('NEO4J_USER','neo4j'), os.getenv('NEO4J_PASSWORD'))
stats = g.execute_query('''
  MATCH (s:Supplement) WITH count(s) as supplements
  MATCH (d:Drug) WITH supplements, count(d) as drugs
  MATCH (m:Medication) WITH supplements, drugs, count(m) as medications
  RETURN supplements, drugs, medications
''')
print(f'✅ Knowledge graph loaded: {stats[0]}')
g.close()
"
```

### 3. Verify Claude API Key

```bash
pdm run python -c "
from dotenv import load_dotenv; import os; load_dotenv()
from anthropic import Anthropic
client = Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
r = client.messages.create(model='claude-sonnet-4-20250514', max_tokens=50, messages=[{'role':'user','content':'Say OK'}])
print(f'✅ Claude API working: {r.content[0].text}')
"
```

### 4. Verify Schema Provider and Singletons

```bash
pdm run python -c "
from dotenv import load_dotenv; load_dotenv()
from src.graph.connections import graph_interface, schema_provider
print('✅ Singletons initialized (GraphInterface + SchemaProvider)')
print(f'   Node labels: {schema_provider.get_node_labels()}')
print(f'   Relationship types: {len(schema_provider.get_relationship_types())} types')
print(f'   Sample Drug names: {schema_provider.get_sample_values(\"Drug\", \"drug_name\")}')
"
```

### 5. Verify LangGraph Workflow Builds

```bash
pdm run python -c "
from src.workflow.graph_builder import build_workflow
w = build_workflow()
print('✅ Workflow compiled successfully')
"
```

### 6. Verify LangGraph Studio

```bash
pdm run studio
```

If it launches without errors and prints a URL, it's working.

### 7. Run Full Pipeline (End-to-End)

```bash
pdm run python -c "
from dotenv import load_dotenv; load_dotenv()
from src.workflow.graph_builder import build_workflow
from src.workflow.state import create_initial_state

w = build_workflow()
state = create_initial_state(
    user_question='Is Fish Oil safe with Warfarin?',
    patient_profile={'medications': 'Warfarin', 'supplements': 'Fish Oil', 'conditions': [], 'dietary_restrictions': []}
)
result = w.invoke(state)
print('✅ End-to-end pipeline complete')
print(f'   Iterations: {result.get(\"iterations\", 0)}')
print(f'   Safety checked: {result.get(\"safety_checked\", False)}')
print(f'   Evidence chain:')
for e in result.get('evidence_chain', []):
    print(f'     → {e}')
"
```

---

## Project Structure

```
├── .env                            # API keys and database credentials (not committed)
├── pyproject.toml                  # PDM project config and dependencies
├── pdm.lock                        # Locked dependency versions
├── langgraph.json                  # LangGraph Studio configuration
├── data/
│   ├── drugbank_data/              # DrugBank CSVs (12 files)
│   └── mayo_clinic_data/           # Mayo Clinic CSVs (10 files)
├── scripts/
│   └── load_data.py                # Knowledge graph data loader (22 CSVs → Neo4j)
└── src/
    ├── agents/                     # LLM-driven nodes (require Claude API)
    │   ├── entity_extractor.py     # Node 1: Extract entities from question + profile
    │   ├── entity_normalizer.py    # Node 2: Map names → database IDs via LLM Cypher
    │   └── supervisor.py           # Node 3: Plan which specialist to call next
    ├── graph/                      # Database infrastructure
    │   ├── graph_interface.py      # Neo4j connection wrapper and query execution
    │   ├── schema.py               # SchemaProvider — loads DB schema for LLM prompts
    │   └── connections.py          # Module-level singletons (GraphInterface + SchemaProvider)
    ├── tools/                      # Deterministic specialist nodes (hardcoded Cypher)
    │   ├── safety_check.py         # 4-pathway supplement-medication interaction check
    │   ├── deficiency_check.py     # Diet + medication + supplement nutrient depletion
    │   └── recommendation.py       # Find supplements for conditions via TREATS relationships
    └── workflow/                   # LangGraph orchestration
        ├── state.py                # ConversationState and InputState definitions
        ├── graph_builder.py        # Build and compile the LangGraph workflow
        └── routing.py              # Supervisor decision → node name mapping
```

### Module Boundaries

| Layer | Files | LLM? | Purpose |
|---|---|---|---|
| **Agents** | `entity_extractor.py`, `entity_normalizer.py`, `supervisor.py` | Yes | Handle ambiguity, typos, dynamic planning |
| **Tools** | `safety_check.py`, `deficiency_check.py`, `recommendation.py` | No | Run deterministic Cypher queries |
| **Graph** | `graph_interface.py`, `schema.py`, `connections.py` | No | Database access and schema introspection |
| **Workflow** | `state.py`, `graph_builder.py`, `routing.py` | No | LangGraph state, graph construction, routing |

---

