"""
Supervisor Agent - Workflow Orchestrator

Plans and routes the conversation through specialist agents.
Sits in a loop — called after each specialist returns — and decides
what to do next based on the question, patient data, and what
specialists have already found.

Reasoning is grounded in:
- The user's question and extracted entities
- Compact structured summaries returned by each specialist
- NOT general biomedical knowledge

Type: Agent (LLM-driven)
"""

import json
import logging
import os
from typing import Any, Dict

from anthropic import Anthropic

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 6  # Safety cap — prevents infinite supervisor loops


# ==================== CONTEXT BUILDER ====================

def _build_specialist_context(state: Dict[str, Any]) -> str:
    """
    Build a compact summary of what specialists have found so far.

    Each specialist writes a structured summary dict to state when it runs.
    This function formats those summaries into a readable block for the
    supervisor's prompt.

    Args:
        state: Current ConversationState

    Returns:
        Formatted string describing specialist results, or 'None yet' if
        no specialists have run.
    """
    lines = []

    safety_results = state.get('safety_results')
    if safety_results:
        lines.append(f"Safety check: {json.dumps(safety_results)}")

    deficiency_results = state.get('deficiency_results')
    if deficiency_results:
        lines.append(f"Deficiency check: {json.dumps(deficiency_results)}")

    recommendation_results = state.get('recommendation_results')
    if recommendation_results:
        lines.append(f"Recommendation check: {json.dumps(recommendation_results)}")

    return "\n".join(lines) if lines else "None yet."


# ==================== DECISION PARSER ====================

def _parse_decision(response_text: str) -> Dict[str, Any]:
    """
    Parse the LLM's JSON decision response.

    Expected format:
    {
        "decision": "check_safety" | "check_deficiency" | "get_recommendations" | "synthesize",
        "reasoning": "brief explanation of why"
    }

    Falls back to 'synthesize' if parsing fails — ensures the loop
    always terminates rather than crashing.

    Args:
        response_text: Raw LLM response string

    Returns:
        Dict with 'decision' and 'reasoning' keys
    """
    try:
        # Strip markdown fences if present
        text = response_text.strip()
        if text.startswith("```"):
            text = "\n".join(
                ln for ln in text.split("\n")
                if not ln.startswith("```") and not ln.startswith("json")
            ).strip()
        parsed = json.loads(text)

        decision = parsed.get("decision", "synthesize")
        valid = {"check_safety", "check_deficiency", "get_recommendations", "synthesize"}
        if decision not in valid:
            logger.warning(f"Supervisor returned invalid decision '{decision}', defaulting to synthesize")
            decision = "synthesize"

        return {
            "decision": decision,
            "patient_context": parsed.get("patient_context", ""),
            "reasoning": parsed.get("reasoning", "")
        }

    except Exception as e:
        logger.warning(f"Failed to parse supervisor decision: {e}. Defaulting to synthesize.")
        return {"decision": "synthesize", "patient_context": "", "reasoning": "parse_error"}


# ==================== LANGGRAPH NODE ====================

def supervisor_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    LangGraph node: Plan next step in the workflow.

    Called after entity_normalizer and after each specialist returns.
    Reads question + entities + specialist results so far, and decides
    which specialist to call next or whether to synthesize.

    Reads from state:
        - user_question
        - medications_list, supplements_list, conditions_list, dietary_restrictions_list
        - safety_checked, deficiency_checked, recommendations_checked
        - safety_results, deficiency_results, recommendation_results
        - iterations

    Writes to state:
        - supervisor_decision: routing key for conditional edge
        - iterations: incremented
        - evidence_chain: appended with supervisor reasoning

    Args:
        state: Current ConversationState

    Returns:
        Partial state update dict
    """
    print("\n" + "=" * 60)
    print("🧠 SUPERVISOR: Planning next step...")
    print("=" * 60)

    # ── Iteration guard ──
    iterations = state.get('iterations', 0) + 1
    if iterations > MAX_ITERATIONS:
        logger.warning(f"Supervisor hit max iterations ({MAX_ITERATIONS}), forcing synthesize")
        return {
            'supervisor_decision': 'synthesize',
            'iterations': iterations,
            'evidence_chain': state.get('evidence_chain', []) + [
                f"Supervisor: max iterations reached, forcing synthesis"
            ]
        }

    # ── Build context for LLM ──
    question = state.get('user_question', '')
    medications = state.get('medications_list', [])
    supplements = state.get('supplements_list', [])
    conditions = state.get('conditions_list', [])
    dietary_restrictions = state.get('dietary_restrictions_list', [])

    already_run = []
    if state.get('safety_checked'):
        already_run.append('check_safety')
    if state.get('deficiency_checked'):
        already_run.append('check_deficiency')
    if state.get('recommendations_checked'):
        already_run.append('get_recommendations')

    specialist_context = _build_specialist_context(state)

    prompt = f"""You are a supervisor agent coordinating a supplement safety analysis system.
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
}}"""

    client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=300,
            temperature=0,
            messages=[{"role": "user", "content": prompt}]
        )
        parsed = _parse_decision(response.content[0].text)
    except Exception as e:
        logger.error(f"Supervisor LLM call failed: {e}")
        parsed = {"decision": "synthesize", "patient_context": "", "reasoning": f"llm_error: {e}"}

    decision = parsed["decision"]
    patient_context = parsed["patient_context"]
    reasoning = parsed["reasoning"]

    print(f"   Patient context : {patient_context}")
    print(f"   Decision        : {decision}")
    print(f"   Reasoning       : {reasoning}")
    print(f"   Iterations      : {iterations}")
    print("=" * 60 + "\n")

    evidence = f"Supervisor (iteration {iterations}): {patient_context} → {decision} — {reasoning}"

    return {
        'supervisor_decision': decision,
        'iterations': iterations,
        'evidence_chain': state.get('evidence_chain', []) + [evidence]
    }