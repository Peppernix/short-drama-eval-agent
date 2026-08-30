import json

from drama_eval.evaluator import extract_json
from drama_eval.rubric import RUBRIC


def test_rubric_has_required_dimensions():
    for name in ["plot_fidelity", "instruction_following", "character_consistency", "shot_fidelity", "visual_quality"]:
        assert name in RUBRIC


def test_extract_json_from_fence():
    result = extract_json('```json\n{"final_decision":"pass"}\n```')
    assert result == {"final_decision": "pass"}
    json.dumps(result)
