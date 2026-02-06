import sys
import pathlib

sys.path.insert(0, str(pathlib.Path('.').resolve() / 'src'))

from workflow.routing import (
    route_supervisor_decision,
    route_with_safety_check,
    route_based_on_confidence,
    NodeNames,
)


def test_route_supervisor_decision_mappings():
    assert route_supervisor_decision({'supervisor_decision': 'check_safety'}) == NodeNames.SAFETY_CHECK
    assert route_supervisor_decision({'supervisor_decision': 'check_deficiency'}) == NodeNames.DEFICIENCY_CHECK
    assert route_supervisor_decision({'supervisor_decision': 'check_recommendations'}) == NodeNames.RECOMMENDATION
    assert route_supervisor_decision({'supervisor_decision': 'finish'}) == NodeNames.SYNTHESIS


def test_route_with_safety_check_handles_errors_and_max_iter():
    # Error state routes to synthesis
    assert route_with_safety_check({'error_message': 'oops'}) == NodeNames.SYNTHESIS

    # Max iterations routes to synthesis
    assert route_with_safety_check({'iterations': 10}) == NodeNames.SYNTHESIS


def test_route_based_on_confidence_loops_or_synthesizes():
    # Low confidence and few iterations -> loop back to supervisor
    assert route_based_on_confidence({'confidence_level': 0.3, 'iterations': 1, 'supervisor_decision': 'check_safety'}) == NodeNames.SUPERVISOR

    # Enough iterations triggers synthesis
    assert route_based_on_confidence({'confidence_level': 0.4, 'iterations': 5, 'supervisor_decision': 'check_safety'}) == NodeNames.SYNTHESIS
