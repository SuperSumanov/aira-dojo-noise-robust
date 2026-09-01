# v11 Release Content Scan — 13-item Preflight（2026-09-02）

> 目标是关闭一部分数据发布阻塞，不是 predictor/scaling/effect 实验。本扫描只读历史 v11 release 与远端 prepared
> competition text；不读 first-960/Target-300/Target-522，不启动 GPU/API/model fit，也不改 immutable v11。

1. **单一问题 / estimand**：在 v11 的 `stdout_tail` 全部行窗口，以及 code 的 decoded string/bytes literal、literal
   container 和 comment 中，是否存在与对应 task prepared text 逐字相同、长度 40 bytes 且通过固定熵门的片段。
2. **输入固定**：cards rows/bytes/SHA=`16,012/305,750,663/6794acbf...1b75`；任务集合来自该文件，不接受调用方
   重选。prepared source 只接受 task 目录下固定 text suffixes；每个文件 rows 不读出，bytes/SHA 写入 private manifest，
   public 只写 manifest hash/count/bytes。
3. **当前覆盖先验**：metadata-only 检查得到 prepared text tasks=`23/25`、text bytes=`1,377,069,541`；缺失固定为
   `aptos2019-blindness-detection` 与 `histopathologic-cancer-detection`。这次最多得到 partial clearance。
4. **字段与阈值预注册**：window=`40 bytes`，minimum distinct bytes=`12`，minimum nonspace=`24`；stdout 逐窗口；
   code 只扫 literals/literal containers/comments。不得结果后换阈值或把 code coverage 写成 arbitrary-source full text。
5. **输出完整性**：public summary 必须逐 task 给 cards、candidate patterns、prepared coverage、source manifest hash、
   matched patterns、affected-card/field counts；private root mode 0700，raw patterns/matches 0600，public 不含 source values、
   card IDs、matched spans 或绝对路径。
6. **无模型训练**：critic/model fits=`0`，GPU/API/base-model update=`0/0/0`；没有 checkpoint、seed 或超参选择。
7. **数据隔离**：只读 `cards_current_v11.jsonl` 与 `/research/.../mle-bench-data/<task>/prepared`；禁止任何
   `prospective_decision_v1`、vault、prediction escrow 或 senior raw archive 路径。
8. **确定性与复核**：pattern 规则无随机性；producer A 后以 `--resume` 重算 B，public/private aggregate 必须逐字节一致；
   verifier 不导入 producer，重建 pattern sets、source manifests、affected-card aggregates，并逐 match 确认 source occurrence。
   test/producer/verifier/summary 全部固定使用项目既有 `venvs/exp/bin/python`，worktree 前必须通过 executable 与
   `import pytest` capability gate；禁止静默回退到系统 Python。
9. **安全门**：公开件必须通过 credential-shape、绝对路径、raw-span/card-ID non-emission 检查；push 前执行 staged filename
   `grep -icE 'env|key|token|secret'` 与内容扫描。任何 raw hit 只留远端只读 private root。
10. **规模 / 预算 / ETA**：一次 producer + 一次 resume replay + verifier A/B；cards=`16,012`，tasks=`25`，可扫=`23`，
    prepared text=`1,377,069,541 bytes`。预估 candidate unique-pattern 上界=`1,433,130`（stdout/code 分开计数之和，
    真正 union 只会更小）。GPU·时=`0`，付费 API=`0`；预估 wall=`15--60 min`，runner hard timeout=`4 h`，每 task
    matcher timeout=`1 h`。
11. **成功 / kill gate**：成功要求 exact cards SHA、23/25 metadata coverage、focused+full tests、全部 grep rc∈{0,1}、
    A/B byte equality、independent verifier PASS、source manifests不漂移、公开安全门全 0。parser failure、grep rc=2、timeout、
    hash drift、matched∉candidate、private mode 错、prospective path/network access 任一触发 fail-closed。
12. **结果解释**：零匹配只表示声明字段/窗口/23 tasks 下未发现逐字文本，不表示没有 semantic/paraphrase/base64/image/
    pretraining leakage；有匹配只触发 review/redaction protocol，不自动改旧 LFS batch，也不删证据。
13. **扩展与版本纪律**：v11 immutable；若需脱敏，创建 append-only sanitized successor descriptor/receipt，不静默覆盖 v11。
    只有补齐两个缺失 prepared tasks 并按同一协议复核，competition-data gate 才可能从 PARTIAL 变为 full。

正式 runner：`phase1/scripts/run_release_content_scan_v11_20260902.sh`。它必须从公开 exact commit 的 fresh no-smudge
worktree 运行，保留失败 receipt、完整日志与 private evidence，并只回传 aggregate public summary/verifier。
