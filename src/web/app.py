"""
Supplement Safety Advisor - Streamlit App
Personalized supplement recommendations using knowledge graphs
"""
import os
import sys
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

# Add src directory to path
src_dir = Path(__file__).parent.parent
sys.path.append(str(src_dir))

from agents.graph_interface import GraphInterface
from agents.workflow_agent import WorkflowAgent

# Load environment
load_dotenv()

# Page config
st.set_page_config(
    page_title="Supplement Safety Advisor",
    page_icon="💊",
    layout="centered"
)

@st.cache_resource
def initialize_system():
    """Initialize the knowledge graph and agent"""
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
        agent = WorkflowAgent(graph, anthropic_key)
        return agent, graph
    except Exception as e:
        st.error(f"Failed to connect to database: {e}")
        st.stop()

def format_profile_context(medications, supplements, conditions, diet):
    """Format user profile into context string"""
    context_parts = []
    
    if medications:
        meds = [m.strip() for m in medications.split(',') if m.strip()]
        if meds:
            context_parts.append(f"Taking medications: {', '.join(meds)}")
    
    if supplements:
        supps = [s.strip() for s in supplements.split(',') if s.strip()]
        if supps:
            context_parts.append(f"Current supplements: {', '.join(supps)}")
    
    if conditions:
        context_parts.append(f"Medical conditions: {', '.join(conditions)}")
    
    if diet:
        context_parts.append(f"Diet: {', '.join(diet)}")
    
    return " | ".join(context_parts) if context_parts else ""

def display_safety_warning(result):
    """Display safety warnings prominently"""
    # Check for dangerous interactions in the answer
    answer = result.get('answer', '').lower()
    
    # Look for warning keywords
    warning_keywords = ['warning', 'caution', 'avoid', 'dangerous', 'risk', 'interaction']
    has_warning = any(keyword in answer for keyword in warning_keywords)
    
    if has_warning:
        st.error("⚠️ SAFETY ALERT")
        st.warning(
            "This response contains important safety information. "
            "Please consult with your healthcare provider before making any changes."
        )

def main():
    # Header
    st.title("💊 Supplement Safety Advisor")
    st.caption("Evidence-based supplement safety using knowledge graphs")
    
    # Initialize system
    agent, graph = initialize_system()
    
    # Initialize session state
    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = []
    
    # Sidebar - Health Profile
    with st.sidebar:
        st.header("Your Health Profile")
        st.caption("This information helps detect dangerous interactions")
        
        medications = st.text_area(
            "💊 Medications",
            placeholder="Warfarin, Metformin, Atorvastatin...",
            help="Enter prescription medications (comma-separated)",
            height=80
        )
        
        supplements = st.text_area(
            "🌿 Current Supplements",
            placeholder="Fish Oil, Vitamin D, St. John's Wort...",
            help="Supplements you're already taking",
            height=60
        )
        
        conditions = st.multiselect(
            "🏥 Medical Conditions",
            [
                "High Blood Pressure",
                "High Cholesterol", 
                "Type 2 Diabetes",
                "Heart Disease",
                "Blood Clotting Disorder",
                "Kidney Disease",
                "Liver Disease",
                "Osteoporosis"
            ]
        )
        
        diet = st.multiselect(
            "🥗 Dietary Restrictions",
            ["Vegan", "Vegetarian", "Pescatarian", "Keto", "Gluten-Free", "Dairy-Free"]
        )
        
        st.divider()
        
        # Quick stats from database
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
            except:
                st.caption("Stats unavailable")
        
        st.divider()
        st.caption("⚠️ Educational tool only. Always consult healthcare providers.")
    
    # Main content
    st.subheader("Ask About Supplement Safety")
    
    # Example questions organized by type
    with st.expander("💡 Example Questions", expanded=False):
        st.markdown("**Safety Checks:**")
        st.markdown("- Is it safe to take fish oil with warfarin?")
        st.markdown("- Can I take Red Yeast Rice with my statin medication?")
        st.markdown("- Are there interactions between ginkgo and my medications?")
        
        st.markdown("**Deficiency Detection:**")
        st.markdown("- What nutrients might I be deficient in?")
        st.markdown("- I'm vegan and take metformin - what should I supplement?")
        
        st.markdown("**Recommendations:**")
        st.markdown("- Which supplements support heart health?")
        st.markdown("- What supplements help with high blood pressure?")
        
        st.markdown("**Comparisons:**")
        st.markdown("- What's better for heart health: fish oil or plant-based omega-3?")
        st.markdown("- Should I take magnesium glycinate or melatonin for sleep?")
    
    # Question input
    col1, col2 = st.columns([4, 1])
    
    with col1:
        question = st.text_input(
            "Your question:",
            placeholder="e.g., Is it safe to take...",
            label_visibility="collapsed"
        )
    
    with col2:
        ask_button = st.button("Ask", type="primary", use_container_width=True)
    
    # Process question
    if ask_button and question:
        # Build context
        profile_context = format_profile_context(medications, supplements, conditions, diet)
        
        # Enhance question with context
        if profile_context:
            full_question = f"{question}\n\nContext: {profile_context}"
        else:
            full_question = question
        
        # Get answer from agent
        with st.spinner("🔍 Analyzing knowledge graph..."):
            try:
                result = agent.answer_question(full_question)
            except Exception as e:
                st.error(f"Error: {str(e)}")
                return
        
        # Display safety warnings first
        display_safety_warning(result)
        
        # Display answer
        st.markdown("### Answer:")
        st.info(result['answer'])
        
        # Show technical details
        with st.expander("🔍 How this answer was generated"):
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**Query Classification**")
                st.write(result.get('question_type', 'Unknown'))
                
                st.markdown("**Entities Extracted**")
                entities = result.get('entities', [])
                if entities:
                    for entity in entities:
                        st.write(f"• {entity}")
                else:
                    st.write("None extracted")
            
            with col2:
                st.markdown("**Results Found**")
                st.write(f"{result.get('results_count', 0)} records")
                
                if result.get('error'):
                    st.error(f"Error: {result['error']}")
            
            # Show Cypher query
            if result.get('cypher_query'):
                st.markdown("**Database Query (Cypher)**")
                st.code(result['cypher_query'], language='cypher')
            
            # Show sample results
            if result.get('raw_results'):
                st.markdown("**Sample Database Results**")
                st.json(result['raw_results'])
        
        # Add to history
        st.session_state.chat_history.append({
            'question': question,
            'answer': result['answer'],
            'has_warning': 'warning' in result['answer'].lower()
        })
    
    # Show recent history
    if st.session_state.chat_history:
        st.divider()
        st.subheader("Recent Questions")
        
        # Show last 3 questions
        for i, item in enumerate(reversed(st.session_state.chat_history[-3:])):
            icon = "⚠️" if item.get('has_warning') else "💬"
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