"""
LangGraph Workflow Agent - LLM-POWERED CYPHER GENERATION

Key improvement: Uses LLM to dynamically generate Cypher queries
based on the database schema and question type, rather than rigid templates.
"""

import json
import logging
from typing import Any, Dict, List, Optional, TypedDict

from anthropic import Anthropic

from agents.graph_interface import GraphInterface

logger = logging.getLogger(__name__)


class WorkflowState(TypedDict):
    """State that flows through workflow steps."""
    user_question: str
    user_profile: Optional[Dict[str, Any]]
    question_type: Optional[str]
    entities: Optional[Dict[str, List[str]]]
    cypher_query: Optional[str]
    results: Optional[List[Dict]]
    sanity_check: Optional[Dict[str, Any]]
    synthesis: Optional[Dict[str, Any]]
    safety_warnings: Optional[List[str]]
    final_answer: Optional[str]
    error: Optional[str]


class WorkflowAgent:
    """Personalized workflow agent with LLM-powered Cypher generation."""

    MODEL_NAME = "claude-sonnet-4-20250514"
    
    # Database schema - loaded once at initialization
    SCHEMA = """
# Neo4j Knowledge Graph Schema for Supplement Safety Advisor

## Node Types

### Supplement
Properties:
- supplement_name: String (e.g., "Fish Oil", "Vitamin D")
- safety_rating: String (e.g., "Generally Safe", "Use with Caution")
- description: Text
- common_dosage: String

### Medication
Properties:
- medication_name: String (e.g., "Warfarin", "Metformin")
- drug_class: String (e.g., "Anticoagulant", "Antidiabetic")
- description: Text

### Drug
Properties:
- drug_name: String (DrugBank drug name)
- drugbank_id: String (e.g., "DB00682")
- description: Text

### Category
Properties:
- category: String (e.g., "Anticoagulant", "Anti-inflammatory")
- description: Text

### Symptom
Properties:
- symptom_name: String (e.g., "High Blood Pressure", "Insomnia")
- description: Text

### MedicalCondition
Properties:
- condition_name: String (e.g., "Hypertension", "Diabetes")
- description: Text

### Nutrient
Properties:
- nutrient_name: String (e.g., "Vitamin B12", "CoQ10")
- description: Text

### DietaryRestriction
Properties:
- diet_type: String (e.g., "Vegan", "Vegetarian")
- description: Text

## Relationship Types

### Supplement Relationships

TREATS
- (Supplement)-[:TREATS]->(Symptom)
- Indicates supplement helps with symptom
- Properties: evidence_strength (String: "Strong", "Moderate", "Weak")

HAS_SIMILAR_EFFECT_TO
- (Supplement)-[:HAS_SIMILAR_EFFECT_TO]->(Category)
- Indicates supplement has pharmacological effects similar to drug category
- Properties: confidence (Float: 0.0-1.0)

ADDRESSES
- (Supplement)-[:ADDRESSES]->(MedicalCondition)
- Indicates supplement may help with medical condition
- Properties: evidence_strength (String: "Strong", "Moderate", "Weak")

CONTAINS_NUTRIENT
- (Supplement)-[:CONTAINS_NUTRIENT]->(Nutrient)
- Indicates supplement provides this nutrient

INTERACTS_WITH_DRUG
- (Supplement)-[:INTERACTS_WITH_DRUG]->(Drug)
- Direct supplement-drug interaction
- Properties: severity (String: "Major", "Moderate", "Minor"), mechanism (Text)

### Medication Relationships

CONTAINS_DRUG
- (Medication)-[:CONTAINS_DRUG]->(Drug)
- Links medication to its active pharmaceutical ingredient

DEPLETES
- (Medication)-[:DEPLETES]->(Nutrient)
- Indicates medication causes nutrient depletion
- Properties: mechanism (Text), severity (String)

### Drug Relationships

BELONGS_TO
- (Drug)-[:BELONGS_TO]->(Category)
- Indicates drug belongs to pharmacological category

### Diet Relationships

DEFICIENT_IN
- (DietaryRestriction)-[:DEFICIENT_IN]->(Nutrient)
- Indicates diet type commonly lacks this nutrient
- Properties: risk_level (String: "High", "Moderate", "Low")
"""

    def __init__(self, graph_interface: GraphInterface, anthropic_api_key: str):
        """Initialize workflow agent."""
        self.graph_db = graph_interface
        self.anthropic = Anthropic(api_key=anthropic_api_key)
        logger.info("WorkflowAgent initialized - LLM-powered Cypher generation")

    def _get_llm_response(self, prompt: str, max_tokens: int = 300) -> str:
        """Get response from Claude."""
        try:
            response = self.anthropic.messages.create(
                model=self.MODEL_NAME,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}]
            )
            return response.content[0].text.strip()
        except Exception as e:
            logger.error(f"LLM request failed: {e}")
            raise

    # ========================================================================
    # STEP 1: CLASSIFY QUESTION
    # ========================================================================
    
    def classify_question(self, state: WorkflowState) -> WorkflowState:
        """Step 1: Classify question type."""
        prompt = f"""Classify this supplement safety question into ONE category:

Categories:
- safety_check: Asking if supplement is safe with medications/conditions
- comparison: Comparing two supplements (look for "vs", "or", "better")
- recommendation: Asking which supplements to take for a condition/goal
- deficiency: Asking about nutrient deficiencies or depletion
- general_knowledge: General info about supplements

Question: {state['user_question']}

Respond with ONLY the category name."""

        try:
            classification = self._get_llm_response(prompt, max_tokens=20).lower().strip()
            state['question_type'] = classification
            logger.info(f"✓ Classified as: {classification}")
        except Exception as e:
            logger.error(f"Classification failed: {e}")
            state['question_type'] = 'general_knowledge'
            state['error'] = f"Classification error: {str(e)}"
        
        return state
    
    # ========================================================================
    # STEP 2: EXTRACT ENTITIES
    # ========================================================================
    
    def extract_entities(self, state: WorkflowState) -> WorkflowState:
        """Step 2: Extract entities from question + profile."""
        profile = state.get('user_profile', {})
        
        # Build comprehensive context from profile
        profile_context = ""
        if profile:
            if profile.get('medications'):
                profile_context += f"\nUser's medications: {', '.join(profile['medications'])}"
            if profile.get('supplements'):
                profile_context += f"\nUser's current supplements: {', '.join(profile['supplements'])}"
            if profile.get('conditions'):
                profile_context += f"\nUser's medical conditions: {', '.join(profile['conditions'])}"
            if profile.get('diet'):
                profile_context += f"\nUser's dietary restrictions: {', '.join(profile['diet'])}"
        
        prompt = f"""Extract ALL relevant entities from the question and user profile.

Question: {state['user_question']}
{profile_context}

Return JSON with these keys:
{{
  "supplements": ["supplement names from question"],
  "medications": ["medication names from question AND profile"],
  "conditions": ["conditions from question AND profile"],
  "diet": ["diet types from profile"],
  "nutrients": ["specific nutrients mentioned"]
}}

IMPORTANT:
- Include medications from BOTH the question AND user profile
- Include conditions from BOTH question AND profile
- Use proper capitalization (e.g., "Fish Oil", "Warfarin")

EXAMPLES:
Question: "Can I take magnesium?"
Profile medications: Warfarin
→ {{"supplements": ["Magnesium"], "medications": ["Warfarin"], "conditions": [], "diet": [], "nutrients": []}}

Question: "magnesium or melatonin for sleep"
→ {{"supplements": ["Magnesium", "Melatonin"], "medications": [], "conditions": [], "diet": [], "nutrients": []}}

Question: "Am I at risk for B12 deficiency?"
Profile: medications=[Metformin], diet=[Vegan]
→ {{"supplements": [], "medications": ["Metformin"], "conditions": [], "diet": ["Vegan"], "nutrients": ["Vitamin B12"]}}

Return ONLY valid JSON."""

        try:
            response = self._get_llm_response(prompt, max_tokens=400)
            response = response.strip()
            if response.startswith("```json"):
                response = response.replace("```json", "").replace("```", "").strip()
            
            entities = json.loads(response)
            
            # Ensure all keys exist
            for key in ['supplements', 'medications', 'conditions', 'diet', 'nutrients']:
                if key not in entities:
                    entities[key] = []
            
            state['entities'] = entities
            logger.info(f"✓ Extracted: {entities}")
            
        except Exception as e:
            logger.warning(f"Entity extraction failed: {e}")
            state['entities'] = {
                'supplements': [], 
                'medications': [], 
                'conditions': [],
                'diet': [],
                'nutrients': []
            }
        
        return state
    
    # ========================================================================
    # STEP 3: GENERATE CYPHER QUERY (LLM-POWERED)
    # ========================================================================
    
    def generate_query(self, state: WorkflowState) -> WorkflowState:
        """Step 3: Use LLM to generate Cypher query based on question type and entities."""
        question_type = state.get('question_type', 'general_knowledge')
        entities = state.get('entities', {})
        question = state['user_question']
        
        # Skip query generation for general knowledge
        if question_type == 'general_knowledge':
            state['cypher_query'] = None
            logger.info("Skipping query generation for general_knowledge")
            return state
        
        # Build query generation prompt with schema and guidance
        query_guidance = self._get_query_guidance(question_type)
        
        prompt = f"""You are a Cypher query expert for a Neo4j supplement safety database.

**DATABASE SCHEMA:**
{self.SCHEMA}

**USER QUESTION:** {question}

**QUESTION TYPE:** {question_type}

**EXTRACTED ENTITIES:**
{json.dumps(entities, indent=2)}

**QUERY GUIDANCE FOR {question_type.upper()}:**
{query_guidance}

**YOUR TASK:**
Generate a Cypher query that:
1. Uses the entities extracted from the question
2. Follows the query patterns appropriate for {question_type}
3. Returns relevant data for answering the user's question
4. Uses toLower() for case-insensitive string matching
5. For medications convert to the drug bank medication name
5. Limits results appropriately (LIMIT 10-20)

**CRITICAL RULES:**
- Return ONLY the Cypher query, no explanation
- Use proper Neo4j syntax
- Include all relevant relationships for the question type
- For safety checks: MUST check user's medications from profile
- For deficiency: MUST check BOTH diet AND medications
- For recommendations: MUST filter by user's medications to avoid interactions

**FORMAT:**
Return the query starting with MATCH, no markdown formatting.

Generate the Cypher query now:"""

        try:
            cypher_query = self._get_llm_response(prompt, max_tokens=800)
            
            # Clean up the response
            cypher_query = cypher_query.strip()
            if cypher_query.startswith("```"):
                # Remove markdown code blocks
                cypher_query = cypher_query.replace("```cypher", "").replace("```", "").strip()
            
            state['cypher_query'] = cypher_query
            logger.info(f"✓ Generated Cypher query:\n{cypher_query}")
            
        except Exception as e:
            logger.error(f"Cypher generation failed: {e}")
            state['error'] = f"Query generation error: {str(e)}"
            state['cypher_query'] = None
        
        return state
    
    def _get_query_guidance(self, question_type: str) -> str:
        """Get query pattern guidance based on question type."""
        
        guidance = {
            'safety_check': """
GOAL: Find interactions between supplement and user's medications

PATTERN:
MATCH (s:Supplement)-[interaction]->(intermediate)<-[connection]-(m:Medication)
WHERE toLower(s.supplement_name) IN [supplement_list]
  AND toLower(m.medication_name) IN [user_medications_from_profile]

Common paths:
1. Direct interaction: (Supplement)-[:INTERACTS_WITH_DRUG]->(Drug)<-[:CONTAINS_DRUG]-(Medication)
2. Similar effects: (Supplement)-[:HAS_SIMILAR_EFFECT_TO]->(Category)<-[:BELONGS_TO]-(Drug)<-[:CONTAINS_DRUG]-(Medication)

RETURN supplement name, medication name, interaction type, severity/confidence
""",
            
            'deficiency': """
GOAL: Find nutrient deficiencies from BOTH diet and medications

PATTERN:
// First find nutrient at risk
MATCH path where diet OR medication causes deficiency

Common paths:
1. Diet risk: (DietaryRestriction)-[:DEFICIENT_IN]->(Nutrient)
2. Medication depletion: (Medication)-[:DEPLETES]->(Nutrient)
3. Combined risk: Both paths pointing to same Nutrient

Use UNION or WITH clauses to combine results
RETURN nutrient name, risk sources (diet and/or medications), severity
""",
            
            'recommendation': """
GOAL: Find supplements that help condition AND are safe with user's medications

PATTERN:
// Step 1: Find supplements that address the condition
MATCH (s:Supplement)-[:ADDRESSES]->(condition:MedicalCondition)
WHERE condition matches user's condition
  AND evidence_strength IN ['Strong', 'Moderate']

// Step 2: Filter out supplements that interact with user's medications
WITH s
OPTIONAL MATCH (s)-[interaction]-(medication path)
WHERE medication in user's medication list

// Step 3: Return only safe supplements
WHERE no interaction found OR interaction is null

RETURN supplement name, benefit, evidence level
""",
            
            'comparison': """
GOAL: Compare two supplements across multiple dimensions

PATTERN:
// Get information about both supplements
MATCH (s:Supplement)
WHERE toLower(s.supplement_name) IN [supplement1, supplement2]

// Get their benefits
OPTIONAL MATCH (s)-[:TREATS]->(sym:Symptom)
OPTIONAL MATCH (s)-[:ADDRESSES]->(cond:MedicalCondition)

// Get safety info
OPTIONAL MATCH (s)-[:HAS_SIMILAR_EFFECT_TO]->(cat:Category)

Use UNION to get different types of info
RETURN supplement, property type, property value
""",
            
            'general_knowledge': """
Not applicable - no query needed for general knowledge questions.
"""
        }
        
        return guidance.get(question_type, "Generate appropriate query based on schema.")
    
    # ========================================================================
    # STEP 4: EXECUTE QUERY
    # ========================================================================
    
    def execute_query(self, state: WorkflowState) -> WorkflowState:
        """Step 4: Execute Cypher query."""
        cypher_query = state.get('cypher_query')
        
        if not cypher_query:
            logger.info("No query to execute")
            state['results'] = []
            return state
        
        try:
            results = self.graph_db.execute_query(cypher_query)
            state['results'] = results
            logger.info(f"✓ Query returned {len(results)} results")
            
            if results:
                logger.info(f"Sample result: {results[0]}")
            
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            logger.error(f"Failed query: {cypher_query}")
            state['error'] = f"Database error: {str(e)}"
            state['results'] = []
        
        return state
    
    # ========================================================================
    # STEP 5: SANITY CHECK
    # ========================================================================
    
    def sanity_check(self, state: WorkflowState) -> WorkflowState:
        """Step 5: Validate results make sense."""
        results = state.get('results', [])
        question_type = state.get('question_type', 'unknown')
        entities = state.get('entities', {})
        
        sanity = {
            'passed': True,
            'confidence': 'MEDIUM',
            'warnings': []
        }
        
        # Check 1: Results exist when expected
        if question_type in ['safety_check', 'deficiency', 'recommendation']:
            if not results:
                sanity['warnings'].append("No results found - supplement may not be in database")
                sanity['confidence'] = 'LOW'
        
        # Check 2: For safety checks, verify we checked user's medications
        if question_type == 'safety_check':
            user_meds = entities.get('medications', [])
            if user_meds and results:
                # Verify results mention user's medications
                result_meds = set()
                for r in results:
                    if 'medication' in r:
                        result_meds.add(r['medication'].lower())
                
                user_med_set = set(m.lower() for m in user_meds)
                if not result_meds.intersection(user_med_set):
                    sanity['warnings'].append("Results may not include user's medications")
        
        # Check 3: Interaction severity
        if results:
            for r in results:
                severity = r.get('severity', r.get('confidence', ''))
                if severity in ['Major', 'High'] or (isinstance(severity, float) and severity > 0.7):
                    sanity['confidence'] = 'HIGH'
                    sanity['warnings'].append("High-severity interaction detected")
                    break
        
        # Check 4: Evidence strength for recommendations
        if question_type == 'recommendation':
            if results:
                evidence_levels = [r.get('evidence_strength', 'Unknown') for r in results]
                if 'Strong' in evidence_levels:
                    sanity['confidence'] = 'HIGH'
                elif all(e in ['Weak', 'Unknown'] for e in evidence_levels):
                    sanity['confidence'] = 'LOW'
                    sanity['warnings'].append("Limited evidence for recommendations")
        
        state['sanity_check'] = sanity
        logger.info(f"✓ Sanity check: {sanity}")
        
        return state
    
    # ========================================================================
    # STEP 6: SYNTHESIZE RESPONSE
    # ========================================================================
    
    def synthesize_response(self, state: WorkflowState) -> WorkflowState:
        """Step 6: Create personalized natural language response."""
        results = state.get('results', [])
        question_type = state.get('question_type', 'unknown')
        
        # Handle no results
        if not results:
            if question_type == 'general_knowledge':
                state['final_answer'] = self._synthesize_general_knowledge(state)
            else:
                state['final_answer'] = self._synthesize_no_results_response(state)
            return state
        
        # Generate personalized response
        response_prompt = self._build_personalized_synthesis_prompt(state)
        
        try:
            synthesized = self._get_llm_response(response_prompt, max_tokens=600)
            
            # Add footer
            sanity = state.get('sanity_check', {})
            confidence = sanity.get('confidence', 'MEDIUM')
            warnings = sanity.get('warnings', [])
            
            footer_parts = []
            if warnings:
                footer_parts.append(f"\n**Note:** {'; '.join(warnings)}")
            
            footer_parts.append(f"\n**Confidence Level:** {confidence}")
            footer_parts.append(f"**Source:** Neo4j Knowledge Graph ({len(results)} records)")
            footer_parts.append("\n⚠️ Always consult your healthcare provider before making supplement decisions.")
            
            state['final_answer'] = synthesized + "\n" + "\n".join(footer_parts)
            
        except Exception as e:
            logger.error(f"Response synthesis failed: {e}")
            state['final_answer'] = self._fallback_format(state)
        
        return state
    
    def _build_personalized_synthesis_prompt(self, state: WorkflowState) -> str:
        """Build prompt for personalized synthesis."""
        question = state['user_question']
        question_type = state['question_type']
        results = state['results']
        profile = state.get('user_profile', {})
        
        # Extract profile
        user_meds = profile.get('medications', [])
        user_supps = profile.get('supplements', [])
        user_conditions = profile.get('conditions', [])
        user_diet = profile.get('diet', [])
        
        # Summarize results
        result_summary = json.dumps(results[:15], indent=2)
        
        # Build profile text
        profile_text = ""
        if user_meds:
            profile_text += f"\n• **Medications:** {', '.join(user_meds)}"
        if user_supps:
            profile_text += f"\n• **Current Supplements:** {', '.join(user_supps)}"
        if user_conditions:
            profile_text += f"\n• **Health Conditions:** {', '.join(user_conditions)}"
        if user_diet:
            profile_text += f"\n• **Diet:** {', '.join(user_diet)}"
        
        prompt = f"""You are creating a PERSONALIZED supplement safety response for THIS SPECIFIC USER.

**User's Question:** {question}

**Question Type:** {question_type}

**This User's Profile:**{profile_text if profile_text else " None provided"}

**Database Results (Neo4j):**
```json
{result_summary}
```

**CRITICAL RULES:**

1. **ADDRESS USER DIRECTLY:**
   ✅ "You should NOT take Fish Oil with your Warfarin"
   ❌ "People taking warfarin should avoid fish oil"
   
2. **USE THEIR SPECIFIC MEDICATIONS/CONDITIONS:**
   ✅ "Your Warfarin interacts with Fish Oil"
   ✅ "Given your Vegan diet and Metformin, you're at high risk for B12 deficiency"
   ❌ "Blood thinners interact with fish oil"
   
3. **ONLY USE DATABASE RESULTS:**
   - If database shows interaction → state it clearly
   - If database shows NO results → say "no known interactions found in our database"
   - DO NOT add generic warnings not in results
   
4. **QUESTION-TYPE SPECIFIC FORMATTING:**

   For SAFETY_CHECK:
   ```
   [✅ SAFE or ❌ NOT SAFE verdict]
   
   **Why:** [Explain interaction/lack thereof]
   
   **What You Should Do:** [Action items]
   ```
   
   For DEFICIENCY:
   ```
   **Your Deficiency Risk:** [HIGH/MODERATE/LOW]
   
   **Why:** [Explain diet and/or medication factors]
   
   **What You Should Do:** [Supplement recommendations or testing]
   ```
   
   For RECOMMENDATION:
   ```
   **Safe Options for You:**
   1. [Supplement] - [Why it helps, evidence level]
   2. [Supplement] - [Why it helps, evidence level]
   
   **What You Should Do:** [How to use them]
   ```
   
   For COMPARISON:
   ```
   **Comparison: [Supp1] vs [Supp2]**
   
   [Supp1]: [Benefits, safety with user's profile]
   
   [Supp2]: [Benefits, safety with user's profile]
   
   **For You:** [Which is better given their profile]
   ```

5. **KEEP CONCISE:** 2-4 paragraphs maximum

Now write the PERSONALIZED response for THIS user:"""
        
        return prompt
    
    def _synthesize_general_knowledge(self, state: WorkflowState) -> str:
        """Handle general knowledge questions without database."""
        question = state['user_question']
        
        prompt = f"""Answer this general supplement question briefly and accurately:

Question: {question}

Provide a 2-3 paragraph response covering:
- Basic information about the supplement/topic
- General safety considerations
- Suggestion to check interactions with their specific medications

Keep it concise and evidence-based."""
        
        try:
            answer = self._get_llm_response(prompt, max_tokens=400)
            return answer + "\n\n⚠️ For personalized safety advice, please add your medications in the sidebar."
        except:
            return "I can provide general information, but for personalized safety advice, please add your medications to your profile."
    
    def _synthesize_no_results_response(self, state: WorkflowState) -> str:
        """Personalized response when no results found."""
        entities = state.get('entities', {})
        profile = state.get('user_profile', {})
        question_type = state.get('question_type', 'unknown')
        
        supplements = entities.get('supplements', [])
        medications = entities.get('medications', [])
        
        supp_text = supplements[0] if supplements else "this supplement"
        
        if question_type == 'safety_check' and medications:
            return f"""I couldn't find interaction data between **{supp_text}** and your medications ({', '.join(medications)}) in our database.

**What This Means:**
Our database doesn't have documented interactions for this combination. This doesn't mean it's safe - just that we don't have the data.

**What You Should Do:**
• Consult your healthcare provider before taking {supp_text}
• Try asking about supplements we have extensive data on (Fish Oil, Vitamin D, St. John's Wort, etc.)"""
        
        elif question_type == 'deficiency':
            return f"""I couldn't find deficiency risk data for your profile in our database.

**What You Should Do:**
• Ask your doctor about nutrient testing
• Common medication-induced deficiencies include: B12 (Metformin), CoQ10 (Statins), Magnesium (Proton pump inhibitors)"""
        
        else:
            return f"""I couldn't find information about **{supp_text}** in our database.

**What You Should Do:**
• Try asking about supplements in our database: Fish Oil, Vitamin D, Magnesium, CoQ10, St. John's Wort, etc.
• Add your medications in the sidebar for personalized safety checks"""
    
    def _fallback_format(self, state: WorkflowState) -> str:
        """Simple fallback if synthesis fails."""
        results = state['results']
        
        lines = ["**Database Results:**\n"]
        
        for i, r in enumerate(results[:5], 1):
            lines.append(f"{i}. {json.dumps(r, indent=2)}")
        
        lines.append("\n⚠️ Please consult your healthcare provider.")
        
        return "\n".join(lines)
    
    # ========================================================================
    # MAIN ENTRY POINT
    # ========================================================================
    
    def answer_question(
        self, 
        question: str, 
        user_profile: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Main entry point - personalized workflow with LLM-powered query generation."""
        logger.info(f"\n{'='*60}")
        logger.info(f"NEW QUESTION: {question}")
        if user_profile:
            logger.info(f"PROFILE: {user_profile}")
        logger.info(f"{'='*60}")
        
        # Initialize state
        state = WorkflowState(
            user_question=question,
            user_profile=user_profile,
            question_type=None,
            entities=None,
            cypher_query=None,
            results=None,
            sanity_check=None,
            synthesis=None,
            safety_warnings=None,
            final_answer=None,
            error=None
        )
        
        # Run workflow
        state = self.classify_question(state)
        state = self.extract_entities(state)
        state = self.generate_query(state)  # Now LLM-powered!
        state = self.execute_query(state)
        state = self.sanity_check(state)
        state = self.synthesize_response(state)
        
        logger.info(f"✓ Workflow complete")
        
        # Return results
        return {
            'answer': state.get('final_answer', 'No answer generated'),
            'question_type': state.get('question_type'),
            'entities': state.get('entities', {}),
            'cypher_query': state.get('cypher_query'),
            'results_count': len(state.get('results', [])),
            'raw_results': state.get('results', [])[:3],
            'sanity_check': state.get('sanity_check', {}),
            'error': state.get('error')
        }
