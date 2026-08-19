# BalancedClientProductionSmoke v1：预注册与长实验预检

日期：2026-08-19。状态：`PREREGISTERED_NOT_SUBMITTED`。

## 目的与固定矩阵

0AY 证明现有 generator×task×environment 支持不足。先验证一个只改变 client 的 future exact-stratum 生产
smoke，防止重演历史上 `PC_CLIENT` 传入但四个 operator 没有实际切换的事故。

固定矩阵：3 clients（DeepSeek v4 Flash、Qwen3 Coder Flash、GLM-5）× Spooky Author × seed 1401，
共 3 physical runs；MCTS、operator set、任务、seed、硬件档、step limit=2、execution timeout=300 秒、
run time limit=900 秒全部相同。3×1 GPU array，Slurm `00:30:00`，硬上限 1.5 GPU·h。正式 smoke 预计
6–12 次 API 生成；另有 3 次 max_tokens=1 的 fail-closed provider probe。

remote `.env` 只 source、不复制；`logger.write_env_vars=false`。

## a1 fail-closed 与 a2 修复（结果读取前）

a1 的三家 one-token probe 和 Linux 全套 `400 passed in 33.83s` 均通过；job `11178` 的 Qwen worker
随后在真正生成调用前被 resolved-config 门拦截：旧 source pin 的 `litellm_gen2` 实际解析为
`qwen-max-latest`，与预注册的 `qwen3-coder-flash` 不符。Qwen 为 `FAILED 1:0`，其余两行立即取消。
a1 不读取或报告任何 score，只记作 source-pin 工程失败。

a2 不修改 client/task/seed/operator/budget/hardware 矩阵；只把 source 与 control 统一锁到包含正确三个
client YAML 的同一 immutable commit，并新增 production YAML 对 probe matrix 的测试。a1/a2 不拼接，
a2 仍须三行独立通过下述全部成功门才可扩展。

## a2 fail-closed 与 a3 调度修复（solver 实例化前）

a2 的同 commit 门、Linux 全套 `402 passed in 40.13s`、三家 one-token probe，以及三行 resolved config
的四 operator 核验全部通过。随后三个 worker 均在 solver/operator 实例化前失败：AIRA 的
`get_slurm_id()` 在看到 `SLURM_ARRAY_JOB_ID` 时调用 submitit `JobEnvironment()`，但本实验由原生
`sbatch --array` 提交，不存在 submitit 上下文。三行均 `FAILED 1:0`；日志只有 LiteLLM model-price GET，
没有生成调用或效果读取。

a3 的唯一变化是把 native array 改为三个普通 Slurm jobs，并以显式 `BALANCED_CLIENT_INDEX=0/1/2`
固定映射；这样 AIRA 走既有 `SLURM_JOB_ID` 分支，不修改实验代码、模型、任务、seed 或预算。新增测试禁止
launcher/worker 再使用 array。a1/a2/a3 不拼接，a3 仍须通过原始全部成功门。

## a3 最终裁决

a3 source/control=`f989b622def3c66dfa7aac6e1ccd1bc8b2a5b416`，Linux 全套
`403 passed in 36.10s`。job `11189/11190/11191` 均 `COMPLETED 0:0`，elapsed=`513/432/165`
秒。独立 verifier 连跑两次逐字节一致：3 runs / 6 journal rows、resolved/final 四 operator client 精确、
checkpoint state 与 search export/journal 一致、env dump=0、`score_fields_read=false`；verification SHA=
`1fbe1464ad47346bf1a8e5e086c62053f70d21c5c07a701069d777610340c658`。裁决为
`PASS_BALANCED_CLIENT_SMOKE`。

限定：这是生产链工程 PASS，不是效果。Qwen 行虽然 rc=0 且结构完整，但日志显示最终没有 valid solution；
后续 pilot 必须逐 client 报 valid-submission/failure rate，不能用 Slurm completion 代替解题成功。

## 成功门

三行必须全部满足：Slurm `COMPLETED 0:0`、worker rc=0；结果前 resolved config 的 analyze/debug/draft/
improve 四个 operator 均精确绑定目标 model/base URL；task/seed/step/execution/run cap 精确一致；journal 恰有
2 个 steps 且非空代码；search export/state 与 journal 一致；产物中不存在 `env_variables.json`；独立 verifier
不读取 code/stdout/secret 内容即可确认。任一失败即停止，不提交后续 12-run pilot。

## 13 项预检

1. 四 operator 从 resolved config 与最终 `dojo_config.json` 双重验证 client。
2. 先做 3 个一 token provider probe 和 2-step smoke，再允许扩大。
3. 新 seed/issue/root，无旧 pair/node/test 复用。
4. 三 client 逐行报告，不用 pooled success 掩盖单 provider 失败。
5. 本轮只有一 task，只是工程资格门，不报告科学效果。
6. 保存 manifest、resolved config、job rc、source/control commit 和 Slurm accounting。
7. 不读取 frozen/test；不建立训练集。
8. seed=1401 固定；client assignment 由 array index manifest 固定。
9. key 仅在远端 `.env`；禁 env dump；发布前仍做密钥扫描。
10. Slurm hard cap=3×0.5=1.5 GPU·h；run cap=900 秒，墙钟 30 分钟。
11. smoke 不承担功效，只验证生产路径；后续 pilot 另算 pair/run/task 支持。
12. worker 先保存真实 run rc；非零退出。
13. source/control commit、manifest 和 output root 不可变，目标存在即拒绝覆盖。
