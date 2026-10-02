"""检索层指标。只比较标注的片段编号和实际返回顺序，不调用模型。

Recall@k、Precision@k、Hit Rate@k、MRR、nDCG@k 的定义与
《企业级 RAG 知识库与检索评估指南》一致。有标注集之后，用同一份数据
对比切分或检索改动；在此之前不要凭这些函数改线上检索参数。
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence

Case = Mapping[str, Sequence[str]]


def recall_at_k(relevant: Sequence[str], retrieved: Sequence[str], k: int) -> float:
    """相关片段里，前 k 条找到了多少。"""

    truth = _truth(relevant)
    if not truth:
        return 0.0
    return len(truth.intersection(retrieved[:_k(k)])) / len(truth)


def precision_at_k(relevant: Sequence[str], retrieved: Sequence[str], k: int) -> float:
    """前 k 个位置里，真正相关的比例。不足 k 条时仍除以 k。"""

    limit = _k(k)
    truth = _truth(relevant)
    hits = sum(1 for item in retrieved[:limit] if item in truth)
    return hits / limit


def hit_at_k(relevant: Sequence[str], retrieved: Sequence[str], k: int) -> float:
    """前 k 条里是否至少有一条相关结果。"""

    truth = _truth(relevant)
    return 1.0 if any(item in truth for item in retrieved[:_k(k)]) else 0.0


def reciprocal_rank(relevant: Sequence[str], retrieved: Sequence[str]) -> float:
    """第一条相关结果排名的倒数；没有相关结果时为 0。"""

    truth = _truth(relevant)
    for index, item in enumerate(retrieved, start=1):
        if item in truth:
            return 1.0 / index
    return 0.0


def ndcg_at_k(
    relevant: Mapping[str, float] | Sequence[str],
    retrieved: Sequence[str],
    k: int,
) -> float:
    """越相关的结果越靠前，分数越接近 1。序列形式按二元相关处理。"""

    limit = _k(k)
    grades = _grades(relevant)
    ranking = list(retrieved[:limit])
    dcg = _dcg(grades.get(item, 0.0) for item in ranking)
    ideal = sorted((grade for grade in grades.values() if grade > 0), reverse=True)[:limit]
    idcg = _dcg(ideal)
    if idcg == 0:
        return 0.0
    return dcg / idcg


def summarize_retrieval(
    cases: Sequence[Case],
    *,
    ks: Sequence[int] = (5, 10),
) -> dict[str, float | int]:
    """对多道题取平均。每题需要 relevant_chunk_ids 和 retrieved_chunk_ids。"""

    if not cases:
        raise ValueError("cases must not be empty")
    totals: dict[str, float] = {}
    for case in cases:
        relevant = list(case.get("relevant_chunk_ids") or [])
        retrieved = list(case.get("retrieved_chunk_ids") or [])
        totals["mrr"] = totals.get("mrr", 0.0) + reciprocal_rank(relevant, retrieved)
        for k in ks:
            totals[f"recall@{k}"] = totals.get(f"recall@{k}", 0.0) + recall_at_k(
                relevant, retrieved, k
            )
            totals[f"precision@{k}"] = totals.get(f"precision@{k}", 0.0) + precision_at_k(
                relevant, retrieved, k
            )
            totals[f"hit@{k}"] = totals.get(f"hit@{k}", 0.0) + hit_at_k(
                relevant, retrieved, k
            )
    count = len(cases)
    summary: dict[str, float | int] = {"count": count}
    summary.update({key: value / count for key, value in totals.items()})
    return summary


def _k(k: int) -> int:
    if k < 1:
        raise ValueError("k must be positive")
    return k


def _truth(relevant: Sequence[str]) -> set[str]:
    return {item for item in relevant if item}


def _grades(relevant: Mapping[str, float] | Sequence[str]) -> dict[str, float]:
    if isinstance(relevant, Mapping):
        return {str(key): float(value) for key, value in relevant.items()}
    return {str(item): 1.0 for item in relevant}


def _dcg(grades: Iterable[float]) -> float:
    score = 0.0
    for index, grade in enumerate(grades, start=1):
        if grade:
            score += float(grade) / math.log2(index + 1)
    return score
