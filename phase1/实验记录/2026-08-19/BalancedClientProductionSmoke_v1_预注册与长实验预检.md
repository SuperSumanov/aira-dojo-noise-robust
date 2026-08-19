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
