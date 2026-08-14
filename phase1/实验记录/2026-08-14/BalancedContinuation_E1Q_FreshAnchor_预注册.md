# Balanced continuation E1-Q：fresh-anchor pilot 预注册

日期：2026-08-14。状态：用户已批准 E1；本文写在新 E1-Q data gate、operator API 调用、候选执行和
新 anchor 的 D_search/D_val outcome 之前。稳定主线仍是 run-clean、decision-local benchmark 与 first-960
前瞻确认；E1-Q 是并行的 gated 方法支线，不恢复旧 HCE、多保真或 probe。

## 1. 纠错边界与 estimand

旧 DeepSeek E1 因 scorer 接口和 8/8 operator 截断/格式失败而作废。旧 Qwen execution smoke 的 1/2 又被证明是
验证器错误：它把 accuracy 任务的布尔提交错误强制为浮点。immutable artifacts 在 commit
`047420c498f673ae6e302a60b1f099c1845f6f2a` 下独立重验为 2/2 合法，repair receipt SHA-256 为
`40a7f793a70d30b12ace25a8b929caf6c009df98ce045b7b50ff4bac1df05ecf`；新增执行/API/GPU/outcome 读取均为 0。

E1-Q 明确改变 operator policy，因此估计的是：

\[
V_1^{\pi_Q,\kappa}(c)=\mathbb E[U(Y_1)\mid c,\pi_Q,\kappa],
\]

其中 `π_Q` 固定为 `qwen3-coder-flash`、temperature=0、thinking=false、max output=8192、one-shot 完整脚本、
0 retry；`κ` 固定为 single RTX3090、600 秒 candidate cap、fresh workspace、public-only 容器与 pristine
D_search/D_val evaluator。结果不得与旧 DeepSeek labels 混合成无下标的节点固有价值。

## 2. outcome-blind fresh anchors

- 固定任务仍为 `spaceship-titanic` 与 `tabular-playground-series-may-2022`；任务不是按旧 gain 选择；
- 每任务从 v11 b0 train-run 的 exact-two parent 中，按 `(run_id,parent_id)` 排序取第一个合格项；
- 必须排除旧 E1 两个 physical runs 和旧 anchors。旧 identity-only receipt SHA-256 固定为
  `26d018455fb1a9fe2037f4ad96a6a3d7bfa4299ae3a82236eb48e24e89f795af`；
- selected endpoint/run 对论文 frozen b0/b1/b2 为零交集；只读 frozen identity，不读 winner/gap/outcome；
- cards、hold、decision-train、frozen identities、选择结果、代码 vault 与 split 全部 hash-lock；
- D_test、first-960/prospective outcome 永不读取。旧 anchor 的 aggregate 诊断不参与新 anchor 排序。

## 3. 冻结资源矩阵

`2 tasks × 1 anchor/task × 2 siblings × K=2 replicates × H=1`：

- 8 rollout jobs；每 job 先执行一次 warm code，再执行恰好一次 Qwen continuation，共 16 candidate executions；
- 8 operator API calls，0 semantic/SDK retry，0 replacement；
- 每 job 1×RTX3090、6 CPU、40 分钟 Slurm cap；candidate 600 秒硬 cap；
- candidate cap 的绝对上界 `16×600/3600 = 2.6666666666666665 GPU·h`；沿用含调度/evaluator 的计划
  `3.24 GPU·h`；array concurrency=4；
- 排除 `projgpu7,projgpu8,projgpu33,gpu36,gpu38`，QOS 最多 4 jobs/8 GPUs；
- `.env` 只在远端 mode-0600 文件中读取，candidate 使用 clean allowlist env；不把凭据写入 Git/产物。

## 4. 分阶段、不可按分数停止

stage 1 恰好是每任务一个完整 replicate block，即两个 sibling 各一次，共 4 jobs。只有四个 node-local
capability、worker、独立 verifier 与 secret-scan receipt 全为 0，stage 2 才以 `afterok` 提交其余 4 jobs。
stage 1 gate 不读取 D_search/D_val 数值，不查看 gain、validity 比例或 task outcome；因此不是 optional stopping。

每个 paid action 前先落 durable intent。PENDING 且缺完整 receipt 的动作视为 ambiguous，禁止自动重跑或补样；
失败/timeout/invalid submission 是 estimand 的一部分，不 replacement。全部 8 rollout 工程门通过后，collection
verifier 才一次性打开完整 sealed D_val commitments 并构造描述性 sibling labels。

## 5. 必报量与解释门

完整报告 8 个 warm/continuation 的 execution status、submission validity、D_search/D_val utility、gain、wall/API
成本；按 task/sibling/replicate 展示，invalid/timeout 不删除。另报告每个 task 两个 replicate 对 sibling 排序是否
一致、best-of-one gain、正增益与有效 continuation 数。样本只有 2 anchors/2 tasks，不计算或宣称稳健总体效应。

- 工程完整性失败：`E1Q_INVALID_OR_INCOMPLETE`，不补跑；
- 完整但 label 全退化/无可比较支持：`E1Q_COMPLETE_NONINFORMATIVE`；
- 完整且存在非退化 matched labels：`E1Q_LABEL_FEASIBILITY_OBSERVED`，仍只是 E2 power/design 输入；
- E1-Q 无论结果如何都不自动授权 E2/E3，不允许声称 hurdle critic、balanced label 可靠性或 search utility 已通过。

## 6. 13 项长实验预检

1. estimand、旧结论撤回链和 operator-policy 下标已冻结；
2. producer/独立 verifier/状态机/scorer/Qwen task-type regression tests 先通过；
3. 两任务、fresh anchor、exact-two 支持与旧 run 排除在 outcome 前打印；
4. 8 jobs/16 executions/8 API/3.24 GPU·h/concurrency=4 明示；
5. frozen endpoint/run 零交集，D_test/first-960 不读；
6. durable intent、checkpoint/fail-closed ambiguous PENDING，不补跑；
7. source/container/Python/operator/prompt/repair receipt/data/split/evaluator/workspace 均 hash-lock；
8. assignment seed、blocked order、finite/invalid/timeout 规则固定；
9. 密钥仅远端 `.env`，逐 job 和最终 filename/content 双扫描；
10. stage 1 两任务完整 block 的 live capability/worker/verifier 门，不按 outcome 过门；
11. E1-Q 只作 feasibility/descriptive pilot，E2/E3 仍关闭；
12. shell/Slurm/capability/worker/verifier/safety 的真实 rc 分开保存；
13. exact-clean detached worktree、新 append-only roots、原子写入、recursive SHA manifest。
