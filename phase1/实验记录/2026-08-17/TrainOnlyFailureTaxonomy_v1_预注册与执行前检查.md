# Train-only Failure Taxonomy v1：预注册与执行前检查

日期：2026-08-17。状态：`NOT RUN`。本文件冻结在读取 691 个 train execution-error nodes 的
`term_out` 之前。当前 score-channel 主实验、138/150 gate 和前瞻 vault 均不改变。

## 1. 唯一问题

训练侧 missing sibling 中已经确认的 691 个 execution errors，是否有足够多能被固定、机械且不泄露原文的
failure family 分类，从而支持 evaluator-verified failure-memory 数据资产？这不是 contract/memory 方法效果实验。

## 2. 锁定输入与安全顺序

- status registry 固定为既有 producer `per_child.jsonl`，SHA256=
  `bfb9870d83c50ef2d06bf2d374fc9f9213f41665f4cebeab7ab31837bcfde0d2`；
- 只选择 `role=train`、`UNIQUE_NODE_RECOVERED`、`EXECUTION_ERROR`、`parent_match=true` 的 691 nodes；
- roots 与 8 月 15 日 status audit 完全相同，不新增 root；
- 先以锁定 journal SHA 找目标文件，再对完整 bytes 做 credential scan；命中即整 journal skip，绝不 JSON parse；
- 通过后只读目标 node 的 `exit_code` 与 `term_out`；不读 code、numeric grade、pair orientation、frozen/extension
  target、env 或 tar 其他 member；
- 输出只含固定 category/rule ID、diagnostic 是否存在、byte count 与 SHA256；永不输出原始 diagnostic。

## 3. 固定 taxonomy 与优先级

按以下优先级首次命中即停止：

1. `ARTIFACT_OUTPUT_CONTRACT`：submission/sample-submission 与 missing/invalid/column/schema/shape 的近邻组合；
2. `RESOURCE_OOM`；3. `RESOURCE_TIMEOUT`；4. `DEPENDENCY_IMPORT`；5. `PYTHON_SYNTAX`；
6. `FILESYSTEM_INPUT_PATH`；7. `LIBRARY_API_ATTRIBUTE`；8. `DATA_SCHEMA_SHAPE_TYPE`；
9. `PROCESS_SIGNAL`：exit code `-15/-9/137/143`；10. `NO_DIAGNOSTIC_TEXT`；
11. `OTHER_TRACEBACK`；12. `NON_TRACEBACK_TEXT`。

结果后不得重排优先级、增加正则或把 broad `ValueError` 单独解释成 artifact contract failure。
`contract_related` 只取第 1 与第 8 类，并且仍只作描述，不作因果归因。

## 4. 冻结资格门

全部满足才允许 `VERIFIED_STRUCTURED_FAILURE_MEMORY_SUPPORT`：

- target node refind rate >=0.95；
- diagnostic text present share >=0.50；
- structured category share >=0.50；structured 定义为前 9 类；
- structured failures 覆盖至少 10 个任务，且 dominant task share <=0.50；
- credential-shaped target journal SHA 数=0。

通过只说明 failure-memory 数据资产有支持；不说明 contract prompt、retrieval 或搜索收益有效。

## 5. 十三项执行前检查

1. Goal：691 个 train execution errors 的机械 taxonomy 支持度。
2. Context：v11 source-opportunity status registry 与同一 8 个 provenance roots。
3. Constraint：train-only；不接触 frozen/extension targets 或前瞻 cohort。
4. Credential：整 journal scan-before-parse；命中即 skip。
5. Inputs：固定 status SHA、target count、source commit、root aliases。
6. Outcome：只读 exit code/term_out；不读 grade magnitude 或代码。
7. Output：无原始文本，只含类别、长度和 hash。
8. Priority：固定 first-match taxonomy；无结果后加规则。
9. Controls：synthetic 12 类正控、credential negative control、两输出目录逐字节一致。
10. Statistics：报告全体和逐任务计数、share 与 dominant-task；不只报均值。
11. Verification：正式执行双跑逐字节一致；完整测试；若过门再补不 import producer 的 verifier。
12. Resources：CPU-only，预计每次 <10 分钟；GPU=0、API=0、底座更新=0。
13. Stop：任一输入 SHA、target count、credential 或结构门失败即停止；不打开其他 root 补结果。
