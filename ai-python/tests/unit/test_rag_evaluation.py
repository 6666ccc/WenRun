import math

from app.rag.evaluation import (
    hit_at_k,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
    summarize_retrieval,
)


def test_retrieval_metrics_match_the_guide_example():
    relevant = ["a", "b", "c"]
    retrieved = ["x", "a", "y", "b", "z"]

    assert recall_at_k(relevant, retrieved, 5) == 2 / 3
    assert precision_at_k(relevant, retrieved, 5) == 2 / 5
    assert hit_at_k(relevant, retrieved, 5) == 1
    assert reciprocal_rank(relevant, retrieved) == 0.5


def test_ndcg_rewards_relevant_results_near_the_top():
    perfect = ndcg_at_k({"a": 2, "b": 1}, ["a", "b", "c"], 3)
    reversed_ranking = ndcg_at_k({"a": 2, "b": 1}, ["b", "a", "c"], 3)

    assert perfect == 1
    assert reversed_ranking < perfect


def test_summary_averages_recall_and_mrr():
    summary = summarize_retrieval(
        [
            {
                "relevant_chunk_ids": ["a", "b", "c"],
                "retrieved_chunk_ids": ["x", "a", "y", "b", "z"],
            },
            {
                "relevant_chunk_ids": ["only"],
                "retrieved_chunk_ids": ["only"],
            },
        ]
    )

    assert summary["count"] == 2
    assert math.isclose(summary["recall@5"], (2 / 3 + 1) / 2)
    assert math.isclose(summary["mrr"], (0.5 + 1) / 2)
    assert summary["hit@5"] == 1
