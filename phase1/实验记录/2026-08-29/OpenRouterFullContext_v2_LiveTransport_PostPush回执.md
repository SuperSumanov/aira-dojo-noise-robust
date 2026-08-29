# OpenRouter Full-Context v2：公开提交后的 Live Transport 独立复验回执

日期：2026-08-29（Asia/Hong_Kong）

主线：Decision Corpus + Predictor Benchmark + Audit Protocol

裁决：`POSTPUSH_IMPLEMENTATION_VERIFIED_LIVE_BLOCKED_ON_SAFE_CREDENTIAL_INSTALLATION`

## 1. 复验对象

- 公开提交：`69aa57acba50d298e20b222cd27ad8ee72a03d3d`
- fresh detached 根：`/research/d7/spc/yzyang4/openrouter-full-context-live-v2/postpush-69aa57a-r1`
- panel/protocol/representation SHA-256：
  `a9d9f1df5a7a9aef2ba14682eb0514849ec8aba9abcc9dda69101babb7ff6be1` /
  `56a33c2409fd1cd317df948577bacb769f6bf61c08dd748f38b2e7c62e727a29` /
  `63e8acc446417ee8fab51dabcdc296a8d3b38412900a7eb6152f96d5f592cae3`
- hardening/runner/analyzer/launch receipt SHA-256：
  `01af5ff7656fe4131539729efa28383c45480b8ddc5b20dbfcddabc217eb5d60` /
  `1c7da71778dcbe1ec2037fc0596a6bc1af612bceaf4cea7e9e253eb9d0efc9a5` /
  `64ac3dbefb91ee4e39f4c1eb6604ad040113dd4e83458c37e7309ed9c82d7260` /
  `d3c58c4968ee37e8493ada9eedaff9c9826c980c67b047de62586337d9c8433a`

复验从已推送的公开 commit 建立新 worktree，没有使用本地 overlay。worktree HEAD、clean status、冻结 panel mode、六份核心 SHA 与预检包逐项验证后才运行测试。

## 2. 结果

- 预检包：9/9 成员哈希通过，失败 0
- focused tests：`18 passed in 1.87s`
- dry-run：64 requests；请求字节 min/max/total=`18192/46395/2035592`；network syscall hits=0
- mock：intent/raw/parsed=`64/64/64`；network syscall hits=0；attempt-one 与 single-provider gates 通过
- deterministic random mock 的 reliability 总门为 FAIL，符合攻击测试预期，说明门槛不是空泛条件；其伪 accuracy 不是科学结果、也未用于模型选择
- 缺失凭据攻击：`rc=1`、network hits=0、raw/intent 均未创建、missing-key gate hits=1
- 当前提交 changed files=18；credential filename/blob hits=`0/0`
- 实际 live API calls/GPU jobs/model fits/base-model updates=`0/0/0/0`
- prospective first-960、Target-300、Target-522 values 与 search utility 均未读取

公开最小回执包：`phase1/results/openrouter_full_context_live_v2_postpush_20260829_69aa57a/`。

## 3. 资源纪律事故与处置

在公开提交前曾误把完整测试集无边界地跑在 login node：约 10 分钟内观察到约 30 个 CPU threads、累计约 4 小时 47 分 CPU time。发现后以温和中断停止；该次运行没有科学输出。

post-push 没有重复这一错误，而是执行与本提交直接相关的 focused tests、预检包核验、dry/mock/analyzer 和缺失凭据攻击。后续若确需全套测试，只能限制线程与 wall time，或申请合适的 CPU 调度资源；不得在 login node 再跑无界 full suite。

## 4. 当前 blocker

远端 mode-0600 `.env` 仍未出现 `OPENROUTER_API_KEY` 变量。聊天中的明文凭据没有经命令、标准输入、日志、本地文件或 Git 传输。只有用户或学长直接完成远端凭据安装后，才能先做不回显值的 account/catalog/privacy readiness，再启动已批准的 64-call smoke。

smoke 即使通过，也不自动授权 512-call full；它只建立历史 panel 上 transport/reliability 可用性与描述性 evaluator 结果，不能直接推出 predictor scaling、label efficiency 或 search utility。
