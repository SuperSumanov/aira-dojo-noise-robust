# Balanced continuation：完整 synthetic worker E0 裁决

日期：2026-08-14。裁决：**`VERIFIED_FULL_SYNTHETIC_BALANCED_CONTINUATION_E0`**。

稳定论文主线仍是 run-clean、decision-local 的 MLE-agent 搜索树数据集/benchmark 与 first-960 前瞻确认。
本轮只验证 balanced continuation 的 assignment→worker→resume→workspace→独立验收闭环，不读取真实 outcome，
不构成方法正结果，也不恢复旧 HCE、多保真或 probe 路线。

## 1. 实际运行

- 精确 commit：`f7b75a5b7d353116a0ecb0ca94ed3e7ca9870585`；
- 远端 exact clean worktree：`/research/d7/spc/yzyang4/aira-dojo-e0-f7b75a5`；
- 正式 artifact：`/research/d7/spc/yzyang4/balanced-worker-e0-f7b75a5-a1`；
- 归档 tar：`/research/d7/spc/yzyang4/balanced-worker-e0-f7b75a5-a1.tar.gz`；
- tar SHA-256：`f0a5a6e61b059f48836c352461700cb6e5cf83324dadd6767a284c05615c2113`；
- focused tests：22 passed；完整 `phase1/tests`：143 passed；13 项 preflight：13 passed；
- GPU/API/Slurm job：0/0/0。

第一次 launcher 在创建 worktree、run root 或 log root 之前失败，原因为启用 `set -u` 后再 source
`env_setup.sh`，后者读取了未定义的 `LD_LIBRARY_PATH`。修复为先 source、再启用 nounset；失败文本保存在
`results/balanced_worker_e0_20260814_f7b75a5/prelaunch_failure.txt`。因此失败没有污染正式 artifact，
但仍作为实际发生的工程偏差保留。

## 2. 冻结矩阵与完整核算

E0 固定为 2 synthetic tasks × 2 anchors/task × 3 siblings × K=2 × H=2：

- rollout jobs：24；
- warm-start candidate attempts：24；
- continuation candidate attempts：48；
- candidate attempts 合计：72；
- operator calls：48；
- fresh workspace path/token：24/24，全部唯一；
- retry/replacement：0/0；
- 每个 sibling 恰好 K=2，每个 replicate block 恰好包含全部 3 个 siblings。

assignment manifest SHA-256 为
`76d72eb8ce6484850264024cc21c967b307f409bc996efff897c56907efdbb41`；independent assignment receipt
SHA-256 为 `82e30ced65906de3c3632d34d0525bcc30f1564b95b7bdfcd692e04262ad2fd6`；collection receipt
SHA-256 为 `44651fdebc5c535b61dc23a3466bf92b888fb8d73e93167a47aca64a7c835370`。顶层 manifest 对
452 个文件重算，bad=0。

synthetic backend 的 utility pattern 故意覆盖 improve→timeout→debug、invalid→debug、连续 improve 和
双失败路径。其 collection mean 仅是测试夹具的机械结果，**不得作为模型、标签或搜索性能证据**。

## 3. 本轮修复的完整性缺口

1. worker 在 parse 前检查 credential shape，并核对 assignment、contract、code vault 与 backend hash；
2. 每个 rollout 只允许全新 output dir 与全新 workspace；已有目录或 symlink 直接拒绝；
3. warm start 恰好一次，之后恰好 H 个 transition；buggy→debug，否则→improve；失败不补跑；
4. 状态先写 PENDING，再写 durable backend/code/step receipt，最后原子提升 READY；
5. resume 不只看 receipt 是否存在，还在继续执行前重验此前每一步的代码、operator、outcome、backend receipt、
   state hash chain 和 workspace 精确文件集合；缺失或篡改时不产生下一次 execution；
6. 不 import worker 的 verifier 从输入重新推导每个 step 和最终 label；集合 verifier 要求独立 assignment receipt，
   且验证 complete coverage、exact-K、block support、总尝试数、零替换以及 workspace 唯一性；
7. 51 个 CLI 进程的 rc 均即时记录，任何非零 rc 会阻止集合关门。

## 4. 严格解释与下一门

本轮证明的是执行契约可实现、可恢复且可独立验收。它没有证明：

- balanced `V_H^π` 比 historical subtree max 更可靠；
- balanced label 更可预测；
- critic 在相同真实执行预算下提高 D_val utility；
- 真实 aira-dojo workspace 和 pristine evaluator 已接入。

所以三个预注册 scientific gates 仍全部未知。下一步只允许先实现 real-backend/pristine-evaluator adapter 的
0-GPU mock 与静态安全审计；E1 的 8 jobs/16 real candidate executions/预计 3.24 GPU·时仍需新的明确批准，
E2/E3 更未授权。不得把本 E0 的 synthetic mean 写进摘要、主表或顶会把握更新。
