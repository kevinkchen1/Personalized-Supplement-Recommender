"""
Synthesis Agent - Answer Writer

Takes all findings and creates a personalized, evidence-based answer:
- Synthesizes results from all specialist agents
- Includes evidence trail
- Adjusts explanation based on confidence level
- Writes in clear, accessible language

Role: Final answer synthesis
"""

from anthropic import Anthropic
from typing import Dict, Any
import os


class SynthesisAgent:
    """
    Specialist agent for synthesizing final answer
    """
    
    def __init__(self):
        self.client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    
    
    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Synthesize final answer from all findings
        
        Args:
            state: Current conversation state
            
        Returns:
            Updated state with final answer
        """
        print("\n" + "="*60)
        print("✍️  SYNTHESIS AGENT: Creating personalized answer...")
        print("="*60)
        
        # Gather all findings
        confidence = state.get('confidence_level', 0.0)
        
        # Build context for LLM
        context = self._build_synthesis_context(state)
        
        # Generate personalized answer
        answer = self._generate_answer(context, confidence)
        
        state['final_answer'] = answer
        
        print("   ✓ Answer synthesized")
        print("="*60 + "\n")
        
        return state
    
    
    def _build_synthesis_context(self, state: Dict[str, Any]) -> str:
        """
        Build comprehensive context for synthesis
        
        FIXED: Actually includes the supplement names and details!
        
        Args:
            state: Current state
            
        Returns:
            Context string
        """
        context = f"Question: {state['user_question']}\n\n"
        
        # ✨ NEW: Add shared state summary (cross-agent knowledge)
        unsafe_supps = state.get('unsafe_supplements_list', [])
        safe_supps = state.get('safe_supplements_list', [])
        deficiencies = state.get('deficient_nutrients_list', [])
        
        if unsafe_supps or safe_supps or deficiencies:
            context += "=== CROSS-AGENT INSIGHTS ===\n"
            context += "Knowledge gathered from all agents:\n\n"
            
            if deficiencies:
                context += f"🔍 Nutrient Deficiencies Identified: {', '.join(deficiencies)}\n"
                context += f"   (User is at risk for these {len(deficiencies)} nutrients)\n\n"
            
            if safe_supps:
                context += f"✅ Verified Safe Supplements: {', '.join(safe_supps[:10])}\n"
                if len(safe_supps) > 10:
                    context += f"   (+ {len(safe_supps) - 10} more)\n"
                context += f"   (These {len(safe_supps)} supplements have been checked and found safe)\n\n"
            
            if unsafe_supps:
                context += f"⚠️  Supplements with Interactions: {', '.join(unsafe_supps[:10])}\n"
                if len(unsafe_supps) > 10:
                    context += f"   (+ {len(unsafe_supps) - 10} more)\n"
                context += f"   (These {len(unsafe_supps)} supplements have known interactions)\n\n"
            
            context += "="*60 + "\n\n"
        
        # Add profile info
        profile = state.get('patient_profile', {})
        if profile.get('medications'):
            meds = [
                m.get('matched_drug', m.get('user_input', 'Unknown')) if isinstance(m, dict) else str(m)
                for m in profile['medications']
            ]
            context += f"Patient Medications: {', '.join(meds)}\n"
        
        if profile.get('supplements'):
            supps = [
                s.get('supplement_name', s.get('user_input', 'Unknown')) if isinstance(s, dict) else str(s)
                for s in profile['supplements']
            ]
            context += f"Patient Supplements: {', '.join(supps)}\n"
        
        if profile.get('conditions'):
            context += f"Conditions: {', '.join(profile['conditions'])}\n"
        
        if profile.get('dietary_restrictions') or profile.get('diet'):
            diet = profile.get('dietary_restrictions', profile.get('diet', []))
            context += f"Diet: {', '.join(diet)}\n"
        
        context += "\n"
        
        # Add safety findings
        if state.get('safety_checked'):
            safety = state['safety_results']
            context += f"=== SAFETY CHECK ===\n"
            context += f"Verdict: {safety.get('verdict', 'Unknown')}\n"
            if safety.get('interactions'):
                context += f"Interactions Found: {len(safety['interactions'])}\n"
                for ix in safety['interactions'][:5]:  # Show first 5
                    desc = ix.get('description') or 'No description available'
                    context += f"  - {ix.get('supplement', '')} ↔ {ix.get('target', '')}: {desc}\n"
            context += f"Confidence: {safety.get('confidence', 0):.2f}\n\n"
        
        # Add deficiency findings
        if state.get('deficiency_checked'):
            deficiency = state['deficiency_results']
            context += f"=== DEFICIENCY ANALYSIS ===\n"
            context += f"Verdict: {deficiency.get('verdict', 'Unknown')}\n"
            
            # Get diet-based deficiencies
            diet_def = deficiency.get('diet_based', [])
            # Get supplement-based deficiencies
            supplement_def = deficiency.get('supplement_based', [])
            # ✨ NEW: Get medication-based deficiencies
            medication_def = deficiency.get('medication_based', [])
            # Get critical overlaps
            critical_overlaps = deficiency.get('critical_overlaps', [])
            
            if diet_def or supplement_def or medication_def:
                total_count = len(diet_def) + len(supplement_def) + len(medication_def)
                context += f"Nutrient Deficiencies Found: {total_count}\n\n"
                
                # Show diet-based deficiencies
                if diet_def:
                    context += f"FROM DIET ({len(diet_def)}):\n"
                    for d in diet_def:
                        context += f"  - {d['nutrient']} (from {d['source_name']} diet)\n"
                        context += f"    Risk Level: {d['risk_level']}\n"
                        if d.get('evidence'):
                            evidence_short = d['evidence'][:100] + '...' if len(d['evidence']) > 100 else d['evidence']
                            context += f"    Details: {evidence_short}\n"
                    context += "\n"
                
                # Show supplement-based deficiencies
                if supplement_def:
                    context += f"FROM SUPPLEMENTS ({len(supplement_def)}):\n"
                    for d in supplement_def:
                        context += f"  - {d['nutrient']} (from {d['source_name']})\n"
                        context += f"    Risk Level: {d['risk_level']}\n"
                        context += f"    Mechanism: {d['mechanism']}\n"
                        if d.get('evidence'):
                            evidence_short = d['evidence'][:100] + '...' if len(d['evidence']) > 100 else d['evidence']
                            context += f"    Details: {evidence_short}\n"
                    context += "\n"
                
                # Show medication-based deficiencies
                if medication_def:
                    context += f"FROM MEDICATIONS ({len(medication_def)}):\n"
                    for d in medication_def:
                        context += f"  - {d['nutrient']} (from {d['source_name']})\n"
                        context += f"    Risk Level: {d['risk_level']}\n"
                        context += f"    Mechanism: {d['mechanism']}\n"
                        if d.get('evidence'):
                            evidence_short = d['evidence'][:100] + '...' if len(d['evidence']) > 100 else d['evidence']
                            context += f"    Details: {evidence_short}\n"
                        context += f"    Confidence: {d.get('confidence', 0):.2f}\n"
                    context += "\n"
                
                # Show critical overlaps
                if critical_overlaps:
                    context += f"⚠️ CRITICAL OVERLAPS ({len(critical_overlaps)}):\n"
                    for overlap in critical_overlaps:
                        context += f"  - {overlap['nutrient']} affected by {overlap['risk_multiplier']} sources!\n"
                        context += f"    Sources: {', '.join(overlap['source_names'])}\n"
                        context += f"    Overlap Type: {overlap.get('overlap_type', 'UNKNOWN')}\n"
                        context += f"    Combined Risk: {overlap['combined_risk']}\n"
                    context += "\n"
            else:
                context += "No significant deficiency risks identified\n\n"
            
            context += f"Confidence: {deficiency.get('confidence', 0):.2f}\n\n"
        
        # Add recommendations - UPDATED: Filter by safety results
        if state.get('recommendations_checked'):
            recs = state['recommendation_results']
            candidates = recs.get('candidates', [])  # All candidates (not pre-filtered)
            condition = recs.get('condition', 'the condition')
            
            # ✨ NEW: Get safety results to determine which are safe
            safety_results = state.get('safety_results', {})
            interactions_by_supplement = {}
            
            # Build lookup: supplement_name → list of interactions
            for interaction in safety_results.get('interactions', []):
                supp_name = interaction.get('supplement')
                if supp_name not in interactions_by_supplement:
                    interactions_by_supplement[supp_name] = []
                interactions_by_supplement[supp_name].append(interaction)
            
            context += f"=== RECOMMENDATIONS ===\n"
            context += f"For: {condition}\n"
            context += f"Total candidates found: {len(candidates)}\n"
            
            if candidates:
                # ✨ Separate safe and unsafe based on safety agent results
                safe_options = []
                unsafe_options = []
                
                for rec in candidates:
                    supp_name = rec['supplement_name']
                    if supp_name in interactions_by_supplement:
                        # Has interactions → unsafe
                        rec['interactions'] = interactions_by_supplement[supp_name]
                        rec['interaction_count'] = len(rec['interactions'])
                        unsafe_options.append(rec)
                    else:
                        # No interactions found by safety agent → safe
                        safe_options.append(rec)
                
                context += f"Safe: {len(safe_options)}, Unsafe: {len(unsafe_options)}\n\n"
                
                # Show safe options
                if safe_options:
                    context += f"SAFE OPTIONS ({len(safe_options)}):\n"
                    for rec in safe_options[:10]:  # Limit to top 10
                        context += f"{rec['rank']}. {rec['supplement_name']}\n"
                        context += f"   - Safety Rating: {rec.get('safety_rating', 'UNKNOWN')}\n"
                        context += f"   - Treats: {rec.get('symptom_treated', condition)}\n"
                        context += f"   - Verdict: SAFE (no interactions found by safety agent)\n"
                    context += "\n"
                
                # Show unsafe options with warnings
                if unsafe_options:
                    context += f"NOT RECOMMENDED ({len(unsafe_options)}):\n"
                    for rec in unsafe_options[:5]:  # Limit to top 5
                        context += f"{rec['rank']}. {rec['supplement_name']}\n"
                        context += f"   - Interactions: {rec['interaction_count']} found\n"
                        # Show details of first 2 interactions
                        for ix in rec['interactions'][:2]:
                            pathway = ix.get('pathway', 'UNKNOWN')
                            desc = ix.get('description') or 'Unknown interaction'
                            context += f"     • [{pathway}] {desc}...\n"
                    context += "\n"
            else:
                context += "No supplements found in database for this condition.\n\n"
        
        return context
    
    
    def _generate_answer(self, context: str, confidence: float) -> str:
        """
        Generate personalized answer using LLM
        
        Args:
            context: Compiled context (now includes supplement names!)
            confidence: Confidence level
            
        Returns:
            Final answer string
        """
        prompt = f"""
You are a personalized supplement safety advisor. Create a clear, helpful answer based on this analysis:

{context}

Overall Confidence: {confidence:.2f}

Guidelines:
- START by addressing the user's specific question directly
- Use the CROSS-AGENT INSIGHTS at the top to make intelligent connections:
  * If user is deficient in a nutrient AND a supplement providing it is unsafe, suggest safe alternatives
  * If user asks about a supplement that's in the "verified safe" list, confidently recommend it
  * If user asks about a supplement in the "unsafe" list, clearly warn against it with specifics
- Show actual supplement names (be specific!)
- For safe options: present them clearly with their safety ratings
- For unsafe options: explain why they're not recommended with interaction details
- Make connections across findings (e.g., "You're deficient in Omega-3. Fish oil would help, but it's unsafe with Warfarin. Try Flaxseed oil instead.")
- Include relevant safety or deficiency findings
- If confidence < 0.7, recommend consulting healthcare provider
- Use accessible language (avoid jargon)
- Be empathetic and supportive
- Format with markdown for readability

🚨 CRITICAL SAFETY CONSTRAINTS - TWO-TIER RECOMMENDATION SYSTEM:

**TIER 1: System-Verified Recommendations (PRIORITIZE THESE)**
- When suggesting supplements, FIRST check if they appear in the "✅ Verified Safe Supplements" list
- If found, clearly label them: "✅ [Supplement Name] (verified safe with your medications)"
- These are high-confidence recommendations that have been checked against the user's medications

**TIER 2: General Knowledge Suggestions (USE WHEN NO TIER 1 OPTIONS)**
- If no supplement in the verified safe list addresses the need, you MAY suggest based on general knowledge
- BUT you MUST clearly distinguish these with special formatting:
  "⚠️ Based on general knowledge (NOT yet verified with your specific medications): [Supplement Name]"
- ALWAYS add: "Please consult your healthcare provider before taking this, as it hasn't been checked against your medications in our system."

**Examples:**

✅ TIER 1 (BEST):
"You're deficient in Omega-3. While Fish oil is unsafe with Warfarin, 
✅ **Flaxseed oil** (verified safe with your medications) is an excellent alternative 
that also provides Omega-3."

✅ TIER 2 (ACCEPTABLE WHEN NO TIER 1):
"You're deficient in Vitamin D. Unfortunately, no Vitamin D supplements have been 
verified as safe with your medications in our system.

⚠️ **Based on general knowledge** (NOT yet verified with your specific medications):
- Vitamin D3 (cholecalciferol) is commonly recommended for Vitamin D deficiency
- Typical dosage is 1000-2000 IU daily

**Important:** Please consult your healthcare provider before taking Vitamin D 
supplements, as we haven't verified interactions with your specific medications."

✅ MIXED (TIER 1 + TIER 2):
"For heart health, I recommend:

**✅ Verified Safe:**
- Coenzyme Q10 (verified safe with your medications)
- Magnesium (verified safe with your medications)

You're also deficient in Vitamin B-12. Unfortunately, no B-12 supplements have 
been verified in our system.

⚠️ **Based on general knowledge** (NOT yet verified):
- Vitamin B-12 (methylcobalamin or cyanocobalamin) 
- Consult your provider before starting."

**FORMAT REQUIREMENTS:**
- Use ✅ emoji or bold "Verified Safe" for Tier 1 recommendations
- Use ⚠️ emoji or bold "Based on general knowledge" for Tier 2 suggestions
- Always include disclaimer for Tier 2: "NOT yet verified with your specific medications"
- Always recommend consulting provider for Tier 2 suggestions

CRITICAL: Use the cross-agent insights to provide ACTIONABLE advice that connects:
- What they're deficient in
- What's verified safe (Tier 1)
- What's based on general knowledge when no Tier 1 exists (Tier 2)
- Smart alternatives when primary options are unsafe

Create a personalized, intelligent answer with clear two-tier recommendations:
"""
        
        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1500,
            temperature=0.7,
            messages=[{"role": "user", "content": prompt}]
        )
        
        answer = response.content[0].text
        
        # Add confidence disclaimer if needed
        if confidence < 0.7:
            answer += "\n\n⚠️ **Note**: This analysis has moderate confidence. " \
                     "Please consult with your healthcare provider before making changes."
        
        return answer


# Standalone function for LangGraph
def synthesis_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    """Wrapper for LangGraph integration"""
    agent = SynthesisAgent()
    return agent.run(state)