# OpenRouter Full-Context v2：Live Smoke 预检、传输加固与凭据门

日期：2026-08-29（Asia/Hong_Kong）

主线：Decision Corpus + Predictor Benchmark + Audit Protocol

当前状态：`LIVE_SMOKE_AUTHORIZED_BUT_CREDENTIAL_NOT_INSTALLED_FAIL_CLOSED`

## 1. 学长最新 outcome 与本轮裁决

远端只读核验的学长 branch head 为 `30b396323f28064040bb0bdf9cccb198d676dd27`；最新 outcome 的科学提交为
`f534114e60658043c07f7a15d6440492caffc8ad`，Git blob=`7f691d9b6fa3d971bf889738fa8661694b6b0051`，
SHA-256=`17317a2d239cb862ec16d57aa0a2fa168f2c1a6cd841117950d8ee8127129ad6`。原文先在远端内存中整行
脱敏凭据，再读取科学内容；明文 token 与带权 W&B 链接均未复制、调用或写入本地/Git。

三项 NEXT 的裁决不变：

1. 全上下文强 evaluator 历史诊断与 predictor benchmark 直接相关，可以推进；
2. 微调 Qwen generator 会更新 agent 底座，仍违反项目 hard NO，不启动；
3. 3×8 H200 RL trajectory 只接受学长先行导出的脱敏材料，不访问带凭据的 W&B 链接。

用户本轮已转达专用 OpenRouter credential 与学长设置的 50 USD 账户限额，因此 smoke 成本授权成立；项目级机器预算仍用
更窄的 64 calls / scheduler stop 2 USD。credential 只允许进入远端 mode-0600 `.env`，不得进入聊天回显、命令参数、
本地文件、Git 或日志。

## 2. 固定问题、population 与矩阵

问题：在相同完整 task/resource/code 信息、相同历史 pair、A/B 与 B/A 双方向下，四个便宜/免费 evaluator 的 transport、
parse、顺序稳定性与描述性 accuracy 如何？这不是 frozen future confirmation，也不回答 search utility。

- 私有 panel SHA-256：`a9d9f1df5a7a9aef2ba14682eb0514849ec8aba9abcc9dda69101babb7ff6be1`
- 完整 panel：64 pairs、64 physical runs、29 tasks、128 endpoints；每 stratum=8、每 run≤1、每 task≤4、endpoint overlap=0
- smoke：两个 panel × 四个 gap bins 各取第一条，共 8 pairs
- 模型：DeepSeek V4 Flash 0731、GLM 5.3 Flash、Qwen3.8 Flash、Nemotron 3 Ultra free
- 每 pair 两方向；总调用：`8 × 4 × 2 = 64`
- 温度/seed：`0 / 20260829`
- 输入：完整 task description、metric direction、真实 client/hardware/two timeouts、两端完整原始 code
- 输出：不设置 `max_tokens` 或 `max_completion_tokens`；reasoning 只存远端 0600 原始文件
- 预计耗时：credential 就绪后约 30 分钟—3 小时；逐请求 600 秒 timeout 的绝对串行上界为 10 小时 40 分钟，
  append-only raw file 支持安全续跑，但 ambiguous transport failure 禁止自动 retry
- 资源：0 GPU·h、0 model fit、0 base-model update；API 调度停止 2 USD，账户外层限额 50 USD

r2 开发 preflight 曾写 10—60 分钟；它没有覆盖 64 个请求各自 600 秒的保守 envelope，故 r3 在 live 前把
30 分钟—3 小时与绝对串行上界直接写入机器可读 preflight。该勘误只修正 ETA，不改 matrix、threshold 或 scientific
estimand。

## 3. 结果前固定 gates

先判 reliability/safety，后展示 accuracy；accuracy 不决定是否进入 full：

| Gate | Paid model | Free model |
|---|---:|---:|
| parsed orientations | ≥15/16 | ≥14/16 |
| both-parsed pairs | ≥7/8 | ≥6/8 |
| order-consistent pairs | ≥6/8 | ≥5/8 |

此外 64-key 矩阵、transport error、模型漂移、context compression、ZDR/data-collection/parameter/max-price 请求合同、usage/cost
链必须全部通过；四模型全部通过，不允许结果后挑模型、任务、panel 或 gap 桶。smoke PASS 也不自动授权 full，full 须新 launch
receipt。

## 4. live transport 加固

parent protocol/amendment SHA-256=`56a33c2409fd1cd317df948577bacb769f6bf61c08dd748f38b2e7c62e727a29` /
`63e8acc446417ee8fab51dabcdc296a8d3b38412900a7eb6152f96d5f592cae3`。

新增冻结材料：

- hardening：`openrouter_full_context_live_hardening_v2.json`
- runner：`openrouter_full_context_live_v2.py`
- aggregate analyzer：`analyze_openrouter_full_context_smoke_v2.py`
- launch receipt：`openrouter_full_context_smoke_launch_receipt_v2.json`
- synthetic/attack tests：`test_openrouter_full_context_live_v2.py`

exact SHA-256：hardening=`01af5ff7656fe4131539729efa28383c45480b8ddc5b20dbfcddabc217eb5d60`，
runner=`1c7da71778dcbe1ec2037fc0596a6bc1af612bceaf4cea7e9e253eb9d0efc9a5`，
analyzer=`64ac3dbefb91ee4e39f4c1eb6604ad040113dd4e83458c37e7309ed9c82d7260`。

hardening 在原 prompt 与 panel 不变的前提下增加：

1. 每请求 `zdr=true`、`data_collection=deny`、`require_parameters=true`、`sort=price`、`allow_fallbacks=false`；router attempt
   必须恰为 1，同一模型的 16 个方向响应必须来自同一 selected provider；
2. 每模型按 2026-08-29 官方 catalog 价格设置 `provider.max_price`；
3. 开启 `X-OpenRouter-Metadata: enabled`，要求 requested/response/selected endpoint model 不漂移；
4. 任何 router `context_compression` stage 直接失败；
5. 发请求前用“request UTF-8 bytes 作为 input-token 上界 + max(catalog context length, max completion)”计算单 call 最大费用，要求
   `cumulative + upper_bound ≤ 2 USD`，不允许单 call 越过调度停止线；
6. launch receipt、protocol、representation、panel、runner 与模型顺序全部 exact-SHA 绑定；先核 receipt，后读环境变量；
7. 每次调用前先把不含 prompt/结果的 intent 以 mode-0600 落盘并 `fsync`，随后才允许发请求；raw 也逐条 `fsync`。
   只有 intent/raw 数量相等、逐项构成冻结计划的 exact prefix、且每条原始响应可重新推出相同 route/pick/cost 时才允许续跑；
   launch receipt SHA 写入每条 intent/raw，pending intent 或失败记录一律视为调用状态不明并禁止 retry；
8. aggregate analyzer 不信任 runner 写下的 audit 字段，而从 private raw response 独立重算 model/endpoint/compression、usage/
   cost、final pick 与 correctness；stdout 只含 aggregate。

OpenRouter 官方文档确认 `zdr` 只路由到零保留 endpoint，`data_collection=deny` 排除收集数据的 provider；`max_price`
按每百万 token 限制可接受 provider 价格；router metadata 可暴露实际 selected endpoint 与 context-compression pipeline。
直接来源：<https://openrouter.ai/docs/guides/routing/provider-selection>、
<https://openrouter.ai/docs/guides/features/router-metadata>。

2026-08-29T03:16:17Z 的无认证 public endpoint census 显示四个 canonical model 分别暴露 `29/20/1/3` 个 endpoint；
DeepSeek/GLM 的 endpoint completion cap 上限均可到 `1179648`，高于部分 model snapshot。public response 的 data-policy 字段
为空，因此该 census **不能**证明 ZDR，只用于结果前发现 provider-mixing 与费用上界风险；privacy 仍必须由 live 请求合同和
router metadata 逐调用证明。aggregate receipt 见安全包内 `public_endpoint_census_summary.txt`。

## 5. development 验证

权威远端根：`/research/d7/spc/yzyang4/openrouter-full-context-live-v2/dev-candidate-01af-1c7d-r5`

- r1：fresh worktree 在任何测试/请求前因既有 `pairgraph_v11` LFS object 404 中止；原样保留
- r2：只加 `GIT_LFS_SKIP_SMUDGE=1`；本实验使用现成、SHA 精确的私有 panel，不读取该缺失对象
- r2 在任何 live 前的复审发现 ambiguous resume 与 analyzer trust 两个缺口，故其代码/包被 supersede；r3 加入上述 intent 与
  independent recomputation，不改 scientific panel/prompt/model/accuracy gate
- r3 的 public endpoint census 又发现 DeepSeek/GLM 可在多个 endpoint 间负载均衡，且 endpoint completion cap 可高于模型
  快照；故 live 前继续 supersede 为 r4 的 price-sort/no-fallback 与 context-cap 费用上界，不改科学 panel/prompt/model/gate
- r4 的 provenance 复审发现 private rows 尚未直接绑定 launch receipt SHA；r5 在任何 live 前补齐，并让 aggregate analysis
  输出 runner/analyzer/receipt/intent 四个 SHA，不改科学 panel/prompt/model/gate
- focused tests：`18 passed in 2.04s`
- dry-run：64/64 requests；request bytes min/max/total=`18192/46395/2035592`；privacy exact、completion cap omitted
- mock：64/64 intent、64/64 raw、64/64 parsed、0 network；attempt-one 与 single-provider gates 均过；随机 mock 被固定顺序门
  裁为 FAIL，证明 gate 非空泛
- dry/mock network syscall hits=`0`；credential-shape hits=`0`
- 有效 launch receipt + 缺 key 攻击：`rc=1`、network hits=`0`、raw 与 intent 均不存在、missing-key gate hit=`1`
- development 实际 live calls/GPU/model fits/base updates=`0/0/0/0`

公开安全包：`phase1/results/openrouter_full_context_live_v2_preflight_20260829_01af5ff/`；mock accuracy 是固定哈希伪响应的
synthetic 非空泛测试，不是科学结果，也未用于任何模型选择。

## 6. 当前唯一 blocker 与下一动作

远端 `/research/d7/spc/yzyang4/aira-dojo/.env` 存在且 mode=600，但只核变量名后确认
`OPENROUTER_API_KEY` 尚不存在，source 后环境变量也为空。因此 live 必须保持 fail-closed；不能把用户聊天中的明文值重新放进
tool command 或日志来“方便安装”。

credential 由用户或学长直接写入该远端 0600 `.env` 后，先运行不回显 key 的 account-status 与 catalog/privacy readiness
门，再从公开 commit 的 fresh detached worktree执行 64-call smoke。未通过 smoke 时停止；不得自动进入 512-call full。

## 7. 科学边界

即使未来 smoke PASS，也只说明历史平衡 panel 上 evaluator 的完整上下文 transport/reliability 可用，并给出描述性 accuracy。
它不证明 predictor scaling、label efficiency、search utility 或 generator 改善。真正正主张仍需把 evaluator 接入结果前冻结的
label-allocation policy，并在未触碰的 future/run-disjoint graph 上确认。
