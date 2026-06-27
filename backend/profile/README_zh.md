# `backend/profile` — 用户口味记忆（User-defined Taste Memory）

Cochlea 的**用户画像**模块。把听者的反馈（like / dislike / skip / 自由文字 note）
变成**可解释、按用户存储的口味记忆**（Markdown 格式），并供后端其余部分使用。

对应 PRD §7（双消费者记忆）与 `/feedback`、`/your-sound` 端点。记忆只从 **like**
（正向信号）构建；dislike/skip 会压低亲和度；note 原样保存。每条偏好都能追溯到真实
的 Cyanite 标签——**不用 opaque latent 向量**，所以始终可解释。

---

## 目录结构

```
backend/profile/
  api.py           FastAPI 路由（router + 可独立运行的 app）
  mdmemory.py      核心：record_feedback() + 两文件 md 存储 + 读视图 + 新颖度门
  salience.py      标签辨识度（IDF）——决定“值不值得记”
  cyanite_tags.py  极简 Cyanite 标签客户端（磁盘缓存 + 限流）
  tags.py          把原始 model outputs 归一成扁平 tags
  data.py          数据包 id 映射 + 音频 url（demo/种子/评估用）
  config.py        环境 / 路径（读仓库根 .env）
  visualize.py     把用户记忆渲染成“口味卡片”PNG
  tag_base_rates.json  目录标签基率（IDF 用，仅聚合频率）
  test_feedback.py / experiment_novelty.py / evaluate.py / faithfulness.py
  memory/          每用户的记忆文件（运行时；git 忽略）：
                     <uid>.evidence.md  仅追加的原始真相（种子池）
                     <uid>.memory.md    自然语言画像（→ /intent）
                     <uid>.state.json   内部引擎缓存（派生）
  .cache/          缓存的 Cyanite 标签（运行时；git 忽略）
```

## 运行

```bash
# 在仓库根目录，使用 hackatune conda 环境
uvicorn backend.profile.api:app --reload --port 8001   # 文档在 /docs

# 或跑模拟反馈 demo
python -m backend.profile.test_feedback
```

需要仓库根 `.env` 里有 `CYANITE_API_KEY`。没有 key 时进入 **MOCK** 模式（确定性
假标签），保证离线可测。

---

## 唯一接口

```python
from backend.profile import mdmemory

mdmemory.record_feedback(
    user_id, track_id, verdict,      # verdict: like | dislike | skip | play | note
    prompt=None,                     # 该曲来自哪个搜索/Query
    note=None,                       # 用户的自由文字“其他信息”
    track_tags=None,                 # 可选；不传则从 Cyanite 拉取（缓存）
) -> summary_dict
```

读视图：

```python
mdmemory.summary(user_id)               # headline + 结构化偏好（给 /your-sound）
mdmemory.seed_pool(user_id, prompt=...) # 喜欢曲目 id → similarById 种子池
mdmemory.prompt_injection(user_id)      # 注入 /intent 系统 prompt 的口味文字块
```

## HTTP 端点

| 方法 | 路径 | 作用 | 消费者 |
|---|---|---|---|
| POST | `/feedback` | 记一条 like/dislike/skip/note → 更新后摘要 | `/feedback` 循环 |
| POST | `/feedback/batch` | 记一串事件 | 回放 / 批量 |
| GET | `/your-sound/{user_id}` | 记忆摘要 | `GET /your-sound` |
| GET | `/profile/{user_id}/seeds?prompt=&limit=` | 喜欢曲目种子池 | 检索侧 |
| GET | `/profile/{user_id}/injection` | 系统 prompt 口味块（memory.md 正文）| `/intent` |
| GET | `/profile/{user_id}/memory` | 自然语言画像（memory.md）| demo / `/intent` |
| GET | `/profile/{user_id}/evidence` | 仅追加原始日志（evidence.md）| demo |
| GET | `/profile/{user_id}/card.png` | 渲染好的“口味卡片”图 | demo / 前端 |
| GET | `/health` | `{ok, mock}` | — |

## 集成方式（两种）

```python
# 1) 在主 app 挂载 router（推荐）
from backend.profile.api import router as profile_router
main_app.include_router(profile_router)

# 2) 或在自己的 /feedback 处理里直接调函数
from backend.profile import mdmemory
mdmemory.record_feedback(uid, tid, "like", prompt=prompt)   # 持久化 like
seeds = mdmemory.seed_pool(uid, prompt=prompt)              # 给 similarById
inject = mdmemory.prompt_injection(uid)                     # 给 /intent
```

> ⚠️ PRD 里的 `POST /feedback` 还要做邻域**剪枝/回填/重排**（检索侧，另一位队友负责）。
> 本模块只负责**记忆持久化**。二选一：让主 `/feedback` 内部调 `record_feedback()`，
> 或用集成方式 (2)——避免两人都注册同一个 `POST /feedback`。

## 存储格式（PRD-night：两个 markdown 文件，无数据库）

每个用户在 `memory/` 下：

- **`<uid>.evidence.md`** —— 仅追加的原始真相。每条反馈一行
  （`- 👍 like · \`libtr_…\` · 「prompt」 · ts`），**从不修改旧行**。同时充当
  similarById 的**种子池**和画像依据。
- **`<uid>.memory.md`** —— 自然语言口味画像，每次更新**整段重写**（有
  `ANTHROPIC_API_KEY` 用 LLM，否则用确定性规则版段落）+ 一个有据可查的 “Facts” 块。
  `/intent` **原样**注入它。
- **`<uid>.state.json`** —— 内部引擎缓存（亲和度、锚点、IDF、场景），可由 evidence
  重放重建，**不属于对外契约**。

完全贴合 PRD-night 契约：`/feedback` 追加 evidence.md 再重写 memory.md；`/intent`
读 memory.md；无数据库。新颖度门 + IDF 辨识度决定**什么**进画像，所以 memory.md
比“把所有证据一股脑丢给 LLM”更精准。

## 说明

- **配额全队伍共享** → 标签只拉一次并缓存在 `.cache/`，客户端控制在 ~110 次/分钟以内。
- 按挑战许可，**Cyanite 模型输出（`.cache/`）和运行时记忆 git 忽略**，不要提交。
- `/your-sound` 的可选 LLM 润色仅在设置 `ANTHROPIC_API_KEY` 时启用；它只换措辞，
  绝不编造偏好。

---

## 设计参考文献

记忆设计借鉴了可解释 / 案例式推荐的成熟思路，使“记什么”和“为什么推这首”都建立在
已知方法之上，而非临时启发式：

- **可解释推荐与标签式解释** — Zhang & Chen, *Explainable Recommendation: A Survey
  and New Perspectives*（[arXiv:1804.11192](https://arxiv.org/pdf/1804.11192)）。
  用“用户喜欢的标签”来解释每条推荐的依据。
- **可审查的自然语言用户画像** — *On Natural Language User Profiles for Transparent
  and Scrutable Recommendation*（[arXiv:2205.09403](https://arxiv.org/pdf/2205.09403),
  [v2](https://arxiv.org/html/2402.05810v1)）。支撑“画像存成人可读、可编辑的
  Markdown 而非黑盒向量”。
- **案例式推荐（范例）** — Smyth, *Case-Based Recommendation*
  （[综述](https://www.researchgate.net/publication/220800382_Case-Based_Recommendation)）。
  **锚点曲目**的依据：用“像你喜欢的这些曲子”来解释一条推荐。
- **批评式推荐（Critiquing）** — *Critiquing-based recommenders: survey and emerging
  trends*（[Springer](https://link.springer.com/article/10.1007/s11257-011-9108-6)）。
  方向性反馈（“more X / less Y”）的理论来源。
- **记忆激活（频次 + 近因）** — 强化计数 + EMA 加权遵循人类记忆的激活模型：复用概率
  随使用频次和近因上升。

新颖度/冗余门控与“按稀有度筛选（IDF）”是标准信息检索思想，在此用于决定**什么值得记住**。
