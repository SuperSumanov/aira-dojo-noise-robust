# OpenRouter Full-Context：目录价格漂移的结果前追加式修复

日期：2026-08-30（Asia/Hong_Kong）

主线：Decision Corpus + Predictor Benchmark + Audit Protocol

状态：`CATALOG_REFRESH_FROZEN_BEFORE_ANY_LIVE_CALL_KEY_NOT_INSTALLED`

## 1. 发现与裁决

在任何真实 API 调用、intent journal 或模型响应产生前，对 OpenRouter 公共模型目录重新取证。四个冻结模型 ID 仍全部存在，
但 `deepseek/deepseek-v4-flash-0731` 的公开 prompt/completion 价格已经从旧 hardening 中的
`0.045/0.09 USD per million tokens` 变为 `0.065/0.18`。GLM、Qwen 与免费 Nemotron 的冻结价格未变。

旧 hardening 的每模型 `provider.max_price` 因而会错误拒绝 DeepSeek arm。不得直接覆盖旧冻结文件，也不得删除该模型、
放宽成无上限路由或结果后选择其余模型。本次采用 append-only 修复：保留旧 artifact 原样，新增公共目录 receipt、新 hardening
实例和新 launch receipt；科学 panel、prompt、模型顺序、双方向、reliability gates、分析和停止边界逐字段不变。

## 2. 新增冻结材料

- 公共目录 receipt：`openrouter_full_context_catalog_refresh_20260830.json`
  - SHA-256=`a534573d2a80edcef4ac0fac7ec78d7203d58fdf8fef5c13e6b0d28853873ab4`
  - 公共 HTTP response SHA-256=`4cb9dfd07b4c5741f6b3c1a3bc801b8f8fd483a421e744331da2677434b00623`
  - credential used/API calls=`false/0`
- 追加式 hardening：`openrouter_full_context_live_hardening_v2_catalog_20260830.json`
  - SHA-256=`924526a4aaa3c9f7cc4cf0126e7426d3d9d8ae3c5bf598c4869a71d70deb99d7`
  - supersedes old SHA-256=`01af5ff7656fe4131539729efa28383c45480b8ddc5b20dbfcddabc217eb5d60`
- 追加式 smoke receipt：`openrouter_full_context_smoke_launch_receipt_v2_catalog_20260830.json`
  - SHA-256=`8899c1bf5a071733dfe0a26657cc6778d6d203cd02439ea547890384cdcb7f35`
  - supersedes old SHA-256=`d3c58c4968ee37e8493ada9eedaff9c9826c980c67b047de62586337d9c8433a`

官方公共目录入口：<https://openrouter.ai/api/v1/models>。本 receipt 只保存四个冻结模型的公开 metadata、价格和能力，
不保存完整目录响应、凭据、prompt 或结果。

## 3. 不变量与验证

新测试逐字段证明以下合同与旧 hardening 相同：parent panel/representation、request/resume/cost/response hardening、smoke gates、
analysis 与 scientific boundary；授权中的 64 calls、2 USD scheduler stop、远端 mode-0600 `.env` 和禁止凭据进入命令/Git/日志
也不变。唯一模型合同差异是 DeepSeek 的两项目录价格与同一公开 receipt 对齐。

现有 runner 直接加载新 hardening 后，DeepSeek `max_price` 精确为 prompt/completion=`0.065/0.18`，并接受新 receipt 的
protocol、representation、panel、runner、analyzer、模型顺序、64 calls 与 2 USD exact-SHA 绑定。本地 focused=
`9 passed in 0.64s`；本地 full 仅因 Windows 环境没有 scipy/sklearn 而在 collection 阶段停止，未把缺依赖误报为实现失败。

远端固定 venv 的第一次 focused 因开发 launcher 漏设正式安全环境 `umask 077`，临时 private fixture 以 0644 创建并被安全门
正确拒绝；该失败回执保留。只补 `umask 077`、不改任何 tracked 文件后，在同一 detached `da6012d...9f9bd4` worktree
通过 focused/full=`9/1680 passed`，full 耗时 `100.32s`，7 个预期 changed paths；API/GPU/prospective read=`0/0/false`。

## 4. 当前 blocker 与安全边界

2026-08-30T01:41:34Z 只核变量名的远端检查确认 `.env` 存在且 mode=`600`，但 `OPENROUTER_API_KEY` 变量仍不存在；
credential value 未读、未回显，network calls=`0`。聊天中的明文凭据不得经 tool command、stdin、日志、本地文件或 Git 转存；
必须由用户或学长直接写入远端 `.env`。

变量名就绪后仍须立刻重跑 account/catalog/privacy readiness；任何目录再次漂移、provider 不满足 ZDR/deny-collection、
预算上界不闭合或 exact source 不匹配均 fail-closed。即使 64-call smoke 通过，也不自动授权 512-call full。

本次实际资源：GPU jobs/API calls/model fits/base-model updates=`0/0/0/0`。prospective first-960、Target-300、Target-522 的
label、outcome、prediction、accuracy 与 utility 均未读取。
