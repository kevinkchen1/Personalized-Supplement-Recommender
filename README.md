# Personalized-Supplement-Recommender

## DrugBank Knowledge Graph Setup

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
### 6. Delete Data from Neo4j(only if DB has old data and need to reingest new data)
```bash
python3 delete_drugbank_data.py
```

**Expected time:** 1-2 minutes

When prompted, type `yes` to confirm.

---

### 6. Load Data into Neo4j
```bash
python3 load_drugbank_data_OPTIMIZED.py
```

**Expected time:** 10-15 minutes

When prompted, type `yes` to confirm.

---

### 7. Validate Data (Optional)
```bash
python3 test_knowledge_graph.py
```

Should show: `✓ PASSED: 13/13 tests`

---

## What Gets Loaded

- **19,830** drugs
- **2,910,010** drug-drug interactions
- **448,529** drug products
- **52,027** drug synonyms
- And more (categories, food interactions, salt forms, toxicity data)

---

## Files

- `load_drugbank_data_OPTIMIZED.py` - Main loading script (optimized)
- `test_knowledge_graph.py` - Validation test suite
- `drugbank_data/` - CSV data files (pulled via Git LFS)
