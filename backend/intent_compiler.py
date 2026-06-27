"""接缝 · 意图编译（队友负责：LLM + prompt）。

═══════════════════════════════════════════════════════════════════
  这个文件归同伴。编排层只依赖下面这一个函数签名，别的随你换。
  你要做的：把白板便签 + 用户记忆画像，编译成一张 Query Card。
═══════════════════════════════════════════════════════════════════

契约（编排层依赖，不要改签名）:
    compile_query_card(posts, profile_md) -> dict

  入参:
    posts:      白板便签列表，按时间顺序。每项 {"role","text", ...}
                role ∈ {"initial_prompt", "follow_up"}
    profile_md: 该用户 memory.md 的自然语言画像（可能为空字符串）。
                PRD ⑧：把它注进系统 prompt，让 Query Card 自带"你的声音"。

  返回 Query Card dict（字段名固定，前端/编排都按它来）:
    {
      "interpretation_plain": str,        # 一句大白话"我把你的需求理解成…"
      "free_text_query":      str,        # 打进 freeTextSearch 的英文查询
      "soft_targets": [{"dim","value","weight"}],  # 软目标，无则 []
      "negatives":    [{"dim","value"}],           # 负向，只扣分不剔除，无则 []
    }

下面是离线占位实现：把便签文本拼起来。能让编排端到端跑通，
但没有真正的语义理解——你用 LLM 替换函数体即可，签名保持不变。
"""
from __future__ import annotations


def compile_query_card(posts: list[dict], profile_md: str = "") -> dict:
    # TODO(partner): 换成 LLM 调用 + prompt。profile_md 注入系统 prompt。
    texts = [p["text"].strip() for p in posts if p.get("text", "").strip()]
    query = " ".join(texts)
    return {
        "interpretation_plain": f"我把你的需求理解成：{query}",
        "free_text_query": query,
        "soft_targets": [],
        "negatives": [],
    }
