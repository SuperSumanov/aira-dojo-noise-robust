# TraceML Human Fork Future：跨域前瞻资格与效果预注册

日期：2026-08-21。状态：`PREREGISTERED_BEFORE_GRAPH_SUPPORT_OR_OUTCOME_READ`。本方向不替代 AIRA strict-future
escrow，也不恢复旧 HCE/TD/probe；它是冻结 transition scorer 的独立、跨域 extension。

## 1. 为什么值得做，以及不能声称什么

TraceML 官方固定 revision `61faec615b179f186dbe9c82ee59d17e14817e96` 公开 134 个 Kaggle competitions 的
human revision forest、4,847 个 human kernels、graph tables 与 2.9GB raw notebooks。官方构建代码明确把
version/fork/code-sim 三类边组成 forest，并按 `version > fork > code_sim` 为每个 node 选 canonical parent。此前
我方 v1 审计只检查了被线性化的 13 个 MLEvolve runs；它没有审计 human fork graph，因此不是重复读数。

这里唯一问题是：**给定同一个 human parent version 的两个真实 fork 起点，冻结的 parent-relative transition
scorer 能否判断哪个 fork 最终通向更好的 kernel best-private score？** 这把 immediate sibling ranking 外推到
“node may lead to a better solution”，与学长提出的 future-potential novelty 直接对应。

边界必须写死：human forks 不是 agent 同时生成的 search candidates，也不证明在线 AIRA search gain。即使为正，
只能称 `cross-domain human-fork future-potential transfer`；主结论仍须等待 activation 后 AIRA strict-future runs。

官方依据：

- dataset card：https://huggingface.co/datasets/TraceML-HF/TraceML；
- graph files：https://huggingface.co/datasets/TraceML-HF/TraceML/tree/main/extras；
- canonical-parent code：https://huggingface.co/datasets/TraceML-HF/TraceML/blob/main/code/02_parent/build_forest.py。

## 2. 冻结 estimand

只接受 human graph 中满足全部条件的 child：`parent_id` 非空、canonical `edge_kind=="fork"`、parent/child
node 唯一存在、competition 相同、depth 精确 `+1`、child kernel 与 parent kernel 不同。一个 choice set 是共享同一
精确 parent node 的所有不同 child kernels；canonical pair 是其中所有按 node ID 排序的无序二元组，不按 outcome
抽样、不把 version/code-sim/alt-parent 边混入。

主标签固定为 child kernel 的有限 `best_private_score`，按该 competition 的 `score_is_max` 统一方向；两 child 相等
永久记 tie 并排除。这个标签是 fork 后的 eventual branch outcome，不是 child 当时的分数。secondary 才是两 child
均有限时的 immediate `score_public`；不得因 primary 结果调整标签。

Primary 只保留 scorer train+dev 从未出现过的 competition slug。模型不输入 task ID，但这一排除使外部证据同时
具备 source-domain 与 task-domain 距离。task-overlap 结果只能作为明确标注的 secondary，不进入 headline。

## 3. 四阶段 fail-closed 协议

### S0：输入与 schema

固定 dataset/revision/license/path，下载 `nodes/edges/trees/kernels.parquet` 与 `competitions.json`，只读取 schema、
行数 metadata、字段名与 categorical identity；不访问 score 列值。逐文件 SHA-256 写入单独 input manifest 并在
任何支持计数前提交。schema 必须能唯一证明 node/kernel/task/parent/depth/edge-kind/raw-code path 与 score direction；
否则 `IDENTITY_OR_JOIN_AMBIGUOUS`，停止。

### S1：结构与 outcome support

按上节固定映射一次性汇总，不输出逐行 score。必须同时满足：task-unseen competitions≥20、parent groups≥100、
finite non-tie eventual pairs≥500、dominant pair-task share≤0.20、fork child kernel identity 唯一、depth 全部+1、
tree/parent join 无歧义。任何一项失败，停止且不下载 raw notebook。

### S2：代码与来源门

仅 S1 全过才下载 `trajectories_human.tar.gz`。先用不打印匹配内容的 path-only scanner 检查 credential shape；命中的
整份 notebook 在任何科学 parser 前隔离，不读取、不手工修补。其余 `.ipynb` 只按 notebook 顺序拼接 code-cell
source，以两个换行分隔；markdown、outputs 与执行结果全部忽略。parent/children code coverage 必须为 1.0；转换后
任一 code SHA 与 scorer train、v11 frozen/extension 或 prospective inventory 重叠则整 pair 排除，排除后必须重过
S1 数量/平衡门。路径不存在、多对一或 license 不允许均 fail closed。

### S3：冻结 scorer 一次性效果读数

只能使用 activation `dd3aeb4a...` 绑定的 `7458f09...` full-fit 三臂；不重训、不调参、不选择 checkpoint、不看
external dev。固定 primary=`child_plus_transition - child_code`，相同 pair 上计算 task-macro accuracy delta；
task-clustered 与 parent-clustered paired 95% CI 下界都>0、combined accuracy 的两类 chance CI 下界都>0.5、且所有
leave-one-task-out delta 点估计>0，才允许 external positive。否则按预注册报告 null/negative，不换子集或 outcome。

## 4. 13 项预检

1. 当前方向：Decision Corpus + Predictor Benchmark 的 frozen future-potential extension；
2. 唯一问题：冻结 transition 表征是否跨到 human fork eventual outcome；
3. 输入：固定 HF revision/path/license，S0 后补不可变 SHA manifest；
4. 划分：primary task-unseen；source overlap 在 S2 逐代码排除；
5. 样本：全部 canonical fork siblings，不重抽；
6. 模型：三臂与所有 HGB 参数绑定正式 activation receipt；
7. 统计：task/parent clustered CI、LOTO 与 immediate secondary 全部预先固定；
8. RNG：模型 random_state=7；bootstrap seed/replicates 在 S3 源码结果前固定；
9. 资源：S0/S1 CPU、<100MB；S1 过门后才允许约 2.9GB 下载，GPU/API=0；
10. 完整性：producer/verifier 双实现、raw credential 隔离、exact-code overlap 与 syscall 路径审计；
11. 失败：任一 identity/support/license/code/security/verifier 门失败即停止；
12. 恢复：每阶段独立目录/manifest，S2 大文件可 resume，不覆盖旧 artifact；
13. 封存：命令、版本、SHA、聚合结果、空 diff/stderr 与只读权限全部入 receipt。

机器可读合同：`phase1/traceml_human_fork_future_protocol_v1.json`。本预注册时尚未下载 graph files，尚未读取
任何 graph support 数量、best-private/public score 值或 raw notebook 内容。
