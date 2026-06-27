# 口味记忆 — 实验与评估

我们如何决定**记住听者的哪些信息**，以及（基于真实用户数据的）证据，证明**存储方式、
推荐质量、解释可信度**三者都站得住。

所有数字都用缓存的 Cyanite 标签计算；底部有复现命令。

---

## 机制（一段话）

每个 like 都过一道**新颖度门（novelty gate）**。只有当一首曲占据了一个**全新的口味面**
（genre / mood / character）时，才会成为新的**锚点（anchor）**；与已有锚点重叠的 like
只是**强化**它（计数 +1），稀有乐器/纹理则**丰富**最近的锚点而非新建。每首曲“记什么”
由**辨识度（IDF）**筛选：稀有的标签如 `asianFlute` 保留，满大街的如 `drums` 跳过。
每次写入都给出人话理由——记忆就是一份你能直接读的 Markdown。

---

## 实验 1 — 新颖度门去冗余但不丢全貌

把用户 **4006097** 的 25 首喜欢曲目逐一过新颖度门：

> **25 个 like → 存为 14 个锚点，11 个被强化（去重 44%）。**

部分决策示例（每条都是写进记忆的理由）：

| like | 决策 | 理由 |
|---|---|---|
| 一首金属 | ▲ 存 | `new facet: metal, aggressive, rock` |
| 又一首 ambient | · 去重 | `83% facet overlap with anchor …; reinforced (×3)` |
| ambient + 双簧管 | · 去重 | `reinforced (×2); noted new texture: oboe, strings, woodwinds` |

这 14 个锚点构成了该用户口味的一张小而清晰的“地图”；被强化最多的锚点（`×4`）是核心，
只出现一次的锚点是边缘（metal、asian）。→ 记忆存的是**信息**，不是重复。

---

## 实验 2 — 真实 likes 的离线评估（hold-out）

对 16 个用户（每人 ≥10 likes）藏起 30% 的 likes，用剩下的建画像，再测量
（AUC：0.5 = 瞎猜）。负样本是**其他同样偏氛围的用户**的曲目（难负样本），所以这些数字
**不是**靠“氛围 vs 非氛围”这种简单切分刷出来的。

| 问题 | 指标 | 结果 |
|---|---|---|
| **推荐合理吗？** 画像能否把藏起的*真实* like 排在非 like 之前？ | Recognition AUC | **0.705**（plain）→ **0.759**（IDF）|
| **是他的口味、不是通用？** 本人画像 vs 别人画像，打同一批藏起曲 | Personalization AUC | **0.799** |
| **存储合理吗？** 仅用锚点 vs 用全部 likes 建画像 | Compression | **0.777**（锚点）vs 0.759（全量），只留 **57%** 的 likes |

**要点**
- 在难负样本上 Recognition **0.76** → 画像真正捕捉到了口味。
- IDF（辨识度）加权**优于纯标签（0.76 > 0.71）** → 存“稀有/有标识性”的标签是对的。
- Personalization **0.80** → 记忆是个性化的，不是“所有人都 ambient”。
- 仅用锚点**追平/略超**全量，且**少 43% 的曲目** → 新颖度门去掉的是冗余*和*噪声，
  存储方式合理。

---

## 实验 3 — 忠实度：我们的解释跟得上黑盒吗？

我们看不到 Cyanite 的 embedding，于是用共享标签来解释相似性。这忠实吗？取 Cyanite
similar-by-ID 的 **60 个（种子，邻居）对**，把 Cyanite 的相似分和我们的 tag 重叠做相关：

| 我们的可解释指标 | Pearson | Spearman |
|---|---|---|
| **IDF tag-cosine** | **0.363** | **0.379** |
| facet-Jaccard | 0.21 | 0.215 |

正相关且一致 → 当我们说*“相似是因为同样 calm / ambient / piano”*，这确实反映了
Cyanite 模型真正测到的东西。IDF-cosine 又一次胜过原始重叠。相关性是中等（不是 1.0），
有两个诚实原因：(a) Cyanite 的音频模型还听到了标签未编码的制作/质感；(b) **range
restriction（取值范围受限）**——similar-by-ID 只返回本就相似的曲，分数带很窄，会衰减
相关性。所以 0.36 是“标签能解释多少模型”的**下界**。

见 `analysis/faithfulness.png`。

---

## 三组实验合起来证明了什么

1. **存储合理** — 新颖度门去重保留 57% 的 likes，预测力**持平甚至更好**（实验 1 + 2 压缩）。
2. **推荐合理** — 画像识别真实藏起 like 的 AUC 0.76，个性化 0.80（实验 2）。
3. **解释忠实** — 我们基于标签的“why”与 Cyanite 自身相似度正相关（实验 3），说明解释
   不是事后编造。
4. **辨识度（IDF）处处有效** — Recognition 0.71→0.76，且忠实度相关性最强。

---

## 复现

```bash
# 仓库根目录，hackatune 环境
python -m backend.profile.experiment_novelty   # 实验 1：用户 4006097 的新颖度门
python -m backend.profile.evaluate             # 实验 2：16 个用户的 hold-out AUC
python -m backend.profile.faithfulness         # 实验 3：tag 重叠 vs Cyanite 相似分（+散点图）
```

IDF 用的目录基率在 `tag_base_rates.json`（844 首曲目的聚合标签频率；不含原始模型输出，
符合挑战许可）。
