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
            state['question_type'] = self._get_llm_response(prompt, max_tokens=20).lower()
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
        
        prompt = f"""Extract supplement names, medication names, conditions, and dietary restrictions from this question.

Available node types in database:
- Supplement: {', '.join(self.graph_db.get_property_values('Supplement', 'supplement_name', 10))}
- Medication: {', '.join(self.graph_db.get_property_values('Medication', 'medication_name', 10))}
- Drug: Large database of drugs
{profile_info}

Question: {state['user_question']}

Return a JSON object with these keys (empty lists if none found):
{{
  "supplements": ["supplement1", "supplement2"],
  "medications": ["med1", "med2"],
  "conditions": ["condition1"],
  "diet": ["vegan", "vegetarian"]
}}

Return ONLY valid JSON, no other text."""

        try:
            response = self._get_llm_response(prompt, max_tokens=200)
            # Clean up response
            response = response.strip()
            if response.startswith("```json"):
                response = response.replace("```json", "").replace("```", "").strip()
            
            state['entities'] = json.loads(response)
        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"Entity extraction failed: {e}")
            state['entities'] = {
                'supplements': [],
                'medications': [],
                'conditions': [],
                'diet': []
            }
        
        return state

    def generate_query(self, state: WorkflowState) -> WorkflowState:
        """
        Step 3: Generate Cypher query based on question type.
        
        Creates appropriate database query for the question.
        """
        question_type = state.get('question_type', 'general_knowledge')
        
        # For general knowledge, skip query generation
        if question_type == 'general_knowledge':
            state['cypher_query'] = None
            return state
        
        entities = state.get('entities', {})
        
        # Build schema info
        schema_info = f"""
Database Schema:
Nodes: {', '.join(self.schema['node_labels'])}
Relationships: {', '.join(self.schema['relationship_types'])}

Key patterns:
- Safety checks: (Supplement)-[:SUPPLEMENT_INTERACTS_WITH]->(Medication)
- Equivalence: (Supplement)-[:CONTAINS]->(ActiveIngredient)-[:EQUIVALENT_TO]->(Drug)
- Similar effects: (Supplement)-[:HAS_SIMILAR_EFFECT_TO]->(Category)<-[:BELONGS_TO]-(Drug)
"""

        prompt = f"""Generate a Cypher query for this supplement safety question.

{schema_info}

Question Type: {question_type}
Question: {state['user_question']}
Extracted Entities: {json.dumps(entities, indent=2)}

Guidelines:
- Use MATCH patterns to traverse relationships
- Use WHERE clauses for filtering
- Always LIMIT results (typically 10-25)
- For safety checks, look for interactions across multiple pathways
- Return relevant node properties and relationship details

Return ONLY the Cypher query, no explanation."""

        try:
            cypher = self._get_llm_response(prompt, max_tokens=300)
            # Clean up response
            cypher = cypher.strip()
            if cypher.startswith("```"):
                cypher = "\n".join(
                    line for line in cypher.split("\n")
                    if not line.startswith("```") and not line.lower().startswith("cypher")
                ).strip()
            
            state['cypher_query'] = cypher
        except Exception as e:
            logger.error(f"Query generation failed: {e}")
            state['error'] = f"Query generation error: {str(e)}"
            state['cypher_query'] = None
        
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
            
            # Extract safety warnings from results
            warnings = []
            for result in results:
                # Look for interaction-related fields
                if 'interaction_type' in result:
                    if result['interaction_type'] == 'EQUIVALENCE':
                        warnings.append(
                            f"⚠️ {result.get('supplement', 'Supplement')} contains "
                            f"the same drug as {result.get('medication', 'medication')} - "
                            f"risk of double dosing!"
                        )
                    elif 'description' in result:
                        warnings.append(f"⚠️ {result['description']}")
            
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
                "Please try rephrasing your question or contact support if this persists."
            )
            return state
        
        question_type = state.get('question_type', 'general_knowledge')
        
        # For general knowledge, use LLM knowledge
        if question_type == 'general_knowledge':
            prompt = f"""Answer this general supplement/health question clearly and accurately:

Question: {state['user_question']}

Provide a helpful, evidence-based answer. Mention when professional medical advice is needed."""
            
            state['final_answer'] = self._get_llm_response(prompt, max_tokens=400)
            return state
        
        # For database queries, format results
        results = state.get('results', [])
        
        if not results:
            state['final_answer'] = (
                "I didn't find specific information in the database for that question. "
                "This could mean:\n"
                "- The supplements/medications aren't in our database yet\n"
                "- There are no documented interactions\n"
                "- The question needs to be rephrased\n\n"
                "Please consult with a healthcare provider for personalized advice."
            )
            return state
        
        # Use LLM to format results naturally
        prompt = f"""Convert these database query results into a clear, helpful answer.

Original Question: {state['user_question']}
Question Type: {question_type}

Database Results:
{json.dumps(results[:10], indent=2)}

Total Results: {len(results)}

Format the answer to:
1. Directly answer the user's question
2. Highlight any safety concerns prominently
3. Be specific about interactions, dosages, or risks
4. Recommend consulting healthcare providers for serious concerns
5. Keep it concise but complete

Answer:"""

        state['final_answer'] = self._get_llm_response(prompt, max_tokens=500)
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