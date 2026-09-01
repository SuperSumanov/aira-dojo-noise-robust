# Decision Corpus Data Card — Draft v0.1（2026-09-02）

> 状态：`INTERNAL_DRAFT_NOT_RELEASE_CLEARED`。本卡服从 `CURRENT_DIRECTION.md`、
> `PAPER_BLUEPRINT_DECISION_CORPUS_20260902.md` 与 Evidence Index v10。它区分已核验数据事实、前瞻封存状态和
> 尚未完成的法律/隐私发布门；不得把 draft 当最终许可意见。

## 1. Dataset summary

Decision Corpus 是从 AIRA-dojo 的真实 ML-engineering agent 搜索中重建的程序决策语料。基本对象不是线性 trajectory
step，而是带 provenance 的层级结构：

```text
archive → physical run → endpoint/card → recorded parent → sibling decision fragment
```

每张 card 描述一次 agent 候选程序及其搜索上下文；decision resources 将同一 recorded parent 下、同一 physical run
内可评分的 retained children 组成 sibling pairs/fragments。外部 pristine evaluator 的 continuous grade、
status-certified validity partial order 与 source missingness 是三类不同信息，不互相替代。

本数据集服务于执行前 predictor/critic 的训练与公平评价、搜索树数据质量研究、pair weighting/coverage/noise/cost
分析。它不更新 agent 底座，也不声称提供 agent 当时看到的完整 choice set。

## 2. Versioned releases

### 2.1 当前可逐字节重建的历史 card release

| Field | v11 value | Evidence |
|---|---:|---|
| immutable LFS batches | 29 | `phase1/corpus_releases/v11.json` |
| cards/rows | 16,012 | same |
| serialized bytes | 305,750,663 | same |
| SHA-256 | `6794acbf1dbc21ca75bed5899f4dd071b4b0d1a5b092c2e60bc634a8c5701b75` | same |
| heuristic run segments | 667 | v11 source-provenance audit |
| tasks | 25 | v11 direct-competitor/current-release audit |
| rebuild protocol | `legacy-run-id-v6-sanitized-v11` | release descriptor |

重建命令：

```bash
git lfs install --local
git lfs pull --include='phase1/cards_*.jsonl'
bash phase1/rebuild_corpus.sh v11 /tmp/cards_current_v11.jsonl
```

builder 在写出前验证每个 batch 的 rows/bytes/SHA、有序 prefix lock、run segmentation 与 release-specific taxonomy；
输出必须同时匹配 rows/bytes/SHA 才可 promote。v6--v11 已逐字节复建；v4/v5 缺失原始 payload，明确不是可复现 release。

### 2.2 v11 decision resources

v11 发布九个 decision set：`train/frozen/extension × b0/b1/b2`。新版 lineage audit 在 recorded-parent 口径下核验：

- 全九组共 8,107 行均为同一 reconstructed physical run 内的 direct siblings；
- 7,579 行属于 parent-present strict core，528 行属于 lineage-verifiable orphan-parent tier；
- 每个 budget 内 train/frozen 的 unordered pair、endpoint、parent 与 referenced physical run overlap 均为 0；
- 35/36 固定 support gates 通过；`frozen:b2` 的 maximum single-run pair share 未通过，所以不能说 all gates pass。

b0 是最容易解释的 finite numeric fragment：

| Role | pairs | parents | endpoints | runs | tasks |
|---|---:|---:|---:|---:|---:|
| train | 4,263 | 2,293 | 5,499 | 333 | 23 |
| frozen | 1,498 | 845 | 2,022 | 92 | 22 |
| extension | 136 | 114 | 239 | 15 | 10 |

这些数字属于 published labeled sibling fragment，不是完整 source choice set。source-complete parents 分别为
train/frozen/extension=`1,628/651/103`，对应 all parents=`2,293/845/114`；发布 graph 完整覆盖所有 retained finite
children，但不能恢复未 retained child 的完整 numeric outcome。

### 2.3 前瞻封存 cohort（尚未发布结果）

截至本卡时间：

- source archives=`283`；eligible physical runs=`517`；first-960 还差 `443` runs；
- fixed WL scorer 的 common support 为 13,098 endpoints、3,230 pairs；494→517 增加 23 runs、删除 0，旧行逐字节保留；
- broader eligible structural population 为 13,581 endpoints，与 13,098 scorer-common-support 是不同口径；
- labels/outcomes/prediction values/accuracy/search utility 均保持封存；1,500 pairs 只是支持门，不是 stopping rule；
- prospective labels 所在 withheld batch 在独立 release 决策前不得上传到 Git LFS。

因此本节只能证明 append-only accrual 与结构支持，不能给出 predictor 效果或 prospective generalization。

## 3. Provenance and collection

- 生产框架：`facebookresearch/aira-dojo`；固定 agent/search 生成完整 Python candidate programs。
- 原始前瞻语料由学长持续生产并上传；本项目侧负责 credential-first intake、run reconstruction、decision views、
  split、audit、prediction escrow 与 release receipts。
- v11 的 16,012 cards 中，14,339（89.5516%）可唯一映射到 592 个 source-journal SHA，覆盖 587/667 个 heuristic
  runs；5 个 heuristic runs 各合并两个真实 journal，未观察到一个 source journal 被拆到多个 heuristic runs。
- 1,673 cards 尚无 source-truth mapping；另有一个旧 journal 因 credential shape 在解析前跳过。故“未观察到
  source split”只适用于已映射部分，不能外推全语料。
- prospective producer 的 canonical config-v2 sidecar 当前仍为 0；旧 archive 禁止事后回填 exact config provenance。

## 4. Fields and information classes

v11 cards 与九个 decision JSONL 的完整字段字典已经固定在
`SCHEMA_DICTIONARY_DECISION_CORPUS_V11_20260902.md`；机器盘点与独立 verifier 对 10 个资源、24,119 行完全一致，
且不写出 source values。字典逐字段给出 type、nullable、source、decision-time availability、release class 与敏感等级，
并明确以下六类：

1. **Identifiers/provenance**：card、task、archive、physical run、recorded parent、operator/budget/config stratum。
2. **Candidate artifacts**：generated code、sanitized stdout/observation、runtime/status。
3. **Decision-time features**：执行前可得代码/结构；任何 self-report 或 execution feedback 必须标 post-execution。
4. **External labels**：pristine continuous grade、finite availability、gap/orientation。
5. **Partial-order labels**：status-certified validity edges；不得冒充 numeric grade order。
6. **Audit metadata**：source retention、clone fingerprints、cost/noise receipts、split/closure hashes。

公开 schema 不应包含 API key、cookie、authorization header、private reasoning、Kaggle raw data、用户名/邮箱或原始绝对路径。
本 schema 工作没有读取这些内容，也不替代最终 content/license scan。

## 5. Label construction and quality

- numeric truth 来自 agent 不可见的 external pristine evaluator；agent 只见执行反馈，不见 hidden labels。
- 独立 regrade 子集：207 usable cards、10 tasks、3,017 original-vs-first-repeat pair observations；raw agreement=
  `0.965860125953`，task-macro agreement=`0.980180828387`。
- transported single-label quantity 依赖 independent/exchangeable/symmetric-error 假设；不是直接测得的 universal predictor ceiling。
- 主要不确定性使用 task-cluster bootstrap，不使用 pair-i.i.d. binomial interval。
- 公开 Kaggle tasks 可能进入底座预训练；本数据集没有证明 task secrecy 或 unknown-pretraining decontamination。

## 6. Known measurement properties

- choice observability：source child-slot loss 会非线性放大 pair-capacity loss；`C(n,2)` 只是 declared capacity，不是
  agent 实际比较日志。
- pair weighting：first-240→339 中 run-level task HHI 下降但 pair-level HHI 上升；opportunity yield 解释 HHI/TV
  增量约 0.645/0.595。方向通过时序和 LOTO，幅度对一个高产率 drop 敏感。
- deployment cost：static LR/GBM/TF-IDF 在线 pair query 相对 candidate execution p50 低 4,048--6,037×；这不证明
  selector 会改善最终成绩或墙钟。
- duplicate scope：固定 token/AST normalization 下未观察到 cross-run/cross-task duplicates，但 AST coverage gate 未全过；
  不排除 fuzzy/semantic/pretraining duplication。
- archive gate：在 283-archive 状态中，14 个 structural reject events 触及 7 个 competitions；6 个仍保留 accepted
  support，唯一无支持事件链接到 zero-checkpoint archive。该 post-hoc certificate 不是独立第五项科学结果。

## 7. Intended uses

- 训练与评估独立、execution-free MLE candidate predictors/critics；
- 研究 true-sibling、parent-equal、run/task macro 与 pair-micro estimand 的差异；
- benchmark leakage、choice censoring、label repeatability、pair weighting、cost/calibration 的方法研究；
- 在保留 physical-run/config/time provenance 的前提下做 temporal transport；
- 复现 corpus rebuild、withdrawal ledger 与 independent verifier workflow。

## 8. Out-of-scope or misleading uses

- 把 decision fragment 当 agent 完整 opportunity set；
- 把 status-validity edge 当 continuous quality total order；
- 把不同 physical runs 或 root-to-leaf paths 当独立 sibling decisions；
- 用 frozen/test 行训练或周期性选择 checkpoint；
- 把 post-execution self-report 当 execution-free baseline；
- 宣称 semantic clone、pretraining contamination 或 public-task memorization 不存在；
- 用本数据证明某个 critic 已提高 end-to-end search utility；
- 在本项目中微调或 RL-finetune agent 底座 LLM。

## 9. Biases and representativeness

- tasks 来自公开 Kaggle/MLE-bench 风格问题，不代表全部 ML engineering；公开任务可能被底座预训练见过。
- generator、operator、time/hardware、失败/评分机制与任务 difficulty 共同决定哪些 cards 获得 finite label。
- run 数均衡不保证 pair 数均衡；高 branching/yield task 可主导 pair-micro。
- source retention 不完整，且部分 historical physical runs 由 heuristic segmentation 得到。
- task、run、parent、gap 与 generator/config strata 支持不均；所有结果必须同时报告 breadth、coverage 与 dominant share。
- prospective cohort 仍未闭合，不能将当前 517-run prefix 当固定最终 population。

## 10. Privacy, security, and content risks

现有流程对 archive 先做 credential-shape scan，命中则在远端内存流式脱敏后才允许读取；密钥不进本地/Git。公开前仍需
完成全量 code/stdout 的 credential、cookie、绝对路径、个人标识与 competition-data contamination 扫描。

2026-08-08 的旧 compliance 工作只对 v6 的 9,433 cards 做 prepared-data 逐字比对，发现并脱敏 19 张；当时两个图像
任务的 245 cards 未扫。v11 已增长到 16,012 cards，因此旧结果**不能**升级为 v11 全量 clean receipt。

## 11. Licensing and release status

当前许可状态是 **PARTIAL / NOT RELEASE CLEARED**：

- aira-dojo 改动代码继承上游 CC BY-NC 4.0 与 Meta attribution；
- Kaggle competition data 必须零字节分发，用户自行通过官方 prepare/API 获取并遵守 ToS/逐赛事规则；
- 22 个赛事规则的旧审计只精读 4 个，其余依赖模板/API 字段推断，必须逐项复核；
- Qwen 生成批次的 provider 输出条款与计划中的 Apache-2.0/CC-BY-4.0 数据许可兼容性尚需最终法律/机构确认；
- 需要最终 `licenses.json`（competition slug、规则 URL、审计日期、允许的衍生发布范围）与 generator/provider
  provenance table；
- 旧 compliance 文档的 novelty 段已被 ML-Agent、OpenMLE 与 mle-traj supersede，不能继续引用。

在这些门关闭前，只能发布研究代码、已审计 aggregate receipts 与明确允许的重建元数据，不能宣布完整 v11 数据集已经
法律/隐私 cleared。

## 12. Release-blocking checklist

| Gate | Status | Required closure |
|---|---|---|
| v11 16,012-card competition-data scan | BLOCKED | 对所有 prepared tasks 重跑高熵逐字扫描并独立验证 |
| credential/PII/path scan on final public fields | PARTIAL | 对精确 release candidate 做双实现零命中/脱敏 receipt |
| 逐 competition 规则审计 | BLOCKED | 22/22 rule URLs、版本日期、派生代码/score/tree 发布判断 |
| provider/model output terms by immutable batch | PARTIAL | DeepSeek/Qwen provenance 与许可兼容裁决 |
| final dataset license + upstream notices | BLOCKED | 法律/机构 review；生成 `LICENSE`, `NOTICE`, `licenses.json` |
| v11 schema dictionary | COMPLETE (SCHEMA ONLY) | 10 resources / 24,119 rows 已机器盘点并独立复核；完整 release 仍受内容/许可门阻塞 |
| Croissant/Responsible AI metadata | TODO | 从最终 schema/data card 生成并验证 |
| prospective first-960 release | SEALED | closure + one-time result protocol + outcome-independent release decision |
| v4/v5 reproducibility | PERMANENTLY UNRESOLVED | 只在找回原 payload 时可改变；否则明确排除 |

## 13. Maintenance and updates

- 新 batch 必须 append-only：先登记 immutable rows/bytes/SHA，再新增版本 descriptor；禁止改旧 registry row。
- 新 release 必须在 fresh clone/LFS pull 后逐字节 rebuild，并保存 receipt、失败链与 source commit。
- 科学 claim 由 Evidence Index 管理；reconstruction 不得重复计为独立发现。
- 发现泄漏、许可、隐私或 schema 问题时 fail-closed：保留旧版本与撤回记录，不静默覆写。
- 最终联系人、长期 host、DOI、镜像、版本弃用政策和 issue-response SLA 尚待填写。

## 14. Evidence entry points

- release descriptors：`phase1/corpus_releases/`
- current claim ledger：`phase1/results/decision_corpus_evidence_index_v10_20260902_983bdec/`
- decision audit：`phase1/results/decision_corpus_audit_v11_20260814/`
- source provenance：`phase1/results/v11_source_provenance_audit_20260814/`
- choice-fragment boundary：`phase1/results/raw_choice_set_completeness_v11_20260815_6610618/`
- label repeatability：`phase1/results/label_repeatability_v2_20260814_4e3bebe/`
- deployment cost：`phase1/results/deployment_cost_attestation_v2_20260820_c800345/`
- current paper plan：`phase1/PAPER_BLUEPRINT_DECISION_CORPUS_20260902.md`
- v11 schema dictionary：`phase1/SCHEMA_DICTIONARY_DECISION_CORPUS_V11_20260902.md`
- value-free schema inventory：`phase1/results/release_schema_inventory_v11_20260902/`
