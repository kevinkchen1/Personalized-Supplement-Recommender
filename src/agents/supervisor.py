"""
Supervisor Agent - Main Coordinator

The "brain" of the system. Makes high-level decisions about:
- What needs to be investigated
- Which specialist agents to call
- When results are good enough
- When to loop back for more information

Role: Orchestrates the entire workflow dynamically
"""

import os
from anthropic import Anthropic
from typing import Dict, Any
from dotenv import load_dotenv

load_dotenv()


class SupervisorAgent:
    """
    Main supervisor agent that coordinates all specialist agents.
    """
    
    def __init__(self):
        self.client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.model = "claude-sonnet-4-20250514"
    
    def __call__(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main entry point for supervisor agent.
        
        Responsibilities:
        1. Extract entities from question (if not done)
        2. Analyze what needs to be checked
        3. Evaluate current results
        4. Decide next action
        
        Args:
            state: Current conversation state
            
        Returns:
            Updated state with supervisor's decision
        """
        print("🧠 SUPERVISOR: Analyzing question and current state...")
        
        # Step 1: Extract entities if not done yet
        if not state.get('entities_extracted', False):
            print("🧠 SUPERVISOR: Extracting entities from question...")
            state = self._extract_and_normalize_entities(state)
        
        # Step 2: Analyze what needs to be done
        print("🧠 SUPERVISOR: Determining what to check...")
        needs = self._analyze_requirements(state)
        
        # Step 3: Evaluate current progress
        print("🧠 SUPERVISOR: Evaluating results so far...")
        evaluation = self._evaluate_progress(state, needs)
        
        # Step 4: Decide next action
        print("🧠 SUPERVISOR: Making decision...")
        decision = self._make_decision(state, needs, evaluation)
        
        # Update state with decision
        state['supervisor_decision'] = decision['action']
        state['supervisor_reasoning'] = decision['reasoning']
        state['iterations'] = state.get('iterations', 0) + 1
        
        print(f"🧠 SUPERVISOR: Decision → {decision['action']}")
        print(f"   Reasoning: {decision['reasoning']}")
        
        return state
    
    def _extract_and_normalize_entities(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract entities from question and normalize them.
        ALSO normalizes entities from patient profile!
        
        Calls:
        - entity_extractor tool (Phase 1)
        - entity_normalizer tool (Phase 2)
        
        UPDATED: Now creates clean, deduplicated lists for agents to consume
        """
        from tools.entity_extractor import extract_entities_from_text
        from tools.entity_normalizer import (
            normalize_medication_to_database,
            normalize_supplement_to_database
        )
        
        question = state['user_question']
        
        # Extract entities from question
        print("   📋 Extracting entities from question...")
        extracted = extract_entities_from_text(question)
        # Note: We don't store extracted_entities in state anymore to avoid duplication
        
        # Normalize medications from question
        print("   🔄 Normalizing medications from question...")
        normalized_meds = []
        for med in extracted['medications']:
            result = normalize_medication_to_database(med, state['graph_interface'])
            normalized_meds.append(result)
        
        # Normalize supplements from question
        print("   🔄 Normalizing supplements from question...")
        normalized_supps = []
        for supp in extracted['supplements']:
            result = normalize_supplement_to_database(supp, state['graph_interface'])
            normalized_supps.append(result)
        
        # ✨ Normalize patient profile supplements and medications
        profile = state.get('patient_profile', {})
        
        # Normalize profile medications
        profile_meds = profile.get('medications', [])
        if isinstance(profile_meds, str):
            profile_meds = [m.strip() for m in profile_meds.split(',') if m.strip()]
        
        if profile_meds:
            print("   🔄 Normalizing medications from profile...")
            for med in profile_meds:
                # Skip if already normalized from question
                if not any(m.get('user_input') == med for m in normalized_meds):
                    result = normalize_medication_to_database(med, state['graph_interface'])
                    normalized_meds.append(result)
        
        # Normalize profile supplements
        profile_supps = profile.get('supplements', [])
        if isinstance(profile_supps, str):
            profile_supps = [s.strip() for s in profile_supps.split(',') if s.strip()]
        
        if profile_supps:
            print("   🔄 Normalizing supplements from profile...")
            for supp in profile_supps:
                # Skip if already normalized from question
                if not any(s.get('user_input') == supp for s in normalized_supps):
                    result = normalize_supplement_to_database(supp, state['graph_interface'])
                    normalized_supps.append(result)
        
        # Dietary restrictions (no normalization needed - simple strings)
        print("   ✅ Processing dietary restrictions...")
        dietary_restrictions = extracted.get('dietary_restrictions', [])
        
        # ✨ Also get dietary restrictions from profile
        profile_restrictions = profile.get('dietary_restrictions', [])
        
        # Handle different formats (string, list, or list of dicts)
        if isinstance(profile_restrictions, str):
            # Split comma-separated string
            profile_restrictions = [r.strip() for r in profile_restrictions.split(',') if r.strip()]
        
        # Merge profile restrictions (avoid duplicates)
        for restriction in profile_restrictions:
            if isinstance(restriction, dict):
                name = restriction.get('restriction_name') or restriction.get('user_input', '')
            elif isinstance(restriction, str):
                name = restriction
            else:
                name = ''
            
            # Add if not already in list (case-insensitive check)
            if name and name not in dietary_restrictions:
                # Check case-insensitive
                if not any(name.lower() == r.lower() for r in dietary_restrictions):
                    dietary_restrictions.append(name)
        
        # Store normalized results (for debugging/transparency)
        state['normalized_medications'] = normalized_meds
        state['normalized_supplements'] = normalized_supps
        state['normalized_dietary_restrictions'] = dietary_restrictions
        
        # ✨ NEW: Create clean, deduplicated lists for agents to consume
        print("   🧹 Creating deduplicated lists for agents...")
        state['medications_list'] = self._extract_final_names(
            normalized_meds, 
            key='matched_drug'
        )
        state['supplements_list'] = self._extract_final_names(
            normalized_supps, 
            key='matched_supplement'
        )
        state['dietary_restrictions_list'] = dietary_restrictions
        
        print(f"   ✅ Final lists: {len(state['medications_list'])} medications, "
              f"{len(state['supplements_list'])} supplements, "
              f"{len(state['dietary_restrictions_list'])} dietary restrictions")
        
        state['entities_extracted'] = True
        
        return state
    
    def _extract_final_names(self, normalized_list: list, key: str) -> list:
        """
        Extract unique names from normalized results with smart deduplication.
        
        Handles:
        - Case-insensitive matching
        - Base name matching (e.g., "Folate" matches "Folate (folic acid)")
        - Prefers normalized/matched names over user input
        - Handles NOT_FOUND entities gracefully
        
        Args:
            normalized_list: List of normalized entity dicts
            key: The key to extract ('matched_drug' or 'matched_supplement')
            
        Returns:
            List of unique entity names (strings)
        """
        name_map = {}  # lowercase -> preferred_name
        
        for item in normalized_list:
            # Get matched name (or fall back to user_input if not found)
            name = item.get(key) or item.get('user_input')
            
            if not name:
                continue
            
            # Skip NOT_FOUND entities
            if item.get('confidence') == 'NOT_FOUND':
                continue
            
            name_lower = name.lower()
            
            # Extract base name (before parentheses) for matching
            # Example: "Folate (folic acid)" -> base: "folate"
            base_name = name.split('(')[0].strip().lower() if '(' in name else name_lower
            
            # Add both full name and base name as keys
            # This allows "Folate" to match "Folate (folic acid)"
            if name_lower not in name_map:
                name_map[name_lower] = name
            
            if base_name != name_lower and base_name not in name_map:
                name_map[base_name] = name
        
        # Return unique values (in case multiple keys point to same name)
        return list(set(name_map.values()))
    
    def _analyze_requirements(self, state: Dict[str, Any]) -> Dict[str, bool]:
        """
        Analyze the question to determine what needs to be checked.
        
        Uses LLM to understand user intent.
        
        Returns:
            {
                'needs_safety_check': True/False,
                'needs_deficiency_check': True/False,
                'needs_recommendations': True/False
            }
        """
        question = state['user_question'].lower()
        
        # Build medication/supplement name lists (handle both str and dict formats)
        raw_meds = state.get('patient_profile', {}).get('medications', [])
        med_names = [
            m.get('drug_name', 'Unknown') if isinstance(m, dict) else str(m)
            for m in raw_meds
        ]
        
        raw_supps = state.get('patient_profile', {}).get('supplements', [])
        supp_names = [
            s.get('supplement_name', 'Unknown') if isinstance(s, dict) else str(s)
            for s in raw_supps
        ]
        
        # Use LLM to analyze intent
        prompt = f"""
Analyze this user question and determine what they need:

Question: "{state['user_question']}"

User Profile:
- Medications: {med_names}
- Supplements: {supp_names}
- Dietary restrictions: {state.get('patient_profile', {}).get('dietary_restrictions', state.get('patient_profile', {}).get('diet', []))}

Determine what needs to be checked:
1. Safety check? (drug-supplement interactions)
2. Deficiency analysis? (nutrient gaps from diet/medications)
3. Supplement recommendations? (suggestions for conditions/symptoms)

Return ONLY JSON:
{{
    "needs_safety_check": true/false,
    "needs_deficiency_check": true/false,
    "needs_recommendations": true/false,
    "reasoning": "brief explanation"
}}
"""
        
        response = self.client.messages.create(
            model=self.model,
            max_tokens=500,
            temperature=0,
            messages=[{"role": "user", "content": prompt}]
        )
        
        import json
        import re
        
        raw_text = response.content[0].text.strip()
        
        # Strip markdown code fences if present (```json ... ``` or ``` ... ```)
        raw_text = re.sub(r'^```(?:json)?\s*', '', raw_text)
        raw_text = re.sub(r'\s*```$', '', raw_text)
        raw_text = raw_text.strip()
        
        try:
            needs = json.loads(raw_text)
        except json.JSONDecodeError:
            # Fallback: try to extract JSON object from the text
            match = re.search(r'\{[^{}]*\}', raw_text, re.DOTALL)
            if match:
                try:
                    needs = json.loads(match.group())
                except json.JSONDecodeError:
                    print(f"   ⚠️  Could not parse LLM response as JSON: {raw_text[:200]}")
                    # Safe default: check everything
                    needs = {
                        "needs_safety_check": True,
                        "needs_deficiency_check": False,
                        "needs_recommendations": False,
                        "reasoning": "Could not parse LLM intent — defaulting to safety check"
                    }
            else:
                print(f"   ⚠️  No JSON found in LLM response: {raw_text[:200]}")
                needs = {
                    "needs_safety_check": True,
                    "needs_deficiency_check": False,
                    "needs_recommendations": False,
                    "reasoning": "Could not parse LLM intent — defaulting to safety check"
                }
        
        print(f"   📊 Analysis: {needs['reasoning']}")
        
        return needs
    
    def _evaluate_progress(self, state: Dict[str, Any], needs: Dict[str, bool]) -> Dict[str, Any]:
        """
        Evaluate current progress and confidence.
        
        Checks:
        - What's been done vs what's needed
        - Confidence levels of results
        - Any AMBIGUOUS entities that need clarification
        
        Returns:
            {
                'completed': ['safety_check', ...],
                'pending': ['deficiency_check', ...],
                'confidence': 0.85,
                'needs_clarification': True/False
            }
        """
        completed = []
        pending = []
        
        # Check what's been done
        if state.get('safety_checked', False):
            completed.append('safety_check')
        elif needs.get('needs_safety_check'):
            pending.append('safety_check')
        
        if state.get('deficiency_checked', False):
            completed.append('deficiency_check')
        elif needs.get('needs_deficiency_check'):
            pending.append('deficiency_check')
        
        if state.get('recommendations_checked', False):
            completed.append('recommendations')
        elif needs.get('needs_recommendations'):
            pending.append('recommendations')
        
        # Calculate overall confidence
        confidence = self._calculate_confidence(state, completed)
        
        # Check for ambiguous entities
        needs_clarification = self._check_for_ambiguities(state)
        
        return {
            'completed': completed,
            'pending': pending,
            'confidence': confidence,
            'needs_clarification': needs_clarification
        }
    
    def _calculate_confidence(self, state: Dict[str, Any], completed: list) -> float:
        """Calculate overall confidence based on completed checks."""
        if not completed:
            return 0.0
        
        confidences = []
        
        if 'safety_check' in completed:
            confidences.append(state.get('safety_results', {}).get('confidence', 0.5))
        
        if 'deficiency_check' in completed:
            confidences.append(state.get('deficiency_results', {}).get('confidence', 0.5))
        
        if 'recommendations' in completed:
            confidences.append(state.get('recommendation_results', {}).get('confidence', 0.5))
        
        return sum(confidences) / len(confidences) if confidences else 0.0
    
    def _check_for_ambiguities(self, state: Dict[str, Any]) -> bool:
        """Check if any normalized entities are ambiguous."""
        # Check medications
        for med in state.get('normalized_medications', []):
            if med.get('confidence') == 'AMBIGUOUS':
                return True
        
        # Check supplements
        for supp in state.get('normalized_supplements', []):
            if supp.get('confidence') == 'AMBIGUOUS':
                return True
        
        return False
    
    def _make_decision(
        self, 
        state: Dict[str, Any], 
        needs: Dict[str, bool], 
        evaluation: Dict[str, Any]
    ) -> Dict[str, str]:
        """
        Make final decision about next action.
        
        Decision logic:
        1. If entities are ambiguous → clarify
        2. If pending checks → do next check
        3. If confidence low and iterations < 3 → loop back
        4. If everything done and confidence good → synthesize
        
        Returns:
            {
                'action': 'check_safety' | 'check_deficiency' | 'get_recommendations' | 'synthesize' | 'clarify',
                'reasoning': 'why this decision'
            }
        """
        iterations = state.get('iterations', 0)
        
        # Check for ambiguities first
        if evaluation['needs_clarification']:
            return {
                'action': 'clarify',
                'reasoning': 'Entities are ambiguous and need user clarification'
            }
        
        # Do pending checks
        if 'safety_check' in evaluation['pending']:
            return {
                'action': 'check_safety',
                'reasoning': 'Safety check needed based on question analysis'
            }
        
        if 'deficiency_check' in evaluation['pending']:
            return {
                'action': 'check_deficiency',
                'reasoning': 'Deficiency analysis needed based on question analysis'
            }
        
        if 'recommendations' in evaluation['pending']:
            return {
                'action': 'get_recommendations',
                'reasoning': 'Recommendations requested by user'
            }
        
        # Check if we need more evidence
        if evaluation['confidence'] < 0.7 and iterations < 3:
            return {
                'action': 'need_more_evidence',
                'reasoning': f"Confidence too low ({evaluation['confidence']:.2f}), need more investigation"
            }
        
        # Everything done - synthesize answer
        return {
            'action': 'synthesize',
            'reasoning': 'All required checks complete with sufficient confidence'
        }


# Convenience function for LangGraph
def supervisor_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Entry point for LangGraph workflow.
    """
    agent = SupervisorAgent()
    return agent(state)


if __name__ == "__main__":
    # Test the supervisor
    test_state = {
        'user_question': 'Is Fish Oil safe with my medications?',
        'patient_profile': {
            'medications': [
                {'drug_name': 'Warfarin', 'drug_id': 'DB00682'}
            ],
            'supplements': [],
            'dietary_restrictions': []
        },
        'entities_extracted': False,
        'graph_interface': None  # Would be actual graph interface
    }
    
    agent = SupervisorAgent()
    result = agent(test_state)
    
    print("\n" + "="*50)
    print("SUPERVISOR DECISION:")
    print(f"Action: {result['supervisor_decision']}")
    print(f"Reasoning: {result['supervisor_reasoning']}")
