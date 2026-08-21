# Source Decision Answerability v1：执行前冻结

日期：2026-08-21。状态：`NOT RUN`。本轮把已经发布的 finite-finite orientation 与 status-certified
validity edges 组合成严格偏序，问一个未在近期报告计算过的问题：对多少真实 source choice sets，已有关系足以
认证唯一 source winner？这是数据 release 的 answerability 审计，不是 predictor、搜索控制器或新排序算法。

## 固定关系与 estimand

每个单位为 `(role, task, physical_run_id, parent_id)`，source set 必须来自冻结 identity registry：

1. retained finite children 仅由三份 v11 b0 pair 的 endpoint union 确定；上游已保证 endpoint count=finite count；
2. source-complete parent 的 source set=finite endpoints；source-incomplete 且 exact identity recoverable 的 source
   set=finite endpoints∪missing IDs；其余 149 个 identity-unavailable parents 固定为不可回答；
3. baseline direct edges 为发布的 `better -> worse`，只读取 orientation，不读取 `gap_raw` 或 numeric grade；
4. status 图再加入显式 `valid_child -> certified invalid_child`；主分析允许
   `EXECUTION_ERROR`/`OFFICIAL_GRADE_ABSENT`，强敏感性只保留 `EXECUTION_ERROR`；
5. 在每个 DAG 上取传递闭包。仅当某一 candidate 可达 source set 中所有其他 candidates，才记
   `unique source winner identified`；传递推断关系绝不写成真实 logged comparisons。

baseline 已识别 winner 在加边后必须保持同一 candidate；任一 cycle、context/endpoint mismatch、重复无向 pair、
identity/count 不闭合或 status child 未被全部 finite endpoints 支配都立即 fail closed。

## 不可变输入

- 3,252-parent source table：
  `75c02200d1f9b8d87614762a9f2b71ba3c678d598ff28bc237c8a46a4bc36d03`；
- 3,252-row source identity registry：
  `b4261a4f042e92acca4a53630efe3e33ea1f2847d1a8148e9c8f18c35b447cd2`；
- 2,079 validity edges：
  `dda9f121dc32a1ef309992b0bec61934864e35ec337385bb2f5c0c548b258a3d`；
- train/frozen/extension b0 orientation normalized-LF SHA：
  `bd31b467...251fca` / `2717e331...7a8da8` / `2facb5a1...c1ca9c`；
- 固定计数：5,897 published edges；role=4,263/1,498/136；902 invalid children；status categories=
  2,060 execution-error edges + 19 grade-absent edges。

不打开 cards/code/obs、raw journals、numeric grade、gap、regrade、score-channel、prospective vault/outcome 或
first-960。GPU=0、API=0、底座更新=0。

## 结果前 material gates

主分析与 execution-error-only 强敏感性都必须满足：

1. 新识别 source winners≥400；
2. all-parent winner-rate 绝对增益≥0.10；train 与 frozen 各≥0.08；
3. status-aware all-parent winner rate≥0.80；
4. source pair capacity≥100 的 supported tasks≥10，其中 positive-gain tasks≥8；
5. 新识别 winners 的 dominant-task share≤0.35。

任一主门或强敏感性门失败，都不能写 material source-winner recovery；不得改成 available-parent 分母、删除
identity-unavailable parents、筛任务、降低阈值或用 numeric grade 补图。通过也只允许主张该固定 release 的
provenance-bound winner answerability；不允许 complete total order、MAR、missing numeric outcome、predictor
accuracy、search utility、算法 novelty 或 first/only。

## 十三项 pre-flight

1. 方向：直接强化当前 failure-aware Decision Corpus/D&B 主线，不恢复旧 HCE/TD/多保真。
2. 代码：producer、独立 verifier、协议、测试与 runner 在完整 commit 后冻结。
3. 输入：五类输入逐字节或 normalized-LF SHA 绑定，所有已知计数同时核对。
4. 单位：parent；所有 headline 以全部 3,252 parents 为分母，task/run 不当 iid。
5. 已见结果：只知道 direct relation coverage 与 status edge 数；从未计算 source winner answerability。
6. 标签：只读既有 pair orientation 与 validity category，不读 grade/gap。
7. 身份：source-unavailable parent 永久不可回答，不从文件名或 task 代理 missing ID。
8. 图：DAG、endpoint/source closure、baseline winner 单调性均为硬门。
9. 推断：这是完整冻结语料的精确 census，不伪报抽样 CI；task breadth 用固定材料门。
10. 复现：producer×2、verifier×2、逐字节 diff、manifest、syscall 禁止路径审计。
11. 安全：所有输入 parse 前 credential scan；输出 parent/run 只保留 SHA-256，不输出 endpoint ID。
12. 资源：CPU-only，预计含全测试小于 30 分钟。
13. 停止：失败不追救；通过也不接入 scorer/搜索，strict-future 0CP 与 GPU 批准门完全不变。

## 首次 formal attempt 的结果前 runner 失败

commit `f34024c0631e895b0e202b4dc5d9b4fc19ad9b1a` 的 runner 在 fetch/worktree/artifact 创建之前退出：
cluster 的 base checkout 是稀疏工作树，不含 `phase1/v11_decision`，但 runner 错把三份 pair path 指向 base，而
既有 edge exporter 从 detached worktree 读取这些 tracked files。此次没有 output directory、producer、graph row
或 scientific summary。允许的唯一修复是把三份 pair path 与 normalized-LF SHA precheck 移到新 detached
worktree 创建之后；协议、五个 material gates、输入 blobs、分析/验证代码与停止规则均不变。
