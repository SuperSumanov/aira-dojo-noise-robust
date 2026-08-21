# Tree Transition Future Escrow：正式激活与初始托管

日期：2026-08-21。状态：`FORMALLY_ACTIVATED_INITIAL_SUPPORT_ONLY`。本报告只确认 scorer、时间边界与
append-only prediction escrow 已正式建立；不把基础设施完成写成方法正结果。

## 1. 无效 attempt 与修复边界

source commit `921769f...` 的首次正式 attempt 中，模型、activation、escrow 与 append 科学阶段均返回 0；但最终
trace gate 找到 80 次 forbidden-name 路径接触。根因不是结果读取，而是五个 source-binding 入口运行全仓库
`git status --porcelain --untracked-files=all`，对 `.env_default`、`regrade_*`、`score_registry.jsonl` 与 score
目录做了 metadata `stat/open-directory`。没有读取这些文件的内容，也没有计算 effect，但冻结契约要求零路径接触，
所以该 attempt 没有 conclusion、没有 COMPLETE，旧 activation 永久不提升。

修复 commit `7458f0969b92a258ea0e495bbbee282aa12b748e` 删除全仓库枚举，只保留三项精确绑定：HEAD 必须等于
source commit；每个协议登记路径的当前 Git blob 必须等于 `commit:path`；逐文件 SHA-256 必须匹配。新增反例测试在
临时 Git repo 中放置未跟踪 `.env_default`，确认五套绑定实现不枚举它，同时篡改任一登记源码仍 fail closed。

## 2. 正式执行与收据

正式自动 activation 时间为 `2026-08-21T07:05:03.916471Z`。固定模型输入仍为 5,240 train+dev pairs，三臂、
68/37/31 维特征、HGB 参数、random state 与 orientation 全部未变。执行矩阵为：

1. model producer×2 + independent verifier×2；
2. activation×1 + independent verifier×2；
3. initial escrow producer×2 + independent verifier×2；
4. prior append replay producer×1 + independent verifier×1。

共 30 次固定 HGB fit。两次 producer byte-identical；所有独立复算中 training reference 与 future margins 的最大
差均为 0.0；append replay 的 1,665 个 prior rows 逐字段完全存活。正式测试为 23 focused passed 与
582 phase passed（25 warnings）；17 个阶段 rc 均为 0，所有 reproducibility diff 为空。

完整性门同时通过：prospective forbidden-path syscall hits=0；commit filename/content 与 artifact credential-shape
hits 均为 0；226-entry manifest 全部验证；封存后 writable files=0。GPU=0、API=0、base-LLM update=0、
prospective outcome read=0。

## 3. 初始托管状态与可写边界

activation 时 current snapshot 的 249 runs、1,665 pairs 全部早于时间边界。初始 inventory 因而是：

- all/support-only pairs：1,665 / 1,665；
- strict/eligible pairs：0 / 0；
- eligible runs/tasks：0 / 0；
- effect metrics：空列表。

状态 `TRANSITION_ESCROW_INSUFFICIENT_FUTURE_SUPPORT` 表示“尚无严格未来数据”，不是 critic 效果失败。后续只能把
`generation_started_at_utc > 2026-08-21T07:05:03.916471Z` 的新 physical runs append 进托管；既有 rows 必须
逐字段生存。达到 1,500 source-novel parent-covered finite non-tie pairs、150 runs、15 tasks、dominant≤0.25、
parent coverage≥0.80 且 endpoint/run/code overlap 全零后，才允许另行运行已冻结的揭盲统计。

本轮唯一正向结论是：一个此前只在同语料接近门槛的 transition candidate，现在已经获得可独立复算、零结果接触、
严格时间外的验证基础设施。是否成为方法正结果仍完全取决于未来新 runs；不得提前写成 transfer/search gain。

## 4. 关键哈希与位置

- model summary：`7b32ddc85217245d65c767445439072e4dd08f4da88523ce5c52fc3156122bf3`；
- model verification：`33a117fb60577b96420cafff1cff274e3c029f20525d3a9996cdf0fe7ee933eb`；
- activation：`dd3aeb4afce7ff64423f9539beadba133cfeb3310a74169eb18ea27f7ba487d3`；
- activation verification：`70e611bdd56718c7112c8765ab3bf9e896e570f178a07d7c8d6413439be82b46`；
- initial escrow summary：`a3a2977ea2efb7c439e9669ffa24ffe7d6e9e2a5ce7f16a7e40ab8bca5649b50`；
- independent escrow verification：`26b8146503119a7d106e9113a27fccb7a60f408a62ca1e21fa207a21b6f378bd`；
- conclusion：`4e2eca820535e749bd060c9666b358801a3c0b158b77634514c68ab3ebf5b6ec`。

远端完整只读产物：`/research/d7/spc/yzyang4/transition-future-escrow/7458f09-v1`；Git 紧凑证据位于
`phase1/results/transition_future_escrow_20260821_7458f09/`。
