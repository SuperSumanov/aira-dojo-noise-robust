# Within-stratum Target-522 不重叠前瞻确认预注册

## 结果前完整性修订（2026-08-28T13:03:57Z）

首个 monitor 启动后、候选仍为空且 LATEST 仍为固定 887 snapshot 时，发现原协议只列了 corpus 输入 basename，
没有列出独立证明 first-observed crossing 必需的 `observed.tsv`、`candidate.tsv`、`source_script.sh` 等
selection-support 文件；测试终止该 monitor 时又观察到 TERM 没有产生预期 `FAILED_RC`。旧 monitor 已保留为
`SUPERSEDED_PRE_CANDIDATE`，其退出回执缺失也如实记录；没有候选身份或 increment profile 被读取。
旧目录 `SHA256SUMS` 的 SHA-256 为
`423a595f098040f0a2169231d0a20d7c01e23e377a88b328d4579fa94ed70131`。

本修订只把 corpus 与 selection-support 白名单分开，并让脚本显式捕获 TERM/INT/HUP。population、estimand、
Target-522、全部 exact gates、分类顺序及 claim boundary 均未改变。新版 monitor 必须从同一 887 基线重新启动。

## 候选到达前实现

- producer：`phase1/audit_tree_within_stratum_forward_target522.py`；
- 独立 verifier：`phase1/verify_tree_within_stratum_forward_target522.py`，不导入新 producer；
- 两边分别重建 baseline/candidate blind snapshots，并分别验证 selection package、first-observed crossing、
  registry/run-ledger append-only、旧 run/endpoint 的 payload 与原始字节不变、完整新增 physical-run 差集；
- full-snapshot 图完整性先于取差集检查，避免 cross-run parent 在差集里伪装成缺失父节点；
- synthetic end-to-end、哈希合法但跳过更早 crossing、旧行漂移、cross-run parent 与 cycle 攻击均进入测试。

截至实现完成，真实 Target-522 candidate 尚未产生，也没有运行任何真实 increment profile。

状态：`OUTCOME_BLIND_PROTOCOL_FROZEN_BEFORE_TARGET522_SELECTION_OR_INCREMENT_PROFILE`。

冻结时 `LATEST=887491a...`，first-960 provisional population 为 435 runs。候选 snapshot 的身份、计数与任何
increment profile 均未见。

## 为什么不使用“下一个 successor”直接复现

下一个 snapshot 很可能只比 887 多一个很小的 batch；在累计人口上重算会与 887 高度重叠，不能诚实地称为独立复现。
本协议改为首个达到 522 runs 的 snapshot：`522=ceil(435*6/5)`，因此可提取至少 87 个完全不重叠的未来
physical runs。primary estimand 只使用这些新 runs 的全部 endpoints，887 的旧 rows 一律不进入 primary。

## 自动选择与防事后挑选

公开 monitor 从仍为 887 的状态启动，每 5 秒观察一次 outcome-blind `LATEST`；首个 observed
`provisional_first960_runs>=522` 的 immutable snapshot 自动锁定，保留 boundary overshoot。选择过程只读 snapshot
身份、run/endpoint/task counts 与文件 hashes，不计算 within-stratum profile。候选文件必须连续 6 次 hash-stable。

monitor 记录 append-only observation journal。中断后只有当 `LATEST` 仍等于最后已记录 snapshot 时才能 resume；否则
fail closed 并要求单独 continuity audit，不能直接拿当时最新 snapshot 补选。

## 主判定

primary cohort 是 candidate run IDs 减去 887 run IDs 后的完整物理 runs。必须验证旧 run/card rows 全部未改、无 partial
run，并至少有 87 个新 runs、1,500 observed edges、60 个可条件化 runs、8 个可条件化 tasks，parent-present endpoint
fraction 至少 3/4。

scientific thresholds 原样继承已披露的 v1：task/run `W_p` 至少 1/5、3/20；conditional-TV≥1/10 的 group fraction
至少 1/2、1/4；最大 task/run canonical contribution share 至多 2/5、1/5。两轴全过才允许 headline
`FORWARD_INCREMENT_BROAD_NONCOMPOSITIONAL_LINEARIZATION_DISTORTION`。

所有 gate 比较只使用 `Fraction(numerator, denominator)`；`decimal_17g` 只作人类可读描述，永不参与完整性或科学门。
这直接消除 887 formal 的 float-string failure mode，但不会改判或 rescue 887。

## 主张边界

若通过，只能说在自动选出的至少 87 个不重叠未来 physical runs 上，within-task/run distortion 通过了冻结门。
run 独立不等于 task 独立；这不是 cumulative cohort 的独立复现，不证明 predictor accuracy、search utility、语义重要性、
完整 source tree 或跨所有未来分布泛化。

禁止读取 label/grade/outcome/prediction、accuracy/effect/utility 或 raw senior archive；
GPU/API/model-fit/base-update=`0/0/0/0`。机器协议见
`phase1/tree_linearization_within_stratum_forward_target522_v2.json`。

## Formal 自动化与 post-push 回执（结果前）

commit `70a48e3df8c5c764abde277fcad842771de1ffe2` 冻结了以下执行链：

- formal runner：`phase1/scripts/run_tree_within_stratum_forward_target522_formal_20260828.sh`；
- structural-only watcher：`phase1/scripts/monitor_tree_within_stratum_forward_target522_formal_20260828.sh`；
- watcher 在 selection `COMPLETE` 前只检查文件存在性，不读取 candidate identity/count 或 profile；
- selection 闭合后，watcher 才验证固定 selection-package hash 并调用 exact git-object 中的 runner；
- runner 使用 fresh detached worktree，执行 producer A/B、独立 verifier A/B、字节一致性、`strace` 文件/网络审计、
  凭据扫描与 immutable manifest，`COMPLETE` 最后写入；失败和中断均有显式回执。

该 exact push 在独立 Linux fresh worktree 上完成 post-push 复验：

- root：`/research/d7/spc/yzyang4/tree-target522-postpush/postpush-70a48e3-v3`；
- focused：`27 passed in 0.66s`；
- full：`1424 passed, 47 warnings in 86.99s`；
- Python：`3.11.15`；GPU/API/model-fit/base-update=`0/0/0/0`；
- credential filename/content hits：`0/0`；
- `SHA256SUMS` SHA-256：`5b63572ccaf04df80158be170acaa47aceb3f53c19c6534d3ee723c118ff8dc9`。

两次失败的 post-push 尝试原样保留：v1 误从仓库根收集 legacy tests；v2 未限制 BLAS/OpenMP 线程，发现登录节点
CPU 异常后只终止了经 PID/PPID 核验属于本次任务的进程。v3 加入单线程环境限制后通过；这不是隐藏失败，也不改变
科学协议。

截至 `2026-08-28T13:36:15Z`：

- selection root：`/research/d7/spc/yzyang4/tree-within-stratum-forward-target522/latch-42f1044-after-887-v2`，
  PID=`4047654`，状态 `WAITING`；
- formal watcher root：`/research/d7/spc/yzyang4/tree-within-stratum-forward-target522/formal-monitor-70a48e3-target522-v1`，
  PID=`4055136`，状态 `WAITING`；
- 两把锁均有效，`LATEST=887491a021d75d889c00a5af672a11b8b06e249d98e84fd91288534080f62697`，
  first-960 provisional runs=`435`，candidate=`none`。

因此当前新增资产是不可挑选、可独立复验的前瞻执行链；真实 future-increment scientific classification 仍未产生。
