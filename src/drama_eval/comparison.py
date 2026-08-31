from __future__ import annotations

from typing import Any, Dict, Iterable


def compare_with_human(machine: Dict[str, Any], gold: Dict[str, Any]) -> Dict[str, Any]:
    """比较机评与人工黄金答案，返回逐维度误差与汇总指标。"""
    human_answer = gold.get("human_answer", gold)
    machine_scores = machine.get("scores", {})
    human_scores = human_answer.get("scores", {})
    dimensions: Iterable[str] = sorted(set(machine_scores) & set(human_scores))

    details: Dict[str, Any] = {}
    absolute_errors = []
    exact_matches = 0
    within_one = 0

    for dimension in dimensions:
        machine_score = float(machine_scores[dimension]["score"])
        human_score = float(human_scores[dimension]["score"])
        error = abs(machine_score - human_score)
        absolute_errors.append(error)
        exact_matches += int(error == 0)
        within_one += int(error <= 1)
        details[dimension] = {
            "human_score": human_score,
            "machine_score": machine_score,
            "absolute_error": error,
            "within_one_point": error <= 1,
        }

    count = len(details)
    human_decision = human_answer.get("final_decision")
    machine_decision = machine.get("final_decision")
    return {
        "sample_id": gold.get("sample_id"),
        "dimension_count": count,
        "mean_absolute_error": sum(absolute_errors) / count if count else None,
        "exact_score_rate": exact_matches / count if count else None,
        "within_one_point_rate": within_one / count if count else None,
        "decision_match": (
            machine_decision == human_decision
            if machine_decision is not None and human_decision is not None
            else None
        ),
        "human_decision": human_decision,
        "machine_decision": machine_decision,
        "details": details,
    }
