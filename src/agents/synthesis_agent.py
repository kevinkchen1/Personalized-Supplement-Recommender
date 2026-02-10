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
                    desc = ix.get('description', '')[:80]  # Truncate first
                    context += f"  - {ix.get('supplement', '')} ↔ {ix.get('target', '')}: {desc}\n"
            context += f"Confidence: {safety.get('confidence', 0):.2f}\n\n"
        
        # Add deficiency findings
        if state.get('deficiency_checked'):
            deficiency = state['deficiency_results']
            context += f"=== DEFICIENCY ANALYSIS ===\n"
            at_risk = deficiency.get('at_risk', [])
            if at_risk:
                context += f"Nutrients at Risk: {', '.join(at_risk)}\n"
                risk_levels = deficiency.get('risk_levels', {})
                for nutrient, level in risk_levels.items():
                    context += f"  - {nutrient}: {level} risk\n"
            else:
                context += "No significant deficiency risks identified\n"
            context += "\n"
        
        # Add recommendations - FIXED: Include actual supplement names!
        if state.get('recommendations_checked'):
            recs = state['recommendation_results']
            recommendations = recs.get('recommendations', [])
            condition = recs.get('condition', 'the condition')
            safe_count = recs.get('safe_count', 0)
            unsafe_count = recs.get('unsafe_count', 0)
            
            context += f"=== RECOMMENDATIONS ===\n"
            context += f"For: {condition}\n"
            context += f"Total found: {len(recommendations)} ({safe_count} safe, {unsafe_count} unsafe)\n\n"
            
            if recommendations:
                # Show safe options
                safe_options = [r for r in recommendations if r.get('safe')]
                if safe_options:
                    context += f"SAFE OPTIONS ({len(safe_options)}):\n"
                    for rec in safe_options[:10]:  # Limit to top 10
                        context += f"{rec['rank']}. {rec['supplement_name']}\n"
                        context += f"   - Safety Rating: {rec.get('safety_rating', 'UNKNOWN')}\n"
                        context += f"   - Treats: {rec.get('symptom_treated', 'N/A')}\n"
                        context += f"   - Verdict: {rec.get('safety_verdict', 'Safe')}\n"
                    context += "\n"
                
                # Show unsafe options with warnings
                unsafe_options = [r for r in recommendations if not r.get('safe')]
                if unsafe_options:
                    context += f"NOT RECOMMENDED ({len(unsafe_options)}):\n"
                    for rec in unsafe_options[:5]:  # Limit to top 5
                        context += f"{rec['rank']}. {rec['supplement_name']}\n"
                        context += f"   - Verdict: {rec.get('safety_verdict', 'Unsafe')}\n"
                        if rec.get('interactions'):
                            context += f"   - Interactions: {len(rec['interactions'])} found\n"
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
- START by showing the actual supplements found (list them by name!)
- Be specific - use the exact supplement names from the analysis above
- For safe options: present them clearly with their safety ratings
- For unsafe options: explain why they're not recommended
- Include relevant safety or deficiency findings if present
- If confidence < 0.7, recommend consulting healthcare provider
- Use accessible language (avoid jargon)
- Be empathetic and supportive
- Format with markdown for readability

CRITICAL: Do NOT write generic disclaimers without showing the actual supplements!
The user asked for specific recommendations - give them the specific names!

Create a personalized answer:
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