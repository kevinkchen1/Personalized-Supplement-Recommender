"""
Mock Run Example

Builds a tiny StateGraph using the same `ConversationState` and runs a
mocked end-to-end workflow where agents are simple functions that update
the state without external dependencies. This is useful for local testing
and CI where Anthropic or Neo4j are not available.
"""
from langgraph.graph import StateGraph, END
from workflow.state import ConversationState, create_initial_state


def _supervisor(state):
    # Simple supervisor: if entities not extracted, go extract; otherwise synthesize
    if not state.get('entities_extracted'):
        state['supervisor_decision'] = 'extract'
    else:
        state['supervisor_decision'] = 'synthesize'
    return state


def _extractor(state):
    # Fake extraction
    state['extracted_entities'] = {'supplements': ['Fish Oil'], 'medications': ['Warfarin']}
    state['entities_extracted'] = True
    return state


def _safety(state):
    # Fake safety check
    state['safety_checked'] = True
    state['safety_results'] = {'safe': False, 'interactions': ['Fish Oil + Warfarin → increased bleeding'], 'confidence': 0.8}
    state['confidence_level'] = 0.8
    return state


def _synthesis(state):
    # Combine findings into final answer
    safety = state.get('safety_results', {})
    if safety and not safety.get('safe', True):
        state['final_answer'] = "Caution: Fish Oil may increase bleeding with Warfarin. Consult your provider."
    else:
        state['final_answer'] = "No interactions found."
    return state


def run_mock_workflow(question: str, profile: dict):
    graph = StateGraph(ConversationState)

    graph.add_node('supervisor', _supervisor)
    graph.add_node('extract', _extractor)
    graph.add_node('safety', _safety)
    graph.add_node('synthesis', _synthesis)

    # Edges: supervisor -> extract OR supervisor -> synthesis
    graph.add_conditional_edges('supervisor', lambda s: s.get('supervisor_decision', 'extract'), {
        'extract': 'extract',
        'synthesize': 'synthesis',
        'safety': 'safety',
        'supervisor': 'supervisor',
        'END': END
    })

    # extraction -> safety -> supervisor
    graph.add_edge('extract', 'safety')
    graph.add_edge('safety', 'supervisor')
    graph.add_edge('synthesis', END)

    graph.set_entry_point('supervisor')
    compiled = graph.compile()

    state = create_initial_state(question, profile)
    final = compiled.invoke(state)
    return final


if __name__ == '__main__':
    result = run_mock_workflow('Is Fish Oil safe with my Warfarin?', {'medications': [{'drug_name': 'Warfarin'}]})
    print('Final answer:', result.get('final_answer'))
