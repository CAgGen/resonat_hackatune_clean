"""编排 · 薄重排。音频/语义相似分始终主导，标签软目标只做轻微调序。

# ponytail: soft/neg 标签项在标签批量拉取落地前先记 0，护栏才是真正的检查
"""
from __future__ import annotations

import config


def thin_rerank(cards: list[dict],
                w_primary: float = config.W_PRIMARY,
                w_soft: float = config.W_SOFT,
                w_neg: float = config.W_NEG) -> list[dict]:
    assert w_primary > w_soft + w_neg, "护栏: primary 必须主导 (W_PRIMARY > W_SOFT + W_NEG)"

    def score(c: dict) -> float:
        # primary = 卡片的主信号分；soft/neg 暂为 0，留给标签打分接入
        return w_primary * (c.get("score") or 0.0)

    return sorted(cards, key=score, reverse=True)
