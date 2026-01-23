# Personalized-Supplement-Recommender

## Complete Knowledge Graph Setup (DrugBank + Mayo Clinic)

### Prerequisites
1. **Neo4j Database** running (Desktop app or local installation)
2. **Git LFS** installed for large data files

---

## Setup Steps

### 1. Clone Repository and Pull Data
```bash
git clone https://github.com/kevinkchen1/Personalized-Supplement-Recommender.git
cd Personalized-Supplement-Recommender

# Pull large CSV files with Git LFS
git lfs pull
```

---

### 2. Create `.env` File
Create a `.env` file in the project root with your Neo4j credentials:

```bash
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password_here
```

---

### 3. Install Dependencies
```bash
pip3 install pandas python-dotenv neo4j tqdm
```

---

### 4. Start Neo4j Database
- Open **Neo4j Desktop**
- Start your database instance
- Ensure it's running on `bolt://localhost:7687`

---

### 5. Load Complete Knowledge Graph
```bash
python3 scripts/load_data.py
```

**What this does:**
- Automatically clears existing data (if any)
- Creates constraints and indexes
- Loads DrugBank data (drugs, interactions, categories, etc.)
- Loads Mayo Clinic data (supplements, medications, symptoms)
- Creates critical bridge relationships (ingredient equivalence, category similarity)

**Expected time:** 5-10 minutes

When prompted `"⚠️ This will DELETE ALL existing data and reload! Continue? (yes/no):"`, type `yes` to confirm.


## What Gets Loaded

### DrugBank Data:
- **19,830** drugs
- **2,910,010** drug-drug interactions
- **248,483** brand names
- **52,027** drug synonyms
- **4,649** drug categories
- **2,960** salt forms
- **1,429** food interactions

### Mayo Clinic Data:
- **28** supplements
- **71** active ingredients
- **55** medications
- **288** symptoms

### Critical Bridge Relationships:
- **39** active ingredient → drug equivalences (detects hidden pharmaceuticals)
- **71** supplement → active ingredient links
- Supplement → category similarity mappings (detects interaction risks)

**Total:** ~330,000 nodes, ~3.4 million relationships

---

## Project Structure

```
Personalized-Supplement-Recommender/
├── data/
│   ├── drugbank_data/          # DrugBank CSV files
│   └── mayo_clinic_data/       # Mayo Clinic supplement data
├── scripts/
│   ├── load_data.py            # Main loading script
│   ├── delete_all_nodes.py     # Clear nodes (if needed)
│   └── delete_all_relationships.py  # Clear relationships (if needed)
├── knowledge_graph_structure.md     # Complete KG documentation
├── .env                        # Your Neo4j credentials
└── README.md
```


## Documentation

- `knowledge_graph_structure.md` - Complete schema and query examples
- Project proposal - See uploaded PDF for full context
