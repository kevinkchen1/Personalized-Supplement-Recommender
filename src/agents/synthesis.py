"""
Synthesis Agent - Final Response Generator

Consumes all specialist outputs in the ConversationState and produces a single
patient-facing final answer.

Design goals:
- Grounded: use only the specialist result dicts + evidence_chain (no external biomedical knowledge)
- Robust: if Claude API is unavailable, generate a deterministic fallback answer
- Minimal state writes: sets final_answer and appends one evidence_chain entry
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional

from anthropic import Anthropic

logger = logging.getLogger(__name__)


def _safe_json(obj: Any) -> str:
    try:
        return json.dumps(obj, ensure_ascii=False, indent=2, default=str)
    except Exception:
        return json.dumps(str(obj), ensure_ascii=False)


def _truncate(text: str, max_chars: int) -> str:
    if not text:
        return ""
    text = str(text)
    return text if len(text) <= max_chars else text[: max_chars - 3] + "..."


# =====================================================================
# EVIDENCE NARRATION — turn raw interaction records into plain english
# using the pathway/detail data the Cypher queries already return
# =====================================================================

def _narrate_interaction(ix: Dict[str, Any]) -> str:
    """Turn a single safety interaction record into a plain-english sentence."""
    supp = ix.get("supplement", "This supplement")
    target = ix.get("target", "your medication")
    desc = ix.get("description", "")
    detail = ix.get("detail", "")
    pathway = ix.get("pathway", "")

    if pathway == "HIDDEN_PHARMA_EQUIVALENCE" and " = " in str(detail):
        ingredient, drug = detail.split(" = ", 1)
        return (f"{supp} contains {ingredient}, which is pharmaceutically equivalent "
                f"to {drug} in your {target} — this creates a hidden double-dose risk.")

    if pathway == "DRUG_DRUG_INTERACTION" and " interacts with " in str(detail):
        d1, d2 = detail.split(" interacts with ", 1)
        return (f"{supp} contains an ingredient that acts like {d1}, which has a known "
                f"interaction with {d2} (found in your {target}). {desc}")

    if pathway == "SIMILAR_EFFECT":
        return (f"{supp} has a similar pharmacological effect to drugs in the "
                f"{detail} category, which includes your {target}.")

    return f"{supp} has a documented interaction with your {target}. {desc}".strip()


# =====================================================================
# PRE-PROCESSING — build structured findings summary for the prompt
# Groups safety interactions by supplement↔medication pair so the
# LLM doesn't repeat the same concern from multiple pathways.
# =====================================================================

def _build_findings_summary(state: Dict[str, Any]) -> str:
    """Build a human-readable findings summary from all specialist results."""
    lines = []

    # ── Safety (grouped by pair, with evidence paths) ──
    safety = state.get("safety_results") or {}
    interactions = safety.get("interactions") or []
    if interactions:
        pairs: Dict[str, List[Dict]] = {}  # key -> list of raw interaction dicts
        pair_severity: Dict[str, str] = {}
        for ix in interactions:
            key = f"{ix.get('supplement', '?')} and {ix.get('target', '?')}"
            pairs.setdefault(key, []).append(ix)
            sev = ix.get("severity", "MODERATE")
            if sev == "HIGH" or ix.get("pathway") == "HIDDEN_PHARMA_EQUIVALENCE":
                pair_severity[key] = "HIGH"
            elif key not in pair_severity:
                pair_severity[key] = sev

        lines.append("SAFETY FINDINGS:")
        for pair, ix_list in pairs.items():
            sev = pair_severity.get(pair, "MODERATE")
            narratives = [_narrate_interaction(ix) for ix in ix_list]
            combined = " Additionally, ".join(narratives)

            # Build evidence paths from graph traversal data
            paths = []
            for ix in ix_list:
                pathway = ix.get("pathway", "")
                supp = ix.get("supplement", "?")
                target = ix.get("target", "?")
                detail = ix.get("detail", "")

                if pathway == "DRUG_DRUG_INTERACTION" and " interacts with " in str(detail):
                    d1, d2 = detail.split(" interacts with ", 1)
                    paths.append(f"{supp} → contains → {d1} → interacts with → {d2} → found in → {target}")
                elif pathway == "HIDDEN_PHARMA_EQUIVALENCE" and " = " in str(detail):
                    ingredient, drug = detail.split(" = ", 1)
                    paths.append(f"{supp} → contains → {ingredient} → equivalent to → {drug} → in → {target}")
                elif pathway == "SIMILAR_EFFECT" and detail:
                    paths.append(f"{supp} → similar effect to → {detail} category → includes → {target}")
                elif pathway == "DIRECT_SUPPLEMENT_MEDICATION":
                    paths.append(f"{supp} → directly interacts with → {target}")

            if paths:
                combined += " | EVIDENCE PATHS: " + " ; ".join(paths)

            lines.append(f"  [{sev}] {pair}: {combined}")
    elif safety:
        lines.append(f"SAFETY FINDINGS: {safety.get('summary', 'No interactions found.')}")

    # ── Deficiency ──
    deficiency = state.get("deficiency_results") or {}
    all_at_risk = deficiency.get("all_at_risk_details") or {}
    critical_nutrients = {o.get("nutrient") for o in (deficiency.get("critical_overlaps") or [])}
    if all_at_risk:
        lines.append("\nDEFICIENCY FINDINGS:")
        for nutrient, sources in all_at_risk.items():
            source_strs = []
            for s in sources:
                name, mech = s.get("source_name", ""), s.get("mechanism", "")
                if s.get("source_type") == "diet":
                    source_strs.append(f"your {name} diet")
                elif mech:
                    source_strs.append(f"{name} ({mech})")
                else:
                    source_strs.append(name)
            overlap = " [COMPOUNDED RISK — multiple sources]" if nutrient in critical_nutrients else ""
            lines.append(f"  {nutrient}: at risk due to {', '.join(source_strs)}{overlap}")
    elif deficiency:
        lines.append(f"\nDEFICIENCY FINDINGS: {deficiency.get('summary', 'No deficiencies found.')}")

    # ── Recommendations ──
    recs = state.get("recommendation_results") or {}
    candidates = recs.get("recommendations") or []
    if candidates:
        flagged = {ix.get("supplement", "").lower() for ix in interactions}
        lines.append("\nRECOMMENDATION FINDINGS:")
        for c in candidates:
            name = c.get("supplement_name", "Unknown")
            rating = c.get("safety_rating", "unknown")
            symptom = c.get("symptom_treated", "")
            flag_note = " [WARNING: also has safety concern above]" if name.lower() in flagged else ""
            symptom_note = f" for {symptom}" if symptom else ""
            lines.append(f"  {name}: safety rating '{rating}'{symptom_note}{flag_note}")
    elif recs:
        lines.append(f"\nRECOMMENDATION FINDINGS: {recs.get('summary', 'No candidates found.')}")

    return "\n".join(lines) if lines else "No specialist findings available."

# =====================================================================
# PROMPT BUILDER
# =====================================================================

def _build_prompt(state: Dict[str, Any]) -> str:
    """Build a grounded prompt with pre-processed findings."""
    meds = ", ".join(state.get("medications_list", [])) or "none"
    supps = ", ".join(state.get("supplements_list", [])) or "none"
    conditions = ", ".join(state.get("conditions_list", [])) or "none"
    restrictions = ", ".join(state.get("dietary_restrictions_list", [])) or "none"

    ran = [n for n, k in [("Safety", "safety_checked"), ("Deficiency", "deficiency_checked"),
                           ("Recommendations", "recommendations_checked")] if state.get(k)]
    skipped = [n for n, k in [("Safety", "safety_checked"), ("Deficiency", "deficiency_checked"),
                               ("Recommendations", "recommendations_checked")] if not state.get(k)]

    findings = _build_findings_summary(state)

    return f"""You are a supplement safety advisor. A patient has asked you a question.
Write your response the way a confident, knowledgeable doctor would explain something
in plain language — direct, clear, no hedging.

PATIENT: medications: {meds} | supplements: {supps} | conditions: {conditions} | diet: {restrictions}
QUESTION: "{state.get('user_question', '')}"

FINDINGS:
{findings}

SPECIALISTS RAN: {', '.join(ran) or 'none'} | SKIPPED: {', '.join(skipped) or 'none'}

RULES:
- Use ONLY the findings above. Do NOT add biomedical knowledge or invent interactions.
- Use the patient's specific names — "your Warfarin", not "your blood thinner".
- Explain WHY using the mechanism details, in plain language a non-medical person would understand.
  Bad: "decrease the therapeutic efficacy of Warfarin"
  Good: "make your Warfarin less effective at preventing blood clots"
- If multiple pathways affect the same supplement-medication pair, combine them into ONE explanation.
  Do NOT say "additionally" or "there is a second pathway". Just explain the full picture together.
- Be direct. Do not hedge with "potentially", "could possibly", "may compromise". State what the findings say.

FORMATTING:
- Start with a direct 1-2 sentence answer to their question in bold. Get to the point immediately.
- Then explain the details in short paragraphs (2-3 sentences each).
- Use **bold** for supplement and medication names on first mention, and for key takeaways.
- Use a horizontal rule (---) to visually separate the main findings from secondary info like
  skipped specialists or the closing note.
- If evidence paths are provided (arrow chains like A → B → C), display them in a callout block like:
  > **How we found this:** Supplement → contains → Ingredient → interacts with → Drug
  This shows the patient the knowledge graph relationships we traced. Keep the arrows, keep it on one line.
- If a specialist was skipped, mention what wasn't assessed after the --- in one natural sentence.
- Close with one sentence recommending they talk to their provider. Keep it natural.
- No markdown headers (#), no numbered lists, no emojis. Bold and horizontal rules only.
- Total response: 4-6 short paragraphs max including the callout.
"""


# =====================================================================
# DETERMINISTIC FALLBACK (used when no API key or LLM fails)
# =====================================================================

def _deterministic_fallback_answer(state: Dict[str, Any]) -> str:
    question = state.get("user_question", "")
    meds = state.get("medications_list", []) or []
    supps = state.get("supplements_list", []) or []
    conditions = state.get("conditions_list", []) or []
    restrictions = state.get("dietary_restrictions_list", []) or []

    safety = state.get("safety_results") or {}
    deficiency = state.get("deficiency_results") or {}
    recs = state.get("recommendation_results") or {}

    lines: List[str] = []
    lines.append("## Summary")
    lines.append(f"- **Question**: {_truncate(question, 400)}" if question else "- **Question**: (not provided)")
    lines.append(f"- **Medications**: {', '.join(meds) if meds else 'none'}")
    lines.append(f"- **Current supplements**: {', '.join(supps) if supps else 'none'}")
    lines.append(f"- **Conditions/goals**: {', '.join(conditions) if conditions else 'none'}")
    lines.append(f"- **Dietary restrictions**: {', '.join(restrictions) if restrictions else 'none'}")

    lines.append("")
    lines.append("## Safety check")
    if safety:
        lines.append(f"- **Result**: {safety.get('summary', '(no summary)')}")
        interactions = safety.get("interactions") or []
        if interactions:
            lines.append("- **Interactions found**:")
            for ix in interactions[:10]:
                pathway = ix.get("pathway", "UNKNOWN")
                sev = ix.get("severity", "UNKNOWN")
                supp = ix.get("supplement", "")
                target = ix.get("target", "")
                desc = ix.get("description", "")
                detail = ix.get("detail")
                detail_str = f" ({detail})" if detail else ""
                lines.append(f"  - [{sev}] {supp} ↔ {target} — {pathway}: {_truncate(desc, 220)}{detail_str}")
            if len(interactions) > 10:
                lines.append(f"  - …and {len(interactions) - 10} more")
        else:
            lines.append("- **Interactions found**: none reported by the tool")
    else:
        lines.append("- Safety specialist did not run in this trace.")

    lines.append("")
    lines.append("## Nutrient deficiency risk check")
    if deficiency:
        lines.append(f"- **Result**: {deficiency.get('summary', '(no summary)')}")
        overlaps = deficiency.get("critical_overlaps") or []
        at_risk = deficiency.get("all_at_risk") or []
        if overlaps:
            lines.append("- **Critical overlaps (2+ sources affecting same nutrient)**:")
            for ov in overlaps[:10]:
                nutrient = ov.get("nutrient", "Unknown nutrient")
                warning = ov.get("warning", "")
                lines.append(f"  - {nutrient}: {_truncate(warning, 240)}")
            if len(overlaps) > 10:
                lines.append(f"  - …and {len(overlaps) - 10} more")
        elif at_risk:
            lines.append(f"- **Nutrients at risk**: {', '.join(at_risk[:25])}")
            if len(at_risk) > 25:
                lines.append(f"  - …and {len(at_risk) - 25} more")
        else:
            lines.append("- **Nutrients at risk**: none reported by the tool")
    else:
        lines.append("- Deficiency specialist did not run in this trace.")

    lines.append("")
    lines.append("## Candidate supplement recommendations")
    if recs:
        lines.append(f"- **Result**: {recs.get('summary', '(no summary)')}")
        candidates = recs.get("recommendations") or []
        if candidates:
            lines.append("- **Top candidates (from KG `TREATS` edges)**:")
            for c in candidates[:10]:
                name = c.get("supplement_name", "Unknown")
                rating = c.get("safety_rating", "unknown")
                treated = c.get("symptom_treated", "")
                treated_str = f" (treats: {treated})" if treated else ""
                lines.append(f"  - {name} — safety_rating: {rating}{treated_str}")
            if len(candidates) > 10:
                lines.append(f"  - …and {len(candidates) - 10} more")
        else:
            lines.append("- **Candidates**: none reported by the tool")
    else:
        lines.append("- Recommendation specialist did not run in this trace.")

    lines.append("")
    lines.append("## Notes")
    lines.append(
        "- This answer is synthesized from the project's specialist tool outputs. "
        "If something isn't present above, it wasn't found by the tools (or the tool didn't run)."
    )

    return "\n".join(lines).strip() + "\n"


# =====================================================================
# LANGGRAPH NODE
# =====================================================================

def synthesis_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    LangGraph node: Generate the final answer from all specialist outputs.

    Reads from state:
      - user_question, patient_profile, clean lists
      - safety_results, deficiency_results, recommendation_results
      - evidence_chain

    Writes to state:
      - final_answer
      - evidence_chain (append one synthesis step)
      - error_message (only if synthesis fails completely)
    """
    print("\n" + "=" * 60)
    print("🧾 SYNTHESIS: Generating final answer...")
    print("=" * 60)

    prompt = _build_prompt(state)
    evidence_chain = state.get("evidence_chain", []) or []

    # If the API key isn't present, we still want the workflow to succeed.
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        answer = _deterministic_fallback_answer(state)
        print("   ⚠️  No ANTHROPIC_API_KEY found — using deterministic fallback synthesis")
        return {
            "final_answer": answer,
            "evidence_chain": evidence_chain + ["Synthesis: generated final answer (fallback, no API key)"],
        }

    client = Anthropic(api_key=api_key)

    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1500,
            temperature=0,
            messages=[{"role": "user", "content": prompt}],
        )
        answer_text = (response.content[0].text or "").strip()
        if not answer_text:
            raise ValueError("Empty synthesis response from LLM")

        print("   ✅ Final answer generated")
        print("=" * 60 + "\n")
        return {
            "final_answer": answer_text,
            "evidence_chain": evidence_chain + ["Synthesis: generated final answer (LLM)"],
            "error_message": None,
        }
    except Exception as e:
        logger.error(f"Synthesis LLM call failed: {e}")
        answer = _deterministic_fallback_answer(state)
        print("   ⚠️  Synthesis LLM failed — using deterministic fallback synthesis")
        print("=" * 60 + "\n")
        return {
            "final_answer": answer,
            "evidence_chain": evidence_chain + [f"Synthesis: LLM failed, used fallback ({type(e).__name__})"],
            "error_message": None,
        }
