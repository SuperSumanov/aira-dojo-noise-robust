# FLORA transfer invariance audit v1

日期：2026-08-20。结果前 source commit：
`fa7468fac6038b8391a31a6dd161f6138255aa60`；protocol SHA256：
`b9d72bd8d245d42befefe9c021ccc124ea25c4da374295df3a057ab0b7b033d4`。

## 裁决

正式状态是 `FLORA_TRANSFER_REQUIRES_FURTHER_ADJUDICATION`，不是 graph baseline 的效果结论。

- **原版不能等价搬运。** FLORA/Agentic Predictor 要求 workflow 内部 node prompts、internal edges、operator
  implementation、node implementation code、global workflow prompt/code 和自然语言任务。v11 的 7,760 个
  作用域 endpoints 只有自然语言 task description 覆盖 100%，前瞻 5,643 endpoints 的安全 blind sidecar 只有
  task identifier；两侧均有 candidate code，但都没有等价 workflow DAG，literal-equivalent fraction 均为 0。
- **不能用“lineage 完全恒定”作为省略 graph family 的理由。** v11 的 5,897/5,897 pairs 与前瞻当前前缀的
  1,473/1,473 pairs 中，`op/depth/n_siblings` 均无差异，但 `step` 全部不同，因此预冻结的 non-degeneracy
  判据在两侧都通过。两侧 exact candidate code 也分别 5,897/5,897、1,473/1,473 不同。
- 这只证明结构上有可区分输入，**不证明 step 或 graph 有预测力**。`step` 可能只是生成顺序/位置偏差，而且现有
  `static_lr` 已显式包含 `step/depth/n_siblings/op`。朴素 search-lineage GNN 若不加入 candidate code graph 或
  更丰富上下文，只是在重新编码已有顺序特征，不构成方法突破。

因此 `baseline_omission_rationale_supported=false`。若补 family baseline，必须作为 outcome-unread extension 或
未来 cohort，固定包含 `step-only` 位置负控，并把 AST/token candidate-code graph 与 global code/lineage 分开消融；
不得在 v11 frozen 或当前 first-960 outcome 上挑结构、深度或超参。

## 作用域与复核

- v11：5,897 b0 pairs、3,252 choice sets、440 physical runs、23 tasks；frozen 中 1,498 行未直接发布
  `run_id`，均由两个 endpoint 的一致 provenance 恢复，其他 4,399 行与声明 run 一致。
- prospective：固定 snapshot
  `88cb79191b23738c1813a131abe2d5dbba48c31cb8c8095d047902afa29170c8`，223/960 runs 当前前缀；
  1,473 pairs、1,431 choice sets、222 decision runs、25 tasks。未打开 label vault/outcome/scorer prediction。
- producer A/B 三个产物逐字节一致；不 import producer 的 verifier A/B 也逐字节一致，10/10 assertions 通过。
  summary SHA256=`c8916ed84e7d2d661f3c5670f562725344935242d92a1e8379ed8896770baf2a`；独立验证 SHA256=
  `da804f0def4c5d1d94d6a9ad7315aa794deffaa83b6bdf4e18d9841e6f7fb162`。
- Linux focused：`7 passed in 0.11s`；全套：`462 passed in 64.50s`。0 GPU、0 API、0 base-LLM update。

## 安全扫描与失败记录

粗路径 grep 首次因四个 clean-worktree `git status` 各对历史 `score_index.jsonl` 做一次 `newfstatat` 而停止；
该失败原样保留在 `coarse_forbidden_path_scan_failed.txt`。随后 syscall-aware 独立复核四份 trace：禁读路径
metadata calls=4，`open/openat/openat2/creat` content opens=0，状态
`FORBIDDEN_CONTENT_OPEN_SCAN_PASS`。四份 trace 不进 Git，只在受控远端保存，SHA 写入
`forbidden_content_open_scan.json`。

执行前还有两次无科学输出的工程失败：一次在 source env 前启用 `set -u`，一次 clean worktree 被无关旧 LFS
tarball 的服务器 404 阻断；最终改用 no-smudge clean worktree，并对四个 v11 实体输入逐项锁 SHA。两次失败均未
进入 producer，不影响最终双跑。

远端完整产物：`/research/d7/spc/yzyang4/flora-transfer-fa7468f`。
