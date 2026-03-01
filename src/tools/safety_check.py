"""
Safety Check - Interaction Specialist

Checks for dangerous interactions between supplements and medications
using the graph and (optionally) an LLM.

This specialist is designed to mirror the style of other tools in the
project: it exposes a single LangGraph node (`safety_check`) and keeps
its internal logic encapsulated.  The interaction pathways are
configurable via a registry, and a Claude (Anthropic) model can be used
for two kinds of reasoning:

  1. Assessing the clinical severity of each individual interaction
     (`USE_CLAUDE_ASSESSMENT` env var)
  2. Generating the Cypher query for a given pathway so the agent can
     be more "agentic" (`USE_CLAUDE_SAFETY_QUERY` env var)

For backwards compatibility the tool falls back to hardcoded queries and
severity levels when the LLM is unavailable or disabled, so the overall
behavior remains the same even when the agentic features fail.

Reads from state : supplements_list, medications_list (and optional
  `safety_pathways` to override default set)
Writes to state  : safety_checked, safety_results, evidence_chain
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional

from anthropic import Anthropic

from src.graph.connections import graph_interface
from src.prompt_loader import load_prompt

logger = logging.getLogger(__name__)


# ==================== CONFIGURATION FLAGS ====================
USE_CLAUDE_ASSESSMENT = os.getenv("USE_CLAUDE_ASSESSMENT", "true").lower() in ["true", "1", "yes"]
CLAUDE_TIMEOUT = int(os.getenv("CLAUDE_TIMEOUT", "10"))  # seconds

# When set, the agent will ask Claude to produce the Cypher query rather
# than using the built-in template.  This makes the specialist more
# agentic; the previous hardcoded queries are still used as a fallback.
USE_CLAUDE_QUERY = os.getenv("USE_CLAUDE_SAFETY_QUERY", "false").lower() in ["true", "1", "yes"]


# ==================== LLM HELPERS ====================

def _get_llm_client() -> Optional[Anthropic]:
    """Create an Anthropic client if an API key is available.

    Returns None if the key is missing or the client cannot be created.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        logger.debug("no ANTHROPIC_API_KEY found, LLM features disabled")
        return None

    try:
        return Anthropic(api_key=api_key)
    except Exception as e:
        logger.error(f"failed to create Anthropic client: {e}")
        return None


# ==================== PATHWAY REGISTRY ====================

class Pathway:
    def __init__(self, name: str, description: str, query_template: str):
        self.name = name
        self.description = description
        self.query_template = query_template


class PathwayRegistry:
    """Central registry of safety pathways and their Cypher templates."""

    _pathways: Dict[str, Pathway] = {}

    @classmethod
    def register(cls, pathway: Pathway):
        cls._pathways[pathway.name] = pathway

    @classmethod
    def get_pathway(cls, name: str) -> Pathway:
        try:
            return cls._pathways[name]
        except KeyError:
            raise ValueError(f"unknown safety pathway: {name}")

    @classmethod
    def list_pathways(cls) -> List[str]:
        return list(cls._pathways.keys())


# populate registry with the four built-in templates
PathwayRegistry.register(
    Pathway(
        name="DIRECT_SUPPLEMENT_MEDICATION",
        description="Direct interaction recorded on SUPPLEMENT_INTERACTS_WITH",
        query_template="""
MATCH (s:Supplement)-[r:SUPPLEMENT_INTERACTS_WITH]->(m:Medication)
WHERE toLower(s.supplement_name) IN $supplements_lower
  AND toLower(m.medication_name) IN $medications_lower
RETURN s.supplement_name AS supplement,
       m.medication_name AS target,
       r.interaction_description AS description,
       'MODERATE' AS severity,
       null AS detail,
       'DIRECT_SUPPLEMENT_MEDICATION' AS pathway
""",
    )
)

PathwayRegistry.register(
    Pathway(
        name="DRUG_DRUG_INTERACTION",
        description="Supplement and medication share an interacting drug",
        query_template="""
MATCH (s:Supplement)-[:CONTAINS]->(ai:ActiveIngredient)-[:EQUIVALENT_TO]->(d1:Drug)
      -[r:INTERACTS_WITH]->(d2:Drug)<-[:MEDICATION_CONTAINS_DRUG]-(m:Medication)
WHERE toLower(s.supplement_name) IN $supplements_lower
  AND toLower(m.medication_name) IN $medications_lower
RETURN s.supplement_name AS supplement,
       m.medication_name AS target,
       r.description AS description,
       'HIGH' AS severity,
       d1.drug_name + ' interacts with ' + d2.drug_name AS detail,
       'DRUG_DRUG_INTERACTION' AS pathway
""",
    )
)

PathwayRegistry.register(
    Pathway(
        name="HIDDEN_PHARMA_EQUIVALENCE",
        description="Supplement contains ingredient equivalent to a drug",
        query_template="""
MATCH (s:Supplement)-[:CONTAINS]->(a:ActiveIngredient)
      -[:EQUIVALENT_TO]->(d:Drug)<-[:MEDICATION_CONTAINS_DRUG]-(m:Medication)
WHERE toLower(s.supplement_name) IN $supplements_lower
  AND toLower(m.medication_name) IN $medications_lower
RETURN s.supplement_name AS supplement,
       m.medication_name AS target,
       'Contains equivalent pharmaceutical ingredient - duplication risk' AS description,
       'HIGH' AS severity,
       a.active_ingredient + ' = ' + d.drug_name AS detail,
       'HIDDEN_PHARMA_EQUIVALENCE' AS pathway
""",
    )
)

PathwayRegistry.register(
    Pathway(
        name="SIMILAR_EFFECT",
        description="Supplement has similar pharmacological effect to drug",
        query_template="""
MATCH (s:Supplement)-[:HAS_SIMILAR_EFFECT_TO]->(c:Category)
      <-[:BELONGS_TO]-(d:Drug)<-[:MEDICATION_CONTAINS_DRUG]-(m:Medication)
WHERE toLower(s.supplement_name) IN $supplements_lower
  AND toLower(m.medication_name) IN $medications_lower
RETURN s.supplement_name AS supplement,
       m.medication_name AS target,
       'Similar pharmacological effect - additive or antagonistic risk' AS description,
       'MODERATE' AS severity,
       c.category AS detail,
       'SIMILAR_EFFECT' AS pathway
""",
    )
)


# ==================== AGENTIC LLM UTILITIES ====================

def _assess_severity(interaction: Dict[str, Any], pathway: Pathway) -> Dict[str, str]:
    """Return a severity and reasoning, possibly using Claude."""
    default_sev = interaction.get("severity", "MODERATE")
    default_reason = f"Default based on {pathway.name} pathway"

    if not USE_CLAUDE_ASSESSMENT:
        return {"severity": default_sev, "reasoning": default_reason}

    client = _get_llm_client()
    if not client:
        return {"severity": default_sev, "reasoning": default_reason}

    try:
        prompt = load_prompt("safety_assessment")["assess"].format(
            supplement=interaction.get("supplement", ""),
            medication=interaction.get("target", ""),
            description=interaction.get("description", ""),
            pathway=pathway.name,
            current_severity=default_sev,
        )
        resp = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=300,
            temperature=0,
            timeout=CLAUDE_TIMEOUT,
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp.content[0].text.strip()
        # attempt to parse JSON
        try:
            data = json.loads(text)
            sev = data.get("severity", default_sev)
            reason = data.get("reasoning", default_reason)
        except json.JSONDecodeError:
            logger.warning("could not parse severity JSON from LLM: %r", text)
            sev = default_sev
            reason = default_reason
        return {"severity": sev, "reasoning": reason}
    except Exception as e:
        logger.warning("LLM severity assessment failed: %s", e)
        return {"severity": default_sev, "reasoning": default_reason}


def _generate_safety_query(
    pathway_name: str,
    supplements: List[str],
    medications: List[str],
    schema_str: str,
    client: Anthropic,
) -> str:
    """Ask Claude to produce a Cypher query for a pathway.
    """
    prompt = load_prompt("safety_query")["generate"].format(
        pathway=pathway_name,
        supplements=supplements,
        medications=medications,
        schema_str=schema_str,
    )
    try:
        resp = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            temperature=0,
            timeout=CLAUDE_TIMEOUT,
            messages=[{"role": "user", "content": prompt}],
        )
        query = resp.content[0].text.strip()
        # strip markdown backticks if present
        if query.startswith("```"):
            query = query.strip("`")
        return query
    except Exception as e:
        logger.warning("safety query generation failed: %s", e)
        return ""


# ==================== CORE CHECKER ====================

def _check_pathway(
    pathway_name: str,
    supplements: List[str],
    medications: List[str],
) -> Dict[str, Any]:
    """Run a safety check for a single named pathway."""
    try:
        pathway = PathwayRegistry.get_pathway(pathway_name)
    except ValueError as e:
        logger.error(str(e))
        return {"pathway": pathway_name, "status": "error", "error": str(e), "interactions": []}

    parameters = {
        "supplements_lower": [s.lower() for s in supplements],
        "medications_lower": [m.lower() for m in medications],
    }

    # optionally let Claude build the query
    if USE_CLAUDE_QUERY:
        client = _get_llm_client()
        if client:
            schema_str = ""  # could be graph_interface.schema.to_prompt_string() if available
            cypher = _generate_safety_query(pathway.name, supplements, medications, schema_str, client)
            if cypher:
                try:
                    results = graph_interface.execute_query(cypher, parameters) or []
                except Exception as e:
                    logger.warning("generated cypher execution failed: %s", e)
                    results = graph_interface.execute_query(pathway.query_template, parameters) or []
            else:
                results = graph_interface.execute_query(pathway.query_template, parameters) or []
        else:
            results = graph_interface.execute_query(pathway.query_template, parameters) or []
    else:
        results = graph_interface.execute_query(pathway.query_template, parameters) or []

    # add severity/clinical reasoning
    if results:
        for ix in results:
            sev_info = _assess_severity(ix, pathway)
            ix["severity"] = sev_info["severity"]
            ix["clinical_reasoning"] = sev_info["reasoning"]

    logger.info(f"Pathway '{pathway_name}': found {len(results)} interactions")
    return {"pathway": pathway_name, "count": len(results), "interactions": results}


# ==================== RESULT FORMATTING ====================

def _build_results(
    all_interactions: List[Dict[str, Any]],
    supplements_checked: List[str],
    medications_checked: List[str],
) -> Dict[str, Any]:
    by_pathway: Dict[str, List] = {}
    for ix in all_interactions:
        by_pathway.setdefault(ix.get("pathway", "UNKNOWN"), []).append(ix)

    if not all_interactions:
        status = "not_found"
        summary = (
            f"No interactions found between {', '.join(supplements_checked)} and {', '.join(medications_checked)}"
        )
    else:
        status = "found"
        pathway_summary = ", ".join(
            f"{pathway}: {len(records)}" for pathway, records in by_pathway.items()
        )
        summary = (
            f"Found {len(all_interactions)} interaction(s) between {', '.join(supplements_checked)} and {', '.join(medications_checked)} ({pathway_summary})"
        )

    return {
        "specialist": "safety",
        "status": status,
        "entities_checked": supplements_checked + medications_checked,
        "summary": summary,
        "interactions": all_interactions,
        "by_pathway": by_pathway,
        "supplements_checked": supplements_checked,
        "medications_checked": medications_checked,
    }


# ==================== LANGGRAPH NODE ====================

def safety_check(state: Dict[str, Any]) -> Dict[str, Any]:
    print("\n" + "=" * 60)
    print("🔬 SAFETY CHECK: Checking supplement-medication interactions...")
    print("=" * 60)

    current_supplements = state.get("supplements_list", [])
    candidate_supplements = state.get("candidate_supplements_list", [])
    supplements = list(dict.fromkeys(current_supplements + candidate_supplements))
    medications = state.get("medications_list", [])

    # early exits
    if not supplements:
        results = {
            "specialist": "safety",
            "status": "no_supplements",
            "entities_checked": [],
            "summary": "No supplements identified to check",
            "interactions": [],
            "by_pathway": {},
        }
        return {
            "safety_checked": True,
            "safety_results": results,
            "evidence_chain": state.get("evidence_chain", [])
            + ["Safety check: skipped — no supplements to check"],
        }

    if not medications:
        results = {
            "specialist": "safety",
            "status": "no_medications",
            "entities_checked": supplements,
            "summary": "No medications to check against",
            "interactions": [],
            "by_pathway": {},
        }
        return {
            "safety_checked": True,
            "safety_results": results,
            "evidence_chain": state.get("evidence_chain", [])
            + ["Safety check: skipped — no medications to check against"],
        }

    if candidate_supplements:
        print(f"   Current supplements  : {current_supplements if current_supplements else 'none'}")
        print(f"   Candidate supplements: {candidate_supplements}")
        print(f"   Checking combined    : {supplements}")
    else:
        print(f"   Supplements : {supplements}")
    print(f"   Medications : {medications}")

    # determine which pathways to run
    requested = state.get("safety_pathways")
    pathways_to_check = requested if isinstance(requested, list) else PathwayRegistry.list_pathways()

    all_interactions: List[Dict[str, Any]] = []
    for pw in pathways_to_check:
        print(f"\n   Pathway: {pw}")
        outcome = _check_pathway(pw, supplements, medications)
        inters = outcome.get("interactions", [])
        if inters:
            for ix in inters:
                print(f"      ⚠️  [{ix.get('pathway')}] {ix.get('supplement')} ↔ {ix.get('target')}: {str(ix.get('description',''))[:80]}")
            all_interactions.extend(inters)
        else:
            print("      ✅ no interactions found")

    results = _build_results(all_interactions, supplements, medications)

    print(f"\n   {'⚠️  Interactions found' if all_interactions else '✅ No interactions found'}: {results['summary']}")
    print("=" * 60 + "\n")

    return {
        "safety_checked": True,
        "safety_results": results,
        "evidence_chain": state.get("evidence_chain", [])
        + [f"Safety check: {results['summary']}"]
    }
