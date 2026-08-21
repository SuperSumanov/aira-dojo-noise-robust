# Senior Augmented 真实 Batch 身份恢复：S0 正式裁决与 Source 修复清单

日期：2026-08-21。正式状态：`IDENTITY_UNAVAILABLE`。这是 provenance/identity 资格失败，**不是** critic
效果为负；按结果前冻结协议，S1 train-only 效果阶段不得启动。

## 1. 正式结果

精确 source commit=`a466888246ec606816486c164fbf24b7e4da7114`。146 个固定 source archives 共含
12,034 个 member headers、675 个 checkpoint journal headers。676 个匿名 physical runs 的精确 tar-header join 为：

- unique=636；ambiguous=32；missing=8；archive scan errors=2；
- 13,520 个结构 pair 中 identity incomplete=1,058；
- 身份完整部分的 cross-true-batch=0、task mismatch=0；
- 所有 input count 精确复现上游，原始 test 没有参与 role allocation。

预注册要求每个 run 唯一、每个 pair 身份完整且 source archive error=0，不能在结果后只过滤 clean subset；所以
`identity_criteria` 未全过，程序没有打开 pair orientation、numeric grade、raw code 或 frozen-test effect。

## 2. 条件支持规模：正面但不是效果结论

对已能识别的 true batches，固定 task-stratified 20% experiment-dev 规则给出：

- experiment-closed train=6,885 pairs / 80 experiments；
- experiment-closed dev=1,429 pairs / 17 experiments；
- train/dev 均覆盖 15 tasks，dev dominant task share=0.1357592722；
- 12 个 dev tasks 各有至少 20 pairs；train/dev experiment overlap=0；
- excluded low-support train pairs=2,752；
- 原始 test 有 87 个 experiments，其中 49 个与 train role、11 个与 dev role 重叠。

因此九项 support criteria 全过。可允许的正面表述只有：**现有 augmented corpus 的规模与任务分布足以承载
experiment-closed train/dev 研究，真正的瓶颈是 source provenance，而不是样本量。** 原 test 与 train/dev 的
experiment 重叠说明旧 run split 并非 experiment-closed；它不自动等于标签泄漏，也不允许追认现有 scaling 曲线。

## 3. 身份失败的精确来源

### 3.1 缺失的 8 个 runs

8 个 missing runs 全属于 `leaf-classification`。source 侧存在两个可复核的复制错误：

- `0811/leaf-classification-8seeds.tar.gz` 与同日
  `tabular-playground-series-dec-2021-4seeds.tar.gz` 的 SHA256 都是
  `95c3ae8267c39662d2e2231539339b64b3c5d2194c14ae8f6a15ac8b48c93f28`；
- `0812/leaf-classification-8seeds.tar.gz` 与同日 tabular tar 的 SHA256 都是
  `4da282f301dc75e50e8536a3d06e88b7261e9ab680ebc866020c119a5a8ed1d5`。

两个 leaf 文件的 header 实际列出 tabular run directories，因而不能恢复 leaf 的 8 个 run 身份。

### 3.2 歧义的 32 个 runs

ambiguous runs 按 task 为：`learning-agency-lab-automated-essay-scoring-2`=16、
`nomad2018-predict-transparent-conductors`=8、`petfinder-pawpularity-score`=4、
`us-patent-phrase-to-phrase-matching`=4。完整 source run basename 在多个 source batch/date 中出现；匿名 run ID
尾部日期来自 run launch time，不是权威 source-directory date，因此 S0 不得按日期猜唯一来源。

### 3.3 两个 archive errors

- `0730/tabular-playground-series-dec-2021-4seeds.tar.gz` 含 `workspace_agent/data` 指向绝对数据目录的 symlink；
  冻结协议拒绝 link member，且不提取、不跟随该链接。
- `0809/tabular-playground-series-dec-2021-4seeds.tar.gz` 的 header 中 checkpoint journal 数为 0，不能提供权威 run
  身份。

## 4. 给学长的最小修复清单

1. 从原始 batch producer 导出不可变 manifest：每行至少含匿名 `run_id`、source date、batch directory/ID、task、
   source archive SHA256；若同 basename 被复制到多个归档，另给唯一 producer-side instance ID。
2. 重新发布 0811/0812 的真实 leaf archives，或明确声明这 8 个 runs 无法恢复并在**新版本语料**中重建；不得原地
   覆盖旧 LFS object。
3. 对 0730/0809 两个 tabular archives 重新打包普通文件与 checkpoint journal，或在 provenance manifest 中给出
   可独立验证的 authoritative replacement SHA。
4. 新增语料以后让 pair/card 构建产物逐行保留 `source_batch_id` 与 source manifest revision，避免再次从 run ID
   猜 provenance。

只有新 revision 让 archive errors、missing、ambiguous 和 incomplete pairs 全为 0，才可另立新的 S0；不能覆盖本轮
裁决，也不能放宽身份门。

## 5. 复现与完整性

producer×2 和完全独立 verifier×2 均 byte-identical；verifier 独立重扫 146 archives、重连 676 runs 和 13,520
pairs、重分配 132 experiments，并确认正式状态。focused=13 passed；全部 phase tests=604 passed / 25 warnings。
result manifest、source inventory、权限与安全门全部通过；正式目录 mode=500、writable files=0、filename/credential
hits=0。单次 producer 1:56.83、max RSS=58,464KB；单次 verifier 1:56.50、max RSS=74,080KB。整个 S0 为
CPU-only、GPU=0、API=0、model fit=0、archive payload reads=0。

远端完整只读产物：
`/research/d7/spc/yzyang4/senior-true-batch-identity-support/a466888-v3`。
