"""
LangGraph Workflow Agent for Supplement Safety

Multi-step reasoning workflow:
1. Classify question type
2. Extract entities (supplements, medications, conditions)
3. Generate appropriate Cypher query
4. Execute query against knowledge graph
5. Format results into natural language answer
"""

import json
import logging
from typing import Any, Dict, List, Optional, TypedDict

from anthropic import Anthropic

from .graph_interface import GraphInterface

logger = logging.getLogger(__name__)


class WorkflowState(TypedDict):
    """State that flows through workflow steps."""
    user_question: str
    user_profile: Optional[Dict[str, Any]]
    question_type: Optional[str]
    entities: Optional[Dict[str, List[str]]]
    cypher_query: Optional[str]
    results: Optional[List[Dict]]
    safety_warnings: Optional[List[str]]
    final_answer: Optional[str]
    error: Optional[str]


class WorkflowAgent:
    """
    LangGraph workflow agent for supplement safety queries.
    
    Handles natural language questions and translates them into
    knowledge graph queries with safety-first reasoning.
    """

    MODEL_NAME = "claude-sonnet-4-20250514"
    
    # Question type categories
    QUESTION_TYPES = [
        "safety_check",        # Is X safe with Y?
        "deficiency",          # What am I deficient in?
        "recommendation",      # What supplements help with X?
        "comparison",          # X vs Y for condition Z?
        "general_knowledge",   # What is X? How does Y work?
    ]

    def __init__(self, graph_interface: GraphInterface, anthropic_api_key: str):
        """
        Initialize workflow agent.
        
        Args:
            graph_interface: Connected Neo4j interface
            anthropic_api_key: Anthropic API key for Claude
        """
        self.graph_db = graph_interface
        self.anthropic = Anthropic(api_key=anthropic_api_key)
        self.schema = graph_interface.get_schema_info()
        logger.info("WorkflowAgent initialized")

    def _get_llm_response(
        self, 
        prompt: str, 
        max_tokens: int = 300,
        system: Optional[str] = None
    ) -> str:
        """Get response from Claude."""
        try:
            messages = [{"role": "user", "content": prompt}]
            
            kwargs = {
                "model": self.MODEL_NAME,
                "max_tokens": max_tokens,
                "messages": messages
            }
            
            if system:
                kwargs["system"] = system
            
            response = self.anthropic.messages.create(**kwargs)
            content = response.content[0]
            return content.text.strip() if hasattr(content, "text") else str(content)
        except Exception as e:
            logger.error(f"LLM request failed: {e}")
            raise

    def classify_question(self, state: WorkflowState) -> WorkflowState:
        """
        Step 1: Classify the question type.
        
        Determines what kind of query this is to guide subsequent steps.
        """
        prompt = f"""Classify this supplement safety question into ONE category:

Categories:
- safety_check: Asking about interactions or safety of combining supplements/drugs
- deficiency: Asking about nutrient deficiencies based on diet/medications
- recommendation: Asking which supplements to take for a condition/goal
- comparison: Comparing two or more supplements
- general_knowledge: General questions about supplements/health concepts

Question: {state['user_question']}

Respond with ONLY the category name, nothing else."""

        try:
            classification = self._get_llm_response(prompt, max_tokens=20).lower().strip()
            state['question_type'] = classification
            logger.info(f"✓ Classified as: {classification}")
        except Exception as e:
            logger.error(f"Classification failed: {e}")
            state['question_type'] = 'general_knowledge'
            state['error'] = f"Classification error: {str(e)}"
        
        return state

    def extract_entities(self, state: WorkflowState) -> WorkflowState:
        """
        Step 2: Extract relevant entities from question and profile.
        
        Identifies supplements, medications, conditions, etc.
        """
        profile = state.get('user_profile', {})
        
        # Build context from user profile
        profile_info = ""
        if profile:
            if profile.get('medications'):
                profile_info += f"\nUser medications: {', '.join(profile['medications'])}"
            if profile.get('supplements'):
                profile_info += f"\nUser supplements: {', '.join(profile['supplements'])}"
            if profile.get('conditions'):
                profile_info += f"\nUser conditions: {', '.join(profile['conditions'])}"
            if profile.get('diet'):
                profile_info += f"\nUser diet: {', '.join(profile['diet'])}"
        
        prompt = f"""Extract supplement names and medication names from this question.

Question: {state['user_question']}

Examples of supplements: Fish Oil, Vitamin D, St. John's Wort, Ginkgo, Red Yeast Rice
Examples of medications: Warfarin, Metformin, Atorvastatin, Lisinopril, Sertraline

{profile_info}

Return a JSON object with these keys (empty lists if none found):
{{
  "supplements": ["supplement1"],
  "medications": ["medication1"]
}}

Return ONLY valid JSON, no other text."""

        try:
            response = self._get_llm_response(prompt, max_tokens=200)
            # Clean up response
            response = response.strip()
            if response.startswith("```json"):
                response = response.replace("```json", "").replace("```", "").strip()
            if response.endswith("```"):
                response = response[:-3].strip()
            
            entities = json.loads(response)
            state['entities'] = entities
            logger.info(f"✓ Extracted entities: {entities}")
        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"Entity extraction failed: {e}")
            logger.warning(f"LLM response was: {response if 'response' in locals() else 'N/A'}")
            state['entities'] = {
                'supplements': [],
                'medications': [],
                'conditions': [],
                'diet': []
            }
        
        return state

    def get_template_query(self, question_type: str, entities: Dict) -> str:
        """
        Get pre-built query template matching the actual knowledge graph structure.
        Based on the documented interaction detection pathways.
        """
        supplements = entities.get('supplements', [])
        medications = entities.get('medications', [])
        
        # Safety check - uses all 3 pathways from documentation
        if question_type == 'safety_check' and supplements and medications:
            # Convert to lowercase for case-insensitive matching
            supp_list = [s.lower() for s in supplements]
            med_list = [m.lower() for m in medications]
            
            return f"""
            MATCH (s:Supplement)-[i:SUPPLEMENT_INTERACTS_WITH]->(m:Medication)
            WHERE toLower(s.supplement_name) IN {supp_list}
            AND toLower(m.medication_name) IN {med_list}
            RETURN 
                'DIRECT_INTERACTION' as pathway,
                s.supplement_name as supplement,
                m.medication_name as medication,
                coalesce(i.interaction_description, 'Interaction documented') as warning
            LIMIT 10
            
            UNION ALL
            
            MATCH (s:Supplement)-[sim:HAS_SIMILAR_EFFECT_TO]->(c:Category)
                <-[:BELONGS_TO]-(d:Drug)<-[:MEDICATION_CONTAINS_DRUG]-(m:Medication)
            WHERE toLower(s.supplement_name) IN {supp_list}
            AND toLower(m.medication_name) IN {med_list}
            RETURN 
                'SIMILAR_EFFECT' as pathway,
                s.supplement_name as supplement,
                m.medication_name as medication,
                c.category as warning
            LIMIT 10
            
            UNION ALL
            
            MATCH (s:Supplement)-[:CONTAINS]->(a:ActiveIngredient)
                -[:EQUIVALENT_TO]->(d:Drug)<-[:MEDICATION_CONTAINS_DRUG]-(m:Medication)
            WHERE toLower(s.supplement_name) IN {supp_list}
            AND toLower(m.medication_name) IN {med_list}
            RETURN 
                'DRUG_EQUIVALENCE' as pathway,
                s.supplement_name as supplement,
                m.medication_name as medication,
                'Contains equivalent drug' as warning
            LIMIT 10
            """
        
        # If only supplements mentioned (check what they are)
        if supplements and not medications:
            supp_list = [s.lower() for s in supplements]
            return f"""
            MATCH (s:Supplement)
            WHERE toLower(s.supplement_name) IN {supp_list}
            RETURN 
                'INFO' as pathway,
                s.supplement_name as supplement,
                'N/A' as medication,
                coalesce(s.safety_rating, 'Supplement found') as warning
            LIMIT 10
            """
        
        # If only medications mentioned
        if medications and not supplements:
            med_list = [m.lower() for m in medications]
            return f"""
            MATCH (m:Medication)
            WHERE toLower(m.medication_name) IN {med_list}
            RETURN 
                'INFO' as pathway,
                'N/A' as supplement,
                m.medication_name as medication,
                'Medication found' as warning
            LIMIT 10
            """
        
        # Default: show some supplements
        return """
        MATCH (s:Supplement)
        RETURN 
            'BROWSE' as pathway,
            s.supplement_name as supplement,
            'N/A' as medication,
            coalesce(s.safety_rating, 'Available') as warning
        ORDER BY s.supplement_name
        LIMIT 20
        """

    def generate_query(self, state: WorkflowState) -> WorkflowState:
        """
        Step 3: Generate Cypher query based on question type.
        Uses safe templates to avoid syntax errors.
        """
        question_type = state.get('question_type', 'general_knowledge')
        
        # Skip query for pure knowledge questions
        if question_type == 'general_knowledge':
            state['cypher_query'] = None
            return state
        
        entities = state.get('entities', {})
        
        # Always use safe template queries
        query = self.get_template_query(question_type, entities)
        state['cypher_query'] = query.strip()
        
        logger.info(f"✓ Generated query for {question_type}")
        
        return state

    def execute_query(self, state: WorkflowState) -> WorkflowState:
        """
        Step 4: Execute the Cypher query.
        
        Runs query against knowledge graph and captures results.
        """
        cypher_query = state.get('cypher_query')
        
        if not cypher_query:
            state['results'] = []
            return state
        
        try:
            results = self.graph_db.execute_query(cypher_query)
            state['results'] = results
            logger.info(f"✓ Query returned {len(results)} results")
            
            # Extract safety warnings from results
            warnings = []
            for result in results:
                pathway = result.get('pathway', '')
                if pathway == 'DRUG_EQUIVALENCE':
                    warnings.append(
                        f"🚨 CRITICAL: {result.get('supplement', 'Supplement')} contains "
                        f"the same active drug as {result.get('medication', 'medication')}!"
                    )
                elif pathway == 'DIRECT_INTERACTION':
                    warnings.append(
                        f"⚠️ WARNING: {result.get('supplement', 'Supplement')} interacts with "
                        f"{result.get('medication', 'medication')}"
                    )
                elif pathway == 'SIMILAR_EFFECT':
                    warnings.append(
                        f"⚠️ CAUTION: {result.get('supplement', 'Supplement')} has similar effects to "
                        f"{result.get('medication', 'medication')}"
                    )
            
            state['safety_warnings'] = warnings
            
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            state['error'] = f"Query execution error: {str(e)}"
            state['results'] = []
        
        return state

    def format_answer(self, state: WorkflowState) -> WorkflowState:
        """
        Step 5: Format results into natural language answer.
        
        Converts raw database results into user-friendly response.
        """
        if state.get('error'):
            state['final_answer'] = (
                f"I encountered an issue: {state['error']}\n\n"
                "Please try rephrasing your question."
            )
            return state
        
        question_type = state.get('question_type', 'general_knowledge')
        
        # For general knowledge, use LLM
        if question_type == 'general_knowledge':
            prompt = f"""Answer this supplement/health question clearly and accurately:

    Question: {state['user_question']}

    Provide a helpful, evidence-based answer. Mention when professional medical advice is needed."""
            
            state['final_answer'] = self._get_llm_response(prompt, max_tokens=400)
            return state
        
        # For database queries
        results = state.get('results', [])
        
        if not results:
            state['final_answer'] = (
                "I didn't find any documented interactions for that combination in our database.\n\n"
                "This could mean:\n"
                "• No known interactions exist\n"
                "• The supplement/medication isn't in our database yet\n"
                "• Try using more common names (e.g., 'fish oil' instead of 'omega-3')\n\n"
                "⚠️ Always consult your healthcare provider before combining supplements with medications."
            )
            return state
        
        # Format results with proper safety warnings
        answer_parts = []
        
        # Group by pathway type
        direct_interactions = [r for r in results if r.get('pathway') == 'DIRECT_INTERACTION']
        similar_effects = [r for r in results if r.get('pathway') == 'SIMILAR_EFFECT']
        equivalences = [r for r in results if r.get('pathway') == 'DRUG_EQUIVALENCE']
        info_results = [r for r in results if r.get('pathway') in ['INFO', 'BROWSE']]
        
        if equivalences:
            answer_parts.append("🚨 **CRITICAL WARNING - DRUG EQUIVALENCE:**")
            for r in equivalences:
                answer_parts.append(
                    f"• **{r['supplement']}** + **{r['medication']}**: "
                    f"Contains the same active drug - RISK OF DOUBLE DOSING!"
                )
            answer_parts.append("")
        
        if direct_interactions:
            answer_parts.append("⚠️ **DOCUMENTED INTERACTIONS:**")
            for r in direct_interactions:
                answer_parts.append(
                    f"• **{r['supplement']}** + **{r['medication']}**: {r['warning']}"
                )
            answer_parts.append("")
        
        if similar_effects:
            answer_parts.append("⚠️ **SIMILAR PHARMACOLOGICAL EFFECTS:**")
            for r in similar_effects:
                # Now we add the text here instead of in the query
                answer_parts.append(
                    f"• **{r['supplement']}** + **{r['medication']}**: "
                    f"Has similar effects to {r['warning']} - risk of additive effects"
                )
            answer_parts.append("")
        
        if answer_parts:
            answer_parts.append(
                "**Recommendation:** Consult your healthcare provider before taking "
                "these supplements with your medications."
            )
            state['final_answer'] = "\n".join(answer_parts)
        elif info_results:
            # Just browsing or looking up info
            lines = []
            for r in info_results[:10]:
                name = r.get('supplement') if r.get('supplement') != 'N/A' else r.get('medication')
                lines.append(f"• {name}: {r['warning']}")
            state['final_answer'] = "\n".join(lines)
        else:
            state['final_answer'] = "No specific information found."
        
        return state

    def answer_question(
        self, 
        question: str, 
        user_profile: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Main entry point: Answer a supplement safety question.
        
        Args:
            question: User's natural language question
            user_profile: Optional dict with medications, conditions, diet, etc.
            
        Returns:
            Dict with answer, query details, and safety warnings
        """
        # Initialize state
        state = WorkflowState(
            user_question=question,
            user_profile=user_profile,
            question_type=None,
            entities=None,
            cypher_query=None,
            results=None,
            safety_warnings=None,
            final_answer=None,
            error=None
        )
        
        # Run workflow steps
        state = self.classify_question(state)
        state = self.extract_entities(state)
        state = self.generate_query(state)
        state = self.execute_query(state)
        state = self.format_answer(state)
        
        # Return results
        return {
            'answer': state.get('final_answer', 'No answer generated'),
            'question_type': state.get('question_type'),
            'entities': state.get('entities', {}),
            'cypher_query': state.get('cypher_query'),
            'results_count': len(state.get('results', [])),
            'raw_results': state.get('results', [])[:3],  # First 3 for display
            'safety_warnings': state.get('safety_warnings', []),
            'error': state.get('error')
        }