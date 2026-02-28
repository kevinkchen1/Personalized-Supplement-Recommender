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
        "- This answer is synthesized from the project’s specialist tool outputs. "
        "If something isn’t present above, it wasn’t found by the tools (or the tool didn’t run)."
    )

    return "\n".join(lines).strip() + "\n"


def _build_prompt(state: Dict[str, Any]) -> str:
    """Build a grounded prompt with all tool outputs as JSON."""
    payload = {
        "user_question": state.get("user_question", ""),
        "patient_profile": state.get("patient_profile", {}),
        "clean_lists": {
            "medications_list": state.get("medications_list", []),
            "supplements_list": state.get("supplements_list", []),
            "candidate_supplements_list": state.get("candidate_supplements_list", []),
            "conditions_list": state.get("conditions_list", []),
            "dietary_restrictions_list": state.get("dietary_restrictions_list", []),
        },
        "specialist_results": {
            "safety_results": state.get("safety_results"),
            "deficiency_results": state.get("deficiency_results"),
            "recommendation_results": state.get("recommendation_results"),
        },
        "evidence_chain": state.get("evidence_chain", []),
    }

    return f"""You are a synthesis agent for a supplement safety system.
Your job is to write the final user-facing response using ONLY the JSON payload below.

Hard rules:
- Do NOT use general biomedical knowledge.
- Do NOT invent interactions, nutrients, or recommendations not present in the payload.
- If a specialist tool did not run or has empty results, say that explicitly.
- If you make a suggestion, tie it directly to a payload field (quote or paraphrase the tool summary).

Output format:
- Write in clear markdown with headings.
- Include sections:
  1) Summary of the user question and patient context
  2) Safety (interactions + what the user should do next)
  3) Deficiency risks (if any)
  4) Candidate supplements (if any) and whether safety has been checked for them (based on safety_results)
  5) What’s missing / limitations (short)

JSON payload:
{_safe_json(payload)}
"""


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
            max_tokens=900,
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

