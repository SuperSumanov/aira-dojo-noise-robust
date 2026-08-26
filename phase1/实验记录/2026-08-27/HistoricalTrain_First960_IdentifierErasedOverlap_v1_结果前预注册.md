# Historical train ↔ first-960 identifier-erased overlap v1：结果前预注册

冻结时间：2026-08-27（香港时间），在任何真实 historical↔prospective identifier-erased similarity、candidate、edge、
component 或 gate 结果被计算前。当前只运行过 synthetic/adversarial fixtures：alpha-renaming 正控、结构无关负控、
producer/verifier 表示一致性、prefix join↔brute-force。既有 raw/token lexical overlap 结果已知为 0 条跨历史→前瞻边，
因此本项不是 blind replication，而是预先声明的更强表示审计。

## 1. 问题与相关工作边界

问题：历史 v11 critic-train endpoints 与 chronological provisional first-960 prefix 是否存在通过重命名 identifiers、改变
string/number literals 即可掩盖的高相似代码链接？

代码去重及其对 ML 评估的影响已有成熟工作：Allamanis 证明重复可显著夸大 code-ML 指标；The Stack 发布了
near-deduplicated code corpus；Yu et al. 通过 identifier abstraction 改进 clone benchmark；Krinke 与
Ragkhitwetsagul 又警告不能把 syntactic clone benchmark 当 semantic ground truth。因此本项不主张新 clone detector，
也不把抽象后相似称为语义等价。当前检索未发现与“历史 critic train ↔ 时间冻结 MLE-agent search-tree cohort，并按
physical run/task/component 分层且 outcome-blind”完全相同的机器审计；该判断只用于定位 benchmark-integrity 缺口，
不是 novelty 证明。

- Allamanis (2019): https://arxiv.org/abs/1812.06469
- The Stack: https://arxiv.org/abs/2211.15533
- Yu et al., TOSEM: https://dl.acm.org/doi/10.1145/3502852
- Krinke & Ragkhitwetsagul (2025): https://arxiv.org/abs/2505.04311

## 2. 固定人口与输入

- 历史侧仍为 v11 b0/b1/b2 全部 `intask_split=train`：5,816 rows、5,519 unique endpoints、333 runs、23 tasks、
  2,302 parents；三份 normalized-LF SHA 与 305,750,663-byte cards SHA 沿用已公开 schema，不改人口。
- 前瞻侧固定为运行时 `LATEST` 所指 immutable snapshot 的 chronological first-960 prefix；本次 provisional 基线预期为
  snapshot `8579d7cd...d9248`、366 runs、10,683 endpoints、closure=false。若正式运行前 LATEST 已变化，则只能用新的
  immutable snapshot 跑完整协议，并明确该 commit 预注册发生在结果前；不得回选结果更好的 snapshot。
- 只读 identity/run/task/parent/code 与 snapshot-bound blind manifests。历史 JSON 虽含回顾性字段，但不使用其
  label/observation；前瞻 label/outcome/prediction/effect/utility 均禁止打开。

## 3. 固定表示

表示名：`python_token_identifier_erased_v1`。

1. 使用 Python `tokenize.generate_tokens`；tokenization 抛出 `IndentationError`、`SyntaxError` 或 `TokenError` 时该 endpoint
   计入 coverage failure，不删除人口。
2. 删除 ENCODING、COMMENT、NL、NEWLINE、INDENT、DEDENT、ENDMARKER。
3. hard Python keywords 原样保留；其余所有 NAME→`<IDENT>`。soft keywords 不单独保留。
4. NUMBER→`<NUMBER>`，STRING（含 f-string 整体 token）→`<STRING>`；OP 原样保留。
5. 空白 ERRORTOKEN 删除；其他未分类 token 写为 `TOK_NAME:原字符`。
6. 连续 5-token shingles 取 set，每个 shingle 用 BLAKE2b-128；少于 20 个 distinct shingles 计 coverage failure。

该表示旨在检测 Type-2 与部分 Type-3 syntactic clones；因为它抹去 API、列名和变量名，可能制造结构性假阳性。此风险
不能靠结果后改成“保留属性名/库名”来 rescue。

## 4. 固定 join、阈值与结果输出

- primary Jaccard=`17/20=0.85`；strict=`19/20=0.95` 只并列报告，不能 rescue primary。
- prefix-posting join 必须跨全部 historical×prospective 人口枚举 candidates，不能先按 task/run 过滤；最终判定使用
  整数算术，避免浮点边界。
- 固定 SHA(card_id) 排序后的 256×256 subset 必须由 join 与 brute force 得到相同 edge digest。
- 输出只含 aggregate counts/fractions、same-task/cross-task、component sizes/tasks 与 salted-free edge digest；不输出
  card/run/task/code identity 值。
- producer A/B 必须逐字节相同；不 import 新 producer 的 verifier A/B 也必须逐字节相同并复算全部 aggregates。

## 5. 预注册通过门与杀死条件

全部通过才允许写“在固定 identifier-erased 定义下，未发现足以威胁该 cohort 的历史→前瞻高相似泄漏”：

1. historical fingerprint coverage≥0.99；
2. prospective fingerprint coverage≥0.99；
3. prospective affected endpoints fraction≤0.01；
4. cross-task prospective affected endpoints fraction≤0.005；
5. size≥10 endpoints 且跨≥3 tasks 的 component 数=0；
6. 256×256 join/brute-force edge digest 完全一致；
7. producer/verifier 的 candidate count、primary/strict aggregates 与 edge digests 完全一致。

任一门失败，不得改 tokenizer、keyword policy、5-gram、20-shingle、0.85、task/run/endpoint 人口或挑 snapshot；如实报告
失败并只允许另开独立探索协议。当前 366/960、closure=false；即使通过，first-960+独立 accrual closure 后仍须原协议
重跑，当前结果只能称 provisional。

## 6. 13 项 pre-flight

1. **方向**：Decision Corpus + Predictor Benchmark + Audit Protocol；不恢复 HCE/多保真/probe/score-channel。PASS。
2. **问题**：identifier/literal abstraction 后的历史→未来高相似链接。PASS。
3. **人口**：历史 5,519 endpoints 与 chronological first-960 prefix 固定，不按结果删样本。PASS。
4. **输入**：hash-bound pair/cards/snapshot/blind manifests；不读 label/outcome/prediction。PASS。
5. **表示**：token policy、5-gram、BLAKE2b-128、20-shingle 在结果前冻结。PASS。
6. **阈值**：0.85 primary、0.95 strict；strict/subset 不能 rescue。PASS。
7. **正负控**：alpha-renaming/literal-change 必须 Jaccard=1；结构无关 fixture 必须低于 0.85。PASS。
8. **独立性**：producer 与 verifier 使用各自 tokenizer/shingler 和不同 join core；verifier 不 import 新 producer。PASS。
9. **随机性**：无采样；PYTHONHASHSEED 不影响结果。PASS。
10. **推断**：确定性 gate，不报告 p 值或模型 effect。PASS。
11. **资源**：CPU-only，预期小于 15 分钟；GPU/API/model-fit/base-update=0/0/0/0。PASS。
12. **安全**：fresh exact-commit worktree、strace forbidden-open audit、boundary-aware credential scan。PASS。
13. **晋升**：synthetic tests、producer/verifier A/B、全套测试、manifest 全通过才发布；否则无 COMPLETE。PASS。

## 7. 允许与禁止的结论

若全门通过，允许写：在固定且较激进的 identifier/literal-erased syntactic representation 下，历史 critic-train 与当前
chronological future prefix 的高相似链接低于预注册泄漏门。

禁止写：没有 semantic clones、没有 pretraining contamination、所有代码独立、critic 没有记忆、predictor effect 有效，
或当前 provisional 结果等同最终 first-960 closure 结果。
