# Testing

Human-in-the-loop evaluation across four specialist agents. Each test runner loads a golden dataset CSV, runs the full workflow, and writes a plain-text report for manual review. There is no automated scoring — outputs are assessed by hand.

---

## Structure

```
tests/
├── safety/
│   ├── golden_dataset_safety.csv
│   ├── test_runner_safety.py
│   └── reports/
├── deficiency/
│   ├── golden_dataset_deficiency.csv
│   ├── test_runner_deficiency.py
│   └── reports/
├── recommendation/
│   ├── golden_dataset_recommendation.csv
│   ├── test_runner_recommendation.py
│   └── reports/
└── multi_agent/
    ├── golden_dataset_multi_agent.csv
    ├── test_runner_multi_agent.py
    └── reports/
```

---

## Running Tests

Each runner follows the same interface. Run from the project root.

**Run all tests in a suite:**
```bash
python tests/safety/test_runner_safety.py
python tests/deficiency/test_runner_deficiency.py
python tests/recommendation/test_runner_recommendation.py
python tests/multi_agent/test_runner_multi_agent.py
```

**Run a single test by ID:**
```bash
python tests/safety/test_runner_safety.py --test-id 12
```

**Use a custom dataset:**
```bash
python tests/safety/test_runner_safety.py --dataset-path path/to/custom.csv
```

Reports are saved automatically to `tests/{type}/reports/report_{timestamp}.txt`.

---

## Golden Datasets

| Suite | Tests | What it covers |
|---|---|---|
| `safety` | 23 | Supplement–drug interaction detection across known/unknown pairs, multiple meds, missing data edge cases |
| `deficiency` | 10 | Nutrient deficiency detection via dietary restrictions; verifies data gaps in medication/supplement depletion pathways |
| `recommendation` | 10 | Condition-based supplement recommendations; exact match, keyword fallback, exclusion of current supplements |
| `multi_agent` | 15 | Full pipeline routing across all three specialists; safety + deficiency + recommendation in combination |

---

## Report Format

Each report contains one block per test case:

```
Test {id}
  Question:     ...
  Type:         ...
  Desc:         ...

  PATIENT PROFILE:
    Medications:          ...
    Supplements:          ...
    Conditions:           ...
    Dietary Restrictions: ...

  [specialist-specific output fields]

  FINAL ANSWER:
    ...
```

Specialist-specific fields per suite:

- **Safety** — `SAFETY QUERIES` (generated Cypher per supplement), `INTERACTIONS FOUND`
- **Deficiency** — `DIET-BASED DEFICIENCIES`, `MEDICATION-BASED DEPLETIONS`, `SUPPLEMENT-BASED DEPLETIONS`, `CRITICAL OVERLAPS`, `SUMMARY`
- **Recommendation** — `RECOMMENDATIONS FOUND`
- **Multi-agent** — all of the above, depending on which specialists were invoked

---

## Review Process

After running a suite, open the `.txt` report and check each test against its `Desc` field, which documents the expected behavior. The description encodes what data exists in the graph and what the system should return — e.g. `found 1+1 — Fish Oil and Warfarin multiple pathways` or `EDGE — nothing_to_check: all inputs empty`.

Flag issues directly in the report or as tracked action items.
