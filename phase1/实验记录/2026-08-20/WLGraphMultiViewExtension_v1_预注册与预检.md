# WL candidate-code graph / multi-view extension v1：预注册与预检

> **时间字段勘误：** 协议内手填的 `frozen_at_utc` 后经远端时钟核验为未来时间戳，永久作废；不得用于建立
> temporal precedence。模型配置和输入哈希不变，严格前瞻效果只从后续自动生成的 activation receipt 之后计。
> 详见 `WLGraphMultiViewExtension_v1_时间字段勘误.md`。

## 目标与非目标

目标是补齐 0BS 暴露的 graph-family baseline 缺口，而不是申报 GNN/WL novelty。该 extension 只用 v11 train b0
拟合，在 first-960 outcome 打开前对盲 manifest 评分并封存。它不进入 primary、不改停止规则、不读 v11 frozen/
extension、不算训练 accuracy，也不根据当前 first-960 结果选模型。

WL 子树特征遵循 Shervashidze et al. (JMLR 2011) 的离散节点标签迭代思想；FeatureHasher 使用 sklearn 固定
MurmurHash3 实现。这里的图是 candidate program AST/token graph，不冒充 FLORA 的 workflow-internal DAG。

## 固定矩阵

| arm | 固定视图 | 用途 |
|---|---|---|
| `step_only_lr` | step | 位置/生成顺序负控 |
| `wl_graph_lr` | candidate-code WL graph | graph-family 单视图 |
| `wl_graph_static_lr` | WL graph + 既有 decision-time static | 去掉 global char semantics 的多视图消融 |
| `wl_graph_static_tfidf_lr` | WL graph + static + 既有 char TF-IDF | 完整适配多视图 |

四臂均为 symmetric Bradley–Terry LR，`C=1`、无截距、liblinear、seed=20260820、tol=1e-6、max_iter=2000；
不调参。future 结果必须同时与已冻结 `static_lr`、`char_tfidf_lr` 配对报告，且 graph 正结论至少要求完整多视图
相对 char TF-IDF 的 task-clustered CI 下界大于 0；详细 effect gate 在首次评分前另立一次性分析协议，本次不计算。

图配置：AST parent-child 双向 field-labeled edge；初始 node label 保留 AST class 与归一化 identifier/import/
attribute/keyword，常量只保留类型；WL=2，最多 8,192 nodes。AST 失败固定降级 token-sequence graph，tokenizer
再失败降级 raw-line sequence graph。三种模式都产生图，不因已知 97.25% AST 覆盖改阈值。FeatureHasher=65,536
维、alternate_sign=true、float64，逐 endpoint L2 normalize。global TF-IDF 和 static view 必须逐项复用已冻结 scorer
的定义。

## 13 项预检

1. **旋钮产物验证**：bundle/summary 写四臂、WL=2、8192 cap、65536 dims、fallback counts 和全部系数 shape。
2. **便宜路径**：先过合成 parser/fallback/cap/hash determinism；再只对 train-only 小前缀做计时 smoke。
3. **测试查重**：只读已锁 SHA 的 v11 train 4,263 pairs/5,499 endpoints；不构造新 OOF，不读 frozen。
4. **分布**：只报告 parser mode/node/truncation/feature-mass；不报任何效果均值。
5. **评估配平**：本次无 effect eval；future 必须 task/run clustered paired inference。
6. **模型保存**：NPZ、`allow_pickle=false`，保存全部系数、scale、TF-IDF vocabulary/IDF 和 config。
7. **泄漏三查**：复用 train manifest + run/node/raw-code isolation 证据；CLI 禁止 frozen/test/held 参数。
8. **RNG**：FeatureHasher stateless；LR seed 固定；cards/pairs 全排序；不 shuffle。
9. **密钥**：不读 env/API；输出不含 raw code；push 前 filename/content 双扫描。
10. **墙钟**：smoke 外推 build 上限 7,200 秒；超出即停止，不缩图/挑任务救结果。
11. **功效**：本次只冻结 scorer；不得用未来支持不足解释性地修改模型。first-960 + closure 不变。
12. **真实 rc**：producer/verifier/score rc 立即保存，失败不继续。
13. **扩语料冻结**：训练输入五个 SHA 固定；future cohort 排序仍用既有 first-960 ledger，不重抽。

## 预算与停止条件

0 GPU、0 API、0 base-LLM update；单线程 CPU。build 与独立 refit 各最多 2 小时、peak RSS 各最多 32 GiB。
工程 smoke 若外推超过任一门，只保留 feasibility 结果并停，不在用户离开期间申请 GPU。用户此前已授权所有对
该正方向有利的实验；本矩阵不使用贵资源，也不扩大 primary 权限。
