# Decision Corpus Evidence Index v8：完整发布分割证书整合（结果前预注册）

冻结日期：2026-08-28。本文写于完整 v11 release→future identifier-erased 正式链仍在运行、任何该链
aggregate/classification 尚未读取时。v8 是 evidence-stack 升级，不改变 first-960、Target-300 或任何 predictor
estimand，也不授权提前揭盲、GPU、API 或模型训练。

## 1. 固定输入与已知/未知边界

1. source index 固定为 `phase1/results/decision_corpus_evidence_index_v7_20260826_a83bebf/index.json`，
   SHA-256=`d8cc9c60900ab41ff1df0e3aae3add29bbb922d5a32157957dcac5675fa31674`。v7 的撤回链、14 个
   entries 及全部 claim boundary 必须逐项继承，不得删除或放宽。
2. 已知输入是 435-run 双轴 split-integrity certificate：certificate/independent SHA-256 分别为
   `b44035bd073a83d4c57a03550db9c4b88af8afa8df95268c42f18541cdccca5c` /
   `45dc560b882b31df3564740bd619ac2c7248a9edcc19656a8ef865f0720af944`。其结果已知，不冒充新发现。
3. 未知输入是完整 v11 release（16,012 endpoints / 667 runs / 25 tasks）对固定 future `887491a...`
   （11,906 endpoints / 435 runs / 34 tasks）的正式审计。其结果前 protocol SHA-256 固定为
   `22f2d4f4853c11398429c40f91f952711ee2003bc27bec7c977726c82f0771ea`，source commit 固定为
   `ed3d2941d047e5f88a527f244ebcdc6c6cea4e43`。当前不记录、不读取任何 aggregate、link count 或 classification。

## 2. 固定 entry 与 ordered status

v8 只能在 v7 后追加两个 entry，顺序固定：

1. `physical_run_split_integrity_certificate`：绑定 future 内部 lineage-local 与 historical critic-train→future 两轴证书；
2. `complete_release_temporal_overlap_certificate`：绑定本轮完整 v11 release→future 的 producer、独立 verifier、
   result-before-independent postflight 与 immutable manifest。

v8 顶层 status 按以下顺序唯一决定，后项不得 rescue 前项：

1. 若完整 release 审计 classification=`ZERO_IDENTIFIER_ERASED_RELEASE_LINKS`，全部预注册 gate 为 true，且两套
   证书的 producer/verifier/postflight/hash/security 均通过：
   `PROVISIONAL_TEMPORAL_SPLIT_CERTIFIED_EVIDENCE_STACK_AWAITING_FIRST960`；
2. 若 classification=`LOW_IDENTIFIER_ERASED_RELEASE_OVERLAP_WITH_EXCEPTIONS` 且其全部 hard gates 仍通过：
   `PROVISIONAL_QUALIFIED_TEMPORAL_SPLIT_EVIDENCE_STACK_AWAITING_FIRST960`；
3. 其他任何情况：`TEMPORAL_SPLIT_EVIDENCE_STACK_GATE_FAIL`。

strict 0.95 sensitivity、某个子集零链接或旧 404/435 结果不得 rescue primary 0.85/full-release 失败。即使进入第 3 档，
失败 artifact 与限制仍必须进入 v8，不能退回只引用较小 critic-train 子集。

## 3. 允许与禁止的主张

若第 1 档通过，允许的最强措辞仅为：在固定 `python_token_identifier_erased_v1`、5-token shingle、Jaccard≥0.85
表示下，完整可重建 v11 release 与固定 435-run 时间前瞻 population 间未发现链接；future 内高相似链接在同一 physical
run/lineage 内。若第 2 档通过，必须报告例外规模、任务/run 范围与全部限制，不使用“零污染”措辞。

任何档位均禁止声称：semantic clone absence、未知预训练语料去污染、所有历史来源零重叠、predictor accuracy/effect、
search utility、causal independence 或 first-960 closure。12 个不可 fingerprint 的 future endpoints 及表示/阈值依赖必须
保留在正文限制中。

## 4. 正式实现与失败门

- builder A/B 独立进程且逐字节一致；non-importing verifier A/B 独立重建且逐字节一致；
- v7 source、两套证书、完整 release audit、独立 postflight、source commit、protocol 与 snapshot 全部 hash-bound；
- JSON assertion 数、entry 数、artifact 数与 bound-file 数由实现完成后机器打印，并原样写入正式报告，不心算；
- fresh detached Linux worktree，13 项预检、focused/full tests、credential filename/blob scan、manifest recheck 全部通过；
- 不读取 raw senior archives、prospective label/grade/outcome、prediction values 或 identity/code payload；
- GPU/API/model-fit/base-update=`0/0/0/0`；任何未知重复、哈希漂移、snapshot 漂移、超时或 monitor 异常均 fail closed，
  写 immutable failure receipt，不修改 population、representation、threshold 或 status 规则重跑。

v8 仍是 provisional evidence stack；只有 first-960 与独立 accrual-closure receipt 同时闭合后，才按原协议重跑并考虑
移除 `AWAITING_FIRST960`。
