# TraceML 外部结构资格审计 v1：预注册与预检

日期：2026-08-21。状态：`PREREGISTERED_NOT_RUN`。该审计不读取我方 prospective outcome，不训练模型，
不把 189 条 root-to-leaf branches 当作独立 physical runs。

## 1. 当前方向与问题

当前唯一入口仍是 Decision Corpus + Predictor Benchmark + first-960/closure。TraceML/MLE-Traj-v1 已关闭宽泛的
“首个 MLE trajectory dataset”主张，但 TraceML 官方固定 revision 公开了 agent/human paired tables、tree/node/edge
extras 与代码。唯一正向问题是：该独立 release 能否恢复出足够且定义明确的 **真实 same-parent agent sibling
decision**，从而成为未来冻结 scorer 的外部 replication cohort。

## 2. 固定输入与版本

固定 Hugging Face dataset=`TraceML-HF/TraceML`、revision=
`61faec615b179f186dbe9c82ee59d17e14817e96`、license=`CC-BY-4.0`。只下载并锁 SHA：

- `data/paired/state.parquet`；
- `data/paired/action.parquet`；
- `extras/edges.parquet`、`nodes.parquet`、`trees.parquet`、`trajectory_index.parquet`、`kernels.parquet`；
- 为解释字段所必需的官方 README、DATASHEET、schema manifests 与构建脚本。

若 revision、license、HTTP/LFS identity 或下载后 SHA 不一致，立即停止。原始文件放在 Git 外只读缓存；Git 只收
脚本、SHA manifest、聚合回执和不含 raw code 的报告。

## 3. 两阶段读数规则

**S0 schema/provenance 阶段**只读 schema、列名、dtype、官方构建代码与 categorical identity values；不得汇总或
打印 `score_old`、`score_new`、代码正文、LLM 标签或逐行 outcome。S0 必须先固定：

1. agent/human 判定；
2. 13 个 MLEvolve physical-run identity 如何从原始 tree provenance 恢复；
3. canonical parent/child edge 与 same-parent sibling set；
4. branch/path 重复的去重键；
5. score direction 与缺失/tie 处理；
6. code 到 node 的唯一 join 以及对我方 train/frozen/prospective 的 overlap key。

任一映射不能从官方字段/代码唯一证明，则 `IDENTITY_OR_JOIN_AMBIGUOUS`，不读取效果值、不补 heuristic。

### S0 schema 后、支持计数前的固定映射补丁

官方 `import_v1_agents.py` 证明 TraceML v4 将 v1 agent branch 导入为 synthetic linear chain，且 v4-only
`tree_id/raw_code_path` 对 agent 为空；因此不能直接使用 v4 `parent_id` 或 `tree_id`。但 189 个公开 MLEvolve
`key_id` 全部具有官方自描述形式 `<run_id>__branch<integer>`，dataset card 同时明确这些是 13 个 tree-search
runs 线性化出的 189 branches。任何 sibling 支持量产生前，固定如下恢复，不再修改：

1. 只接受 anchored regex `^(?P<physical_run>mlev__run_.+)__branch(?P<branch>[0-9]+)$`；189/189 必须匹配，
   且去 suffix 后必须恰为官方声明的 13 个 physical runs；
2. 原始节点键固定为 `(physical_run, orig_version_number)`；每个 key 内用 action 的 `(v_old,v_new)` 分别
   join state 的 `(key_id,version_number)`，禁止使用 v4 synthetic `parent_node_id/child_node_id`；
3. 原始 edge 固定去重为 `(physical_run,parent_orig,child_orig)`；每个 child 最多一个 parent、无环、每个 edge
   的 depth 必须正好 `+1`，同一原始节点跨 branches 的 task/depth 必须一致；
4. sibling set 是同一 `(physical_run,parent_orig)` 的去重 direct children；branch 重复只算一次。任一强条件
   失败即 `IDENTITY_OR_JOIN_AMBIGUOUS`，不得放宽为 ancestor edge 或从字符串外再猜关系；
5. paired agent 的 `raw_code_path` 若仍为空，结构支持可以描述，但冻结 scorer 资格仍失败；只有正常获得 v1
   gated raw tree/code 并完成 SHA/overlap 审计后才可补 code join。

该补丁只使用 schema、官方 importer、dataset card 与 identity key 形状，尚未读取 score 或计算 sibling 数量。

**S1 support 阶段**只在 S0 receipt 固定后执行，输出聚合计数与哈希，不输出 raw code/score：physical runs、tasks、
parents、children、finite non-tie sibling pairs、最大任务占比、branch duplication、code coverage 与三套我方集合的
exact code SHA overlap。任何 overlap 必须隔离；不能称 external。

## 4. 预固定资格门

只有全部满足时，才允许另行冻结并一次性运行既有 scorer：

- 至少 8 个独立 MLEvolve physical runs；
- 至少 4 个 tasks；
- 至少 150 个 finite non-tie canonical sibling pairs；
- dominant pair-task share `<=0.50`；
- scorer 所需代码覆盖完整，identity/join 无歧义；
- 与我方 train、v11 frozen/extension、prospective 的 physical-run/card/exact-code SHA overlap 均为 0。

S1 过门不授权效果评分；评分脚本、唯一 headline、聚类区间与 scorer identity 仍须在读外部 pair outcomes 前另行
冻结。若不过门，只能把 TraceML 作为 related work 和结构描述，不降低阈值、不把 paths 当 runs、不换 pair 定义。

## 5. 完整性、复现与资源

- 当前输入/输出：公共 TraceML 固定 revision；我方只读 code-SHA denylist，不读 prospective label/outcome/prediction；
- 随机性：无；排序、join 与 canonical pair 输出必须确定性，producer 双跑逐字节一致；
- 独立复核：另一个不 import producer 的 verifier 重建 identity、pairs、gate 与 overlap；
- 安全：下载文件先做 credential-shape 扫描；raw code 永不提交 Git；结果目录再扫描一次；
- 资源：CPU only，GPU=0、API=0、base-LLM update=0；下载文件各约 0.09--38 MB，总磁盘预算 <100 MB；
- 预计时间：下载 5--15 分钟，S0 10--20 分钟，S1 与独立复核 10--20 分钟；
- 失败处理：SHA/schema/license/identity/join/overlap/verifier 任一不符即 fail-closed，保存失败原因，不追正数。
