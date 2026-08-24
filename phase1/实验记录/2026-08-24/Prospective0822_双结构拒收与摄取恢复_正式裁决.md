# Prospective 0822 双结构拒收、摄取恢复与双 cohort 正式裁决

日期：2026-08-24
状态：`INTAKE_RECOVERED_BOTH_COHORTS_COLLECTING_OUTCOME_BLIND`

## 1. 裁决摘要

0822 被观察到的 8 个 archive 已全部得到 outcome-blind、整包级裁决：

- 6 个 archive 已完整进入 append-only intake：`alaska2-image-steganalysis`、
  `billion-word-imputation`、`cdiscount-image-classification-challenge`、`lmsys-chatbot-arena`、
  `osic-pulmonary-fibrosis-progression`、`uw-madison-gi-tract-image-segmentation`；
- `multi-modal-gesture-recognition-8seeds.tar.gz` 因 4/4 checkpoint journal 的 competition identity
  cardinality 均为 0 而精确拒收；
- `AI4Code-8seeds.tar.gz` 因 discovered roots=4、checkpoint journals=0、live-only roots=4 而使用另一条
  独立 reason 精确拒收。

截至 `2026-08-24T10:59:46Z`，新 monitor 已连续两轮返回：
`archives=212, baseline=128, ready=0, rejected=10, transactions=74, outcomes_read=false`。因此当前没有
未决的稳定 archive，也没有由未知头部归档阻塞后续摄取。这里的 “settled” 只表示 accepted 或精确结构拒收，
不表示读过 outcome。

两个冻结人口必须继续分开：

| 人口 | 当前状态 | 当前支持 | 仍缺 | 当前允许用途 |
|---|---|---:|---:|---|
| first-960 + accrual closure | `PROSPECTIVE_COHORT_COLLECTING` | 328 physical runs | 632 runs + 独立 closure | fixed-scorer critic 时间外确认 |
| target-300 identity cohort | `FUTURE_COHORT_COLLECTING` | 53 physical runs | 247 runs，达到边界时保留完整 archive overshoot | score-channel dual-truth 支持审计与 pre-truth prediction escrow |

53/300 是从旧 33-run 前缀向前追加的合法数据进展，不是 accuracy、方法效果或 search utility。它不缩短
first-960，也不授权 replay/GPU effect experiment。

## 2. 两类结构失败不能混为一谈

### 2.1 multi-modal：checkpoint 存在，但 task identity 缺失

精确 archive binding：

- relative path：`0822/multi-modal-gesture-recognition-8seeds.tar.gz`；
- size：`276439998`；
- mtime_ns：`1787498876000000000`；
- SHA-256：`0770c9e390d24a1b27eaedd7260398260baf6e47b5ed3a3dc7e54c3e9aa564da`。

审计发现 4 个 checkpoint roots、4 个 checkpoint journals；每个 journal 都先通过 credential-shape scan，
随后才做结构 JSON 解析。四份 journal 的 task identity cardinality 全为 0，故 reason 固定为
`JOURNAL_TASK_IDENTITY_NOT_EXACTLY_ONE_WITHIN_ARCHIVE`。诊断 receipt SHA-256=
`18a68d79b7c4940ae76aefdccaf398836df33f467612a097ef66a150be60e4d4`，registry SHA-256=
`8d085fd9c195c306f2a9c01d66ad13044f44b1f182fc6170907912dbd80d344b`。

### 2.2 AI4Code：没有 checkpoint，旧审计措辞会 vacuous pass

精确 archive binding：

- relative path：`0822/AI4Code-8seeds.tar.gz`；
- size：`4286045`；
- mtime_ns：`1787498878000000000`；
- SHA-256：`c6291fe93cc2ec6ba8fff28a76ef7db77912f2d5306875280d330df7bbdc019e`。

归档有 4 个 discovered roots、55 个成员，但 checkpoint journals=0，四个 roots 都是 live-only。旧 auditor 对
0 个 journal 会输出语义上错误的 “exactly one in all journals”，虽然 intake 本身仍会因没有 physical run 而
fail closed；这不是可接受的诊断证据。修复后增加独立状态
`STRUCTURAL_NO_CHECKPOINT_REJECTION_SUPPORTED` 和 reason
`ARCHIVE_HAS_NO_CHECKPOINT_JOURNALS`，并要求 discovered roots 与 live-only accounting 非零且严格自洽。

AI4Code 的 live journal 成员没有被读取，测试 fixture 还把 live member 放成不可解码 bytes，以证明审计不依赖其
内容。诊断 receipt SHA-256=`1a7c63ff884a92fd5d86592450a512c31804a83d587c9a45bd5739ca79ef6104`，
registry SHA-256=`992d1a25267a66e161c7b2a4143c30110816011e09a3d82929f65cb8a00d33b7`。

两种拒收都绑定 exact path/size/mtime/SHA，不按任务名泛化；不从 archive 文件名补 task，不从 live journal
恢复 run，不允许部分 salvage。env、live-event 内容、task identity 值、code、stdout、grade、metric、prediction
与 outcome 均未读或未输出。

## 3. 代码、测试与失败证据

修复链为：

1. `a511cdda8f48ce0d93b23c4159548c648cb85b6d`：绑定 multi-modal 精确拒收；
2. `688f03b729921d20186641c33f478653f8d65b80`：修复 no-checkpoint vacuous audit，并给 registry/runner 增加
   独立 reason；
3. `5d0baaddca14ce6db53a43ed1976b85a8b24c9f3`：绑定 AI4Code 精确拒收并恢复 monitor。

fresh Linux exact-commit 结果：

| commit | focused | full `phase1/tests` | 真实归档检查 |
|---|---:|---:|---|
| `a511cdd` | 24 passed | 956 passed、47 warnings | multi-modal audit×2/registry×2 byte-identical |
| `688f03b` | 23 passed | 959 passed、47 warnings | AI4Code audit×2/registry×2 byte-identical |
| `5d0baad` | 28 passed | 960 passed、47 warnings | 两个 registry exact SHA loader 均通过 |

`a511cdd` 的第一次 full-suite 包装漏设数值库线程上限，约 30 个 BLAS threads；只终止了本次 pytest，失败
receipt 原样保留，随后在 `OMP/OpenBLAS/MKL/NumExpr=1` 下从头完成 956 tests。`a511cdd` monitor 随后按预期
在尚未认识的 AI4Code 结构上 fail closed，没有绕过；第一版 watchdog 又因 PID-file 建立竞态退出，失败日志保留。
修复后的 watchdog 只在 monitor 正常完成后重启，异常退出继续 fail closed。

正式成功根：

- `/research/d7/spc/yzyang4/prepush-intake-repair/a511cdd-v2`；
- `/research/d7/spc/yzyang4/prepush-no-checkpoint/688f03b-v1`；
- `/research/d7/spc/yzyang4/prepush-ai4code-registry/5d0baad-v1`；
- `/research/d7/spc/yzyang4/postpush-ai4code-registry/5d0baad-v1`。

本报告首次 commit `b03fa81ffc39a9beca7dd3925b7004fa6f10d76b` 的第一版远端验收包装在 source 集群
环境前错误开启 `set -u`，因初始 `LD_LIBRARY_PATH` 未定义而 rc=1；失败发生在 Git fetch/worktree、测试或任何
state 读取之前，回执保存在 `/research/d7/spc/yzyang4/prepush-0822-report/b03fa81-v0-failed`。只调整包装的
source 顺序后从头复验，39 focused / 960 full tests 全过，registry、first-960、target-300 与全部 formal manifest
由独立脚本重建一致；成功根为 `/research/d7/spc/yzyang4/prepush-0822-report/b03fa81-v1`，其 `SHA256SUMS`
自身 SHA-256=`ca9cad0eb6da7ecefdfe71e0a46aa44664fe7419a5f83fdbdd3a14a62caf20de`。两次均未读取 truth，
GPU/API=0/0。

## 4. first-960 当前不可变状态

当前 `LATEST` snapshot SHA-256=
`f109ac928ed076f83b651af3c4a98bccd11cf592a3c81da541f34f0d2b11d708`。accumulator summary 明确给出：

- eligible/provisional first-960 physical runs：328；
- endpoints：9,992；structural pairs：2,589；tasks：29；
- drops/accepted transactions：74；
- dominant run-task share：`0.09146341463414634`；
- closure `provided=false`，frozen runs/endpoints/pairs 均为 null；
- `label_vault_opened=false`，outcome files 与 scorer prediction files 打开列表均为空。

所以 1,500 structural-pair 支持门已经超过，不得把它当提前揭盲停止门。冻结 confirmation 仍必须等 first-960
按预注册物理时间序达到 960，并另取得 accrual-closure receipt。

## 5. target-300 正式 outcome-blind 刷新

control commit `5d0baad` 的 fresh no-smudge formal root：

`/research/d7/spc/yzyang4/score-channel-future-identity-cohort/5d0baad-f109ac928ed0-04eacf698977`

正式过程包含 focused/full tests、producer×2、独立 verifier×2、strace 文件访问审计和 append-only 前缀检查：

- focused：11 passed；full：960 passed、47 warnings；
- selected：53 physical runs、17 accepted archives、16 tasks；remaining=247；
- settled prefix：20 archives，其中 3 个结构拒收；boundary/pending head 均为 null；
- previous 33 runs / 11 archives 是当前输出的 exact prefix，`exact_prefix_survived=true`；
- producer×2 与 verifier×2 均逐字节一致；
- cohort runs SHA-256=`43dd78cf613513091f282069371633582f8a9d13a01d01f579ae915af20749a6`；
- cohort archives SHA-256=`cd5272b1133d78b1cdd153889a0993358b3e02400ecd64df6ffdd1d3d352e2ca`；
- `SHA256SUMS` 自身 SHA-256=
  `7285cc3b6b91bbfdb390d79d37c103d19f2e426628f5c5b32a4ac980d4d8ce65`。

正式 runner 已完成自己的全项校验。随后一次人工 `sha256sum -c` 因从错误 cwd 调用而只产生 relative-path
missing-file 错误；没有写入或修改 formal root。改用该 root 为工作目录重跑后，manifest 所列全部条目均为 `OK`。

blindness receipt 为：`label_vault_opened=false`、`score_or_outcome_opened=false`、
`raw_archive_payload_opened=false`、`blind_code_view_opened=false`、`truth_support_computed=false`、
`replay_submission_authorized=false`。因此本轮没有任何可报告的 score-channel 效果。

## 6. 当前运行态与学长训练边界

截至 `2026-08-24T11:00:11Z`：

- exact-commit monitor PID 1879230 与 fail-closed watchdog PID 1879524 均存活；
- monitor 使用 clean worktree
  `/research/d7/spc/yzyang4/worktrees/postpush_ai4code_registry_5d0baad_nosmudge`；
- 当前没有我方新 GPU/API/model-fit 作业；
- 学长所有的 scheduler jobs 11408/11410/11411 仍分别为 RUNNING，分配 2/2/4 GPUs；
- `dojo-reproduce` 仍停在 `62964aae03229b8ed6ac8ba5eb40d0060d543025`，
  `src/mle_critic/docs/outcomes` 尚无新的正式文档。

因此 H200 训练目前只能写成“在跑”，不能抄取中途 eval、推断 scaling、定位 checkpoint，或覆盖既有 clean
confirmation 契约。学长作业归学长所有，本轮没有取消、修改或读取其训练数据。

## 7. 后续唯一合法顺序

1. 让 first-960 monitor 继续按 6 小时稳定门与 exact archive transaction 盲摄取；未知结构继续 fail closed；
2. 每批新增 accepted transaction 后，只刷新 target-300 identity receipt，保持旧前缀逐字节一致；
3. 第一次达到 300（含完整 boundary archive overshoot）时自动生成 one-time closure anchor；
4. 在任何 truth 前运行已冻结的 component-breadth prediction escrow；
5. 再人工运行同一 selected-parent lottery 的 `y_norm` 与 official-five-decimal raw-grade 双 truth；
6. 只有各自预注册 support/effect gate 通过，才讨论 replay/orientation/power；GPU effect 仍需另报矩阵、总 runs 与
   GPU·时并获用户批准。

任何步骤都不得用当前 53 runs 提前看 truth、将 53/300 与 328/960 混池、把结构支持说成方法正结果，或用学长
当前 exploratory H200 中途状态 rescue 已关闭的同池方法线。
