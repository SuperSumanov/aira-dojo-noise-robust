# Clean Direct-Decision Qwen Scaling：结构准备与预算校准预注册

日期：2026-08-21。状态：`STRUCTURAL_PASS_G0_NOT_RUN`。本文件在生成 train/dev 结构统计、训练任何
checkpoint 或读取任何新 Qwen 结果前冻结。它服从 `phase1/CURRENT_DIRECTION.md` 的 0CD/0BW；不恢复旧
HCE、多保真、probe、lookahead 或 RL 路线。

## 1. 问题、证据等级与禁止项

唯一问题是：在 exact-config、physical-run-clean 的 augmented decision pair 上，直接训练 Qwen3 Base
critic 后是否出现可重复的容量 scaling，并稳定超过同一 test 上的 char-TFIDF pooled baseline。该实验只给
Decision Corpus + Predictor Benchmark 补强模型容量轴，不申 reward-model 方法首创，也不直接证明搜索收益。

现有 pair/test 已被研究者看过，旧 TF-IDF 与 semantic-mixture 结果也已公开给本项目；所以本轮最多是
`RETROSPECTIVE_CLEAN_MODEL_SUPPORT`，绝不写成 prospective confirmation。训练进程不得读取 outer test，
checkpoint 只按 outer-train physical runs 内切出的 dev 选择。旧 checkpoint、旧周期性 test 曲线、旧
`train_decision.sh`、14B/27B、底座 agent 微调和任何 frozen-first-960 vault 均不得使用。

## 2. 固定输入与结构准备

- 代码 base：senior `baf6bddefe62b769b2fab699ff5805dd627dc69f`；
- 协议补丁：`phase1/upstream_patches/0001-Harden-critic-confirmation-protocol.patch`，SHA-256=
  `2fd5ca7b38e4277b68c2eb90b42c0f0ce85b8ab0ef687802e68ceeb8f0fc1fe2`；
- Cards：SHA-256=`5fd24c8e545a67e1048f8a67b23bcb64605b9ad584a4fbaa44aa1b1f1b6e1afb`，
  bytes=`604190866`；
- exact-config merged pairs：SHA-256=
  `bd6551dfce85d83f9f59716a31a9d7ab88605d6a21f51b41eb28177a952f47d0`，bytes=`2552829`，
  固定为 outer train `5240` / outer test `931`；
- train/dev producer：只从 outer-train physical runs 切分，seed=`20260821`，dev fraction=`0.10`；
- curator mode 只把原 outer-test 逐字节物化为 dedicated held-out file，不改变、过滤或重排 test rows。

结构阶段只允许 producer×2、独立 verifier×2、byte comparison、哈希和 credential-shape 扫描；GPU/API/
模型拟合/模型下载/新 outcome vault 读取均为 0。结构支持门事前固定为：

1. train/dev/test 的 Card、physical run 与 unordered pair 均零交集；
2. dedicated held-out test 恰为 931 rows，SHA 与 source outer-test 独立重建一致；
3. producer 双跑逐字节相同，verifier 双跑逐字节相同，且 verifier 不 import producer；
4. 结构输出 train `>=3800`、dev `>=300`，cross-split dropped 不超过 outer-train 的 25%；
5. dev 覆盖至少 20 tasks，最大 task share `<=0.20`，Draft/Improve 各至少 100 pairs；
6. 任何 hash、split、identity、immutable-write、测试或安全门失败，状态即
   `STRUCTURAL_PREP_INELIGIBLE`，不得通过换 seed/fraction/任务/子集追救。

## 3. 只有结构门通过后才可申请的 GPU 矩阵

### G0：纯工程预算校准（尚未获 GPU 提交授权）

一项 run：Qwen3-1.7B-Base、seed 6、2×96GB Pro6000、bf16、ZeRO-3、`max_len=16384`、
`head_frac=0.25`、task
conditioning 开、budget conditioning 关、LR `1e-5`、cosine、warmup `0.03`、每卡 pair batch 8、
gradient accumulation 8（有效 pair batch 128）。只运行固定 10 optimizer steps，在 dev 上执行一次完整评估；
不得打开 held-out test，不作科学结论。硬 wall cap 2 小时，即最多 4 GPU·h。记录启动/首步/十步/dev 的
wall time、峰值 GPU memory、tokens/examples per second、软件版本和退出码。

G0 的用途仅是把正式预算从猜测变成测量。只有无 OOM/NCCL/NaN、10 steps 和完整 dev eval 都结束，才按
`实测每完整 epoch + 20% guard` 计算 G1；否则先修工程，不缩 context、不换数据或模型偷偷追结果。

### G1：两 seed 容量轴（必须另行给出 G0 后精确 GPU·时并获批）

固定 8 runs：Qwen3 Base `{0.6B,1.7B,4B,8B}` × seeds `{6,7}`，每 run 2×96GB Pro6000，
`max_len=16384`、1 epoch、有效 pair batch 128、LR/scheduler/warmup/task/budget conditioning 与 G0 相同。
每卡 train/eval batch 与 accumulation 固定为 `0.6B:16/16/4`、`1.7B:8/8/8`、`4B:4/4/16`、
`8B:2/2/32`。每 10 optimizer steps 只评 dev，`greater_is_better=true`；所有模型×seed 的 checkpoint
与哈希先锁定，之后才用排他 ledger 各评分一次 dedicated held-out test。不得按 held-out 结果重训、改 checkpoint、
改超参或新增 seed。

固定报告 merged/Draft/Improve micro、task macro、逐 task 与逐 parent 结果、task-clustered 和
parent-clustered 95% CI、seed 离散度、loss/margin/calibration、训练与 query/init 成本。char-TFIDF 必须用相同
train/dev/test 和 train-only fit 重算，不能沿用不同行集的 59.90%。

固定正向效果门为：

1. 四规模两-seed merged mean 随参数规模单调不降，且 8B−0.6B `>=0.02`；
2. 8B 两个 seed 各自高于同池 char-TFIDF，且按 task 对两 seed delta 取均值后的 task-clustered 95% CI 下界 `>0`；
3. 8B 在 Draft 和 Improve 两子集相对 char-TFIDF 的 point delta 都不低于 `-0.01`；
4. 无 task 独占：leave-one-task-out 删除任一 task 后，8B−TF-IDF merged point delta 不得改变符号。

四门全过才可写“clean direct-decision capacity scaling 且 8B 稳定超过字符基线”；否则逐项诚实报告，停止
14B/27B extension。即使全过，也不等价于 critic 改善真实搜索；search utility 仍需未来独立协议。

## 4. 13 项执行前检查

1. PASS：唯一科学旋钮是 Qwen3 参数规模；所有训练/数据/选择规则显式固定。
2. PASS：协议补丁此前本地 24/24、远端 33/33；本次结构工作树仍须重跑聚焦测试。
3. PASS：训练期 test path 被代码拒绝；G0 明确不挂载 held-out 路径。
4. PASS：不只报均值；G1 保留每 run、每 pair、每 task、每 parent 与两个 seed。
5. PASS：task/parent clustered CI、Draft/Improve 分层和 drop-one-task 已预先指定。
6. PASS：checkpoint 只由 dev accuracy 正向选择；旧 test-touched checkpoint 禁用。
7. PASS：exact config、Card/run/pair overlap 与 SHA 均 fail closed。
8. PASS：split seed、训练 seed、模型矩阵、批量和阈值均在结果前固定。
9. PASS：新输出前后执行文件名和内容 credential-shape 双扫描，不打印命中内容。
10. PASS：结构阶段 CPU-only；任何 GPU 前先给精确矩阵、run 数和 GPU·时并获批。
11. PASS：结论限定为 retrospective model support，不宣称 prospective 或搜索收益。
12. PASS：每一步保存命令、环境、返回码；失败不覆盖、不续写成成功。
13. PASS：输入与 held-out 行集不可扩展/重排；结构门失败不得换 seed 或阈值追救。

## 5. GPU 结果前的工程补充冻结（2026-08-21）

本节在 GPU job=0、dev accuracy=未产生、held-out test read=0 时追加，只消除执行歧义，不改变效果门：

- component split 已按另立预注册通过，固定 train/dev/test=`4689/551/931`；train/dev SHA-256 分别为
  `0ec49d76a896accf8e85a2556ca7ed12b9379b1867247d99c6be5e4c83bea98e` /
  `3b3fb53f84277e935c66d3b3d1646d7a7d33624fb916e3f9bcc15f689904cfa4`；
- 原 confirmatory launcher 漏传固定 10 steps，必须再应用
  `0002-Allow-fixed-step-critic-budget-calibration.patch`（SHA-256=
  `89d7af494e436c4d5a7ed5c4a06e43c4d012cb26c3efd3c1e9f52bf00b3bd641`）；当前验证 overlay commit=
  `e740bab3524248f8175ec27dcd7e034515ef5bc5`；
- 还必须应用 timing-only 补丁 `0003-Record-critic-wall-clock-receipts.patch`（SHA-256=
  `a4146bdc6ef3123e3b88a3b909352dd40db3cff992503919d4207c1756313f67`），最终训练 source commit=
  `51c7f480a844364a91cf1ee4ebd9dac18f6bb832`；五个事件固定为 train begin、optimizer step 1、optimizer
  step 10、dev complete、train end，非 world-process-zero 不输出；
- `head_frac=0.25` 原是该精确源码的默认值，现显式冻结；`eval_on_start=false`，故只允许 step 10 一次 dev
  eval。其他未单列 TrainingArguments 继承上述 pinned source，并由 checkpoint metadata/state 留据；
- 模型固定为 `Qwen/Qwen3-1.7B-Base` revision
  `ea980cb0a6c2ae4b936e82123acc929f1cec04c1`；仓库相对文件 manifest SHA-256=
  `ceb388235719297e3647478ad2d96486a41d1f84e4c3fd8301c4772d6840e148`；只允许本地离线快照，不得在 job
  内浮动下载 `main`；
- 运行包必须把 Triton/Torch extension cache 放在 node-local scratch，记录两个 GPU UUID、5 秒遥测、GNU time、
  全部软件版本，并由独立 postflight 强制唯一 `checkpoint-10`、唯一 step-10 dev eval 和有限指标；
- 当前账号缺少 `zliang_gpu` QoS，两个 `sbatch --test-only` 均失败；这不是训练失败，且没有提交任何 job。
  只有精确 4 GPU·h 上限获批且授权提交者可用后才允许运行。
