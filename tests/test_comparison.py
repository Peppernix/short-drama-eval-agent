from drama_eval.comparison import compare_with_human


def test_compare_with_human():
    machine = {
        "scores": {
            "plot_fidelity": {"score": 3},
            "instruction_following": {"score": 5},
            "character_consistency": {"score": 4},
        },
        "final_decision": "revise",
    }
    gold = {
        "sample_id": "sample_001",
        "human_answer": {
            "scores": {
                "plot_fidelity": {"score": 4},
                "instruction_following": {"score": 5},
                "character_consistency": {"score": 2},
            },
            "final_decision": "revise",
        },
    }

    result = compare_with_human(machine, gold)

    assert result["sample_id"] == "sample_001"
    assert result["mean_absolute_error"] == 1
    assert result["exact_score_rate"] == 1 / 3
    assert result["within_one_point_rate"] == 2 / 3
    assert result["decision_match"] is True
