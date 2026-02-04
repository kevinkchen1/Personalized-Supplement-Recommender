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
        question = state['user_question']
        profile = state.get('patient_profile', {})
        safety_results = state.get('safety_results', {})
        deficiency_results = state.get('deficiency_results', {})
        recommendation_results = state.get('recommendation_results', {})
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
        
        Args:
            state: Current state
            
        Returns:
            Context string
        """
        context = f"Question: {state['user_question']}\n\n"
        
        # Add profile info
        profile = state.get('patient_profile', {})
        if profile.get('medications'):
            meds = [m.get('matched_drug', m.get('user_input')) 
                   for m in profile['medications']]
            context += f"Patient Medications: {', '.join(meds)}\n"
        
        if profile.get('conditions'):
            context += f"Conditions: {', '.join(profile['conditions'])}\n"
        
        if profile.get('dietary_restrictions'):
            context += f"Diet: {', '.join(profile['dietary_restrictions'])}\n"
        
        context += "\n"
        
        # Add safety findings
        if state.get('safety_checked'):
            safety = state['safety_results']
            context += f"Safety Check: {safety.get('verdict', 'Unknown')}\n"
            if safety.get('interactions'):
                context += f"Interactions Found: {len(safety['interactions'])}\n"
            context += f"Confidence: {safety.get('confidence', 0):.2f}\n\n"
        
        # Add deficiency findings
        if state.get('deficiency_checked'):
            deficiency = state['deficiency_results']
            at_risk = deficiency.get('at_risk', [])
            if at_risk:
                context += f"Deficiency Risks: {', '.join(at_risk)}\n"
                risk_levels = deficiency.get('risk_levels', {})
                for nutrient, level in risk_levels.items():
                    context += f"  - {nutrient}: {level} risk\n"
            else:
                context += "No significant deficiency risks identified\n"
            context += "\n"
        
        # Add recommendations
        if state.get('recommendations_checked'):
            recs = state['recommendation_results']
            recommendations = recs.get('recommendations', [])
            if recommendations:
                context += f"Recommendations: {len(recommendations)} options found\n"
        
        return context
    
    
    def _generate_answer(self, context: str, confidence: float) -> str:
        """
        Generate personalized answer using LLM
        
        Args:
            context: Compiled context
            confidence: Confidence level
            
        Returns:
            Final answer string
        """
        prompt = f"""
You are a personalized supplement safety advisor. Create a clear, helpful answer based on this analysis:

{context}

Overall Confidence: {confidence:.2f}

Guidelines:
- Be clear and direct
- Include relevant findings
- If confidence < 0.7, recommend consulting healthcare provider
- Explain WHY (include reasoning/evidence)
- Use accessible language (avoid jargon)
- Be empathetic and supportive

Create a personalized answer:
"""
        
        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
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