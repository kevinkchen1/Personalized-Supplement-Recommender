"""
Supplement Safety Advisor - Streamlit App
Personalized supplement recommendations using knowledge graphs
"""
import os
import sys
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

project_root = Path(__file__).parent.parent  # points to src/
sys.path.insert(0, str(project_root))

from workflow.graph_builder import build_workflow, run_workflow
from graph.graph_interface import GraphInterface

# Load environment
load_dotenv()

# Page config
st.set_page_config(
    page_title="Supplement Safety Advisor",
    page_icon="💊",
    layout="centered"
)


# ======================================================================
# Initialization
# ======================================================================

@st.cache_resource
def initialize_system():
    """Initialize the knowledge graph and workflow agent."""
    neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password = os.getenv("NEO4J_PASSWORD")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")

    if not neo4j_password or not anthropic_key:
        st.error("⚠️ Missing credentials in .env file")
        st.info("Please set NEO4J_PASSWORD and ANTHROPIC_API_KEY")
        st.stop()

    try:
        graph = GraphInterface(neo4j_uri, neo4j_user, neo4j_password)
        workflow = build_workflow()
        return workflow, graph
    except Exception as e:
        st.error(f"Failed to connect to database: {e}")
        st.stop()


# ======================================================================
# State → Display translation
# ======================================================================

def translate_result(state: dict) -> dict:
    """
    Translate raw LangGraph state into the flat dict that the UI expects.

    LangGraph state keys         →  UI display keys
    ─────────────────────────────────────────────────
    final_answer                 →  answer
    supervisor_decision (+ LLM)  →  question_type
    extracted_entities           →  entities
    query_history                →  cypher_query, results_count
    safety_results               →  raw_results
    error_message                →  error
    """
    answer = state.get('final_answer') or state.get('error_message') or 'No answer generated.'

    # --- question type ---
    if state.get('recommendations_checked'):
        q_type = 'recommendations'
    elif state.get('safety_checked'):
        q_type = 'safety'
    elif state.get('deficiency_checked'):
        q_type = 'deficiency'
    else:
        q_type = 'general'

    # --- entities ---
    entities = state.get('extracted_entities') or {}

    # --- cypher query (show the last query that was run) ---
    cypher_query = None
    results_count = 0
    raw_results = None

    # Pull cypher from safety_results if available (most detailed)
    safety = state.get('safety_results') or {}
    queries_run = safety.get('queries_run', [])
    if queries_run:
        cypher_query = queries_run[0].get('cypher', '')
        results_count += len(safety.get('interactions', []))
        if safety.get('interactions'):
            raw_results = safety['interactions'][:10]

    # Pull from recommendation_results
    recommendations = state.get('recommendation_results') or {}
    if recommendations.get('recommendations'):
        results_count += len(recommendations['recommendations'])
        if not cypher_query:
            cypher_query = """MATCH (s:Supplement)-[:TREATS]->(sym:Symptom)
WHERE toLower(sym.symptom_name) CONTAINS $condition
RETURN s.supplement_name, sym.symptom_name"""
        if not raw_results:
            raw_results = recommendations['recommendations'][:10]

    # Pull from deficiency_results
    deficiency = state.get('deficiency_results') or {}
    deficiency_queries = deficiency.get('queries_run', [])
    if deficiency_queries and not cypher_query:  # Only if safety didn't already set it
        cypher_query = deficiency_queries[0].get('cypher', '')
        results_count += deficiency.get('total_count', 0)
        if not raw_results:
            # Combine diet_based and supplement_based for display
            diet_def = deficiency.get('diet_based', [])
            supp_def = deficiency.get('supplement_based', [])
            combined_def = diet_def + supp_def
            if combined_def:
                raw_results = combined_def[:10]

    # Fallback to query_history
    if results_count == 0:
        query_history = state.get('query_history', [])
        if query_history:
            results_count = sum(q.get('result_count', 0) for q in query_history)

    return {
        'answer': answer,
        'question_type': q_type,
        'entities': entities,
        'cypher_query': cypher_query,
        'results_count': results_count,
        'raw_results': raw_results,
        'error': state.get('error_message'),
        'confidence': state.get('confidence_level', 0),
        'evidence_chain': state.get('evidence_chain', []),
        'safety_results': safety,
        'iterations': state.get('iterations', 0),
    }


# ======================================================================
# Display helpers
# ======================================================================

def display_answer(result: dict):
    """Display the answer with appropriate formatting."""
    answer = result.get('answer', '')
    question_type = result.get('question_type', '')

    has_warning = any(
        kw in answer.lower()
        for kw in ['warning', 'caution', 'critical', 'risk', 'avoid', 'dangerous']
    )

    if has_warning:
        st.error("⚠️ SAFETY ALERT")
        st.warning(
            "This response contains important safety information. "
            "Please consult with your healthcare provider before making any changes."
        )

    st.markdown("### Answer:")

    if question_type == 'comparison':
        st.info(answer)
    elif has_warning:
        st.warning(answer)
    else:
        st.info(answer)


def display_debug_panel(result: dict):
    """Show technical details in an expander."""
    with st.expander("🔍 How this answer was generated"):
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**Query Classification**")
            st.write(f"Type: `{result.get('question_type', 'Unknown')}`")

            st.markdown("**Entities Extracted**")
            entities = result.get('entities', {})
            supps = entities.get('supplements', [])
            meds = entities.get('medications', [])
            diets = entities.get('dietary_restrictions', [])
            if supps:
                st.write(f"• Supplements: {', '.join(supps)}")
            if meds:
                st.write(f"• Medications: {', '.join(meds)}")
            if diets:
                st.write(f"• Dietary Restrictions: {', '.join(diets)}")
            if not supps and not meds and not diets:
                st.write("• None extracted from question")

        with col2:
            st.markdown("**Results Found**")
            st.write(f"{result.get('results_count', 0)} records")

            confidence = result.get('confidence', 0)
            if confidence:
                st.write(f"Confidence: {confidence:.0%}")

            st.write(f"Iterations: {result.get('iterations', 0)}")

            if result.get('error'):
                st.error(f"Error: {result['error']}")

        # Evidence chain
        evidence = result.get('evidence_chain', [])
        if evidence:
            st.markdown("**Evidence Chain**")
            for step in evidence:
                st.write(f"→ {step}")

        # Cypher query
        if result.get('cypher_query'):
            st.markdown("**Database Query (Cypher)**")
            st.code(result['cypher_query'], language='cypher')
        else:
            st.markdown("**Database Query**")
            st.write("Used LLM reasoning (no database query)")

        # Raw results
        if result.get('raw_results'):
            st.markdown("**Sample Database Results**")
            st.json(result['raw_results'])


# ======================================================================
# Main
# ======================================================================

def main():
    st.title("💊 Supplement Safety Advisor")
    st.caption("Evidence-based supplement safety using knowledge graphs")

    # Initialize
    workflow, graph = initialize_system()

    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = []

    # ------------------------------------------------------------------
    # Sidebar
    # ------------------------------------------------------------------
    with st.sidebar:
        st.header("Your Health Profile")
        st.caption("This information helps detect dangerous interactions")

        medications = st.text_area(
            "💊 Medications",
            placeholder="Warfarin, Metformin, Atorvastatin...",
            help="Enter prescription medications (comma-separated)",
            height=80,
        )

        supplements = st.text_area(
            "🌿 Current Supplements",
            placeholder="Fish Oil, Vitamin D, St. John's Wort...",
            help="Supplements you're already taking",
            height=60,
        )

        conditions = st.multiselect(
            "🏥 Medical Conditions",
            [
                "High Blood Pressure", "High Cholesterol",
                "Type 2 Diabetes", "Heart Disease",
                "Blood Clotting Disorder", "Kidney Disease",
                "Liver Disease", "Osteoporosis",
            ],
        )

        diet = st.multiselect(
            "🥗 Dietary Restrictions",
            ["Vegan", "Vegetarian", "Pescatarian", "Keto", "Gluten-Free", "Dairy-Free"],
        )

        st.divider()

        with st.expander("📊 Database Info"):
            try:
                stats_query = """
                MATCH (s:Supplement) WITH count(s) as supplements
                MATCH (m:Medication) WITH supplements, count(m) as medications
                MATCH (d:Drug) WITH supplements, medications, count(d) as drugs
                RETURN supplements, medications, drugs
                """
                stats = graph.execute_query(stats_query)
                if stats:
                    st.metric("Supplements", stats[0]['supplements'])
                    st.metric("Medications", stats[0]['medications'])
                    st.metric("Drugs (DrugBank)", stats[0]['drugs'])
            except Exception:
                st.caption("Stats unavailable")

        st.divider()
        st.caption("⚠️ Educational tool only. Always consult healthcare providers.")

    # ------------------------------------------------------------------
    # Main content
    # ------------------------------------------------------------------
    st.subheader("Ask About Supplement Safety")

    with st.expander("💡 Example Questions", expanded=False):
        st.markdown("**Safety Checks:**")
        st.markdown("- Is it safe to take fish oil with warfarin?")
        st.markdown("- Can I take Red Yeast Rice with my statin medication?")
        st.markdown("- Are there interactions between ginkgo and my medications?")

        st.markdown("**Comparisons:**")
        st.markdown("- Magnesium vs Melatonin for sleep")
        st.markdown("- Fish oil vs flaxseed oil for heart health")

        st.markdown("**Recommendations:**")
        st.markdown("- What supplements help with high blood pressure?")
        st.markdown("- Which supplements support heart health?")

        st.markdown("**General Questions:**")
        st.markdown("- What is CoQ10 good for?")
        st.markdown("- How does St. John's Wort work?")

    # Question input
    col1, col2 = st.columns([4, 1])
    with col1:
        question = st.text_input(
            "Your question:",
            placeholder="e.g., Can I take...",
            label_visibility="collapsed",
        )
    with col2:
        ask_button = st.button("Ask", type="primary", use_container_width=True)

    # ------------------------------------------------------------------
    # Process question
    # ------------------------------------------------------------------
    if ask_button and question:
        # Build profile from sidebar inputs
        profile = {}

        if medications:
            meds = [m.strip() for m in medications.split(',') if m.strip()]
            if meds:
                profile['medications'] = meds

        if supplements:
            supps = [s.strip() for s in supplements.split(',') if s.strip()]
            if supps:
                profile['supplements'] = supps

        if conditions:
            profile['conditions'] = conditions

        if diet:
            profile['dietary_restrictions'] = diet

        with st.spinner("🔍 Analyzing knowledge graph..."):
            try:
                # Run the LangGraph workflow
                raw_state = run_workflow(
                    workflow,
                    question,
                    profile if profile else {},
                    graph_interface=graph,      # ← passes graph to state
                )

                # Translate LangGraph state → UI display dict
                result = translate_result(raw_state)

            except Exception as e:
                st.error(f"Error: {str(e)}")
                st.info("Please try rephrasing your question or check your database connection.")
                import traceback
                with st.expander("Error details"):
                    st.code(traceback.format_exc())
                return

        # Display
        display_answer(result)
        display_debug_panel(result)

        # Add to history
        st.session_state.chat_history.append({
            'question': question,
            'answer': result['answer'],
            'question_type': result.get('question_type', 'unknown'),
            'has_warning': any(
                kw in result['answer'].lower()
                for kw in ['warning', 'risk', 'caution', 'dangerous']
            ),
        })

    # ------------------------------------------------------------------
    # Chat history
    # ------------------------------------------------------------------
    if st.session_state.chat_history:
        st.divider()
        st.subheader("Recent Questions")

        for item in reversed(st.session_state.chat_history[-3:]):
            if item.get('has_warning'):
                icon = "⚠️"
            elif item.get('question_type') == 'comparison':
                icon = "⚖️"
            elif item.get('question_type') == 'recommendation':
                icon = "💡"
            else:
                icon = "💬"

            with st.expander(f"{icon} {item['question'][:60]}..."):
                st.write(item['answer'])

        if st.button("Clear History"):
            st.session_state.chat_history = []
            st.rerun()

    # Footer
    st.divider()
    st.caption(
        "This tool uses DrugBank and Mayo Clinic data to identify supplement-drug interactions. "
        "Always verify recommendations with healthcare professionals."
    )


if __name__ == "__main__":
    main()
