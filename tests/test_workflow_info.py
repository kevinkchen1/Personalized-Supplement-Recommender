import sys
import pathlib

sys.path.insert(0, str(pathlib.Path('.').resolve() / 'src'))

from workflow.graph_builder import build_workflow, get_workflow_info


def test_get_workflow_info_contains_nodes():
    workflow = build_workflow()
    info = get_workflow_info(workflow)

    assert 'supervisor' in info['nodes']
    assert 'synthesis' in info['nodes']
    assert info['entry_point'] is not None
    assert isinstance(info['end_nodes'], list)
