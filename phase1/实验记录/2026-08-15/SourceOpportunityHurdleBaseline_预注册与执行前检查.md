# Source-opportunity scoreability→quality baseline：预注册与执行前检查

日期：2026-08-15。状态：在读取 frozen-role 候选级 scoreability、预测分数或效用结果前冻结。

本实验承接 `source-opportunity-identity-recovery-v1` 与
`source-opportunity-journal-status-v1`。它不恢复旧 HCE、多保真、probe、TD/RL 或已关闭的 critic
变体，也不把 hurdle/validity predictor 本身申报为算法 novelty。唯一问题是：在因执行失败而发生
informative censoring 的 source-incomplete sibling opportunities 上，只用执行前代码与生成元数据，
train-role 学到的 scoreability 模型能否在 untouched frozen-role 上提高“选中可评分候选”的概率；把它与
train-only conditional-quality 模型组合后，是否提高失败记为 0 的部署效用。

## 冻结输入、单位与边界

- cards：`phase1/cards_current_v11.jsonl`，SHA-256
  `6794acbf1dbc21ca75bed5899f4dd071b4b0d1a5b092c2e60bc634a8c5701b75`。
- source identity registry：
  `/research/d7/spc/yzyang4/source-identity-recovery-v11-3faf001-a1/producer/per_parent.jsonl`，SHA-256
  `b4261a4f042e92acca4a53630efe3e33ea1f2847d1a8148e9c8f18c35b447cd2`。
- missing status registry：
  `/research/d7/spc/yzyang4/source-journal-status-v11-42cb6b1-a2/producer/per_child.jsonl`，SHA-256
  `bfb9870d83c50ef2d06bf2d374fc9f9213f41665f4cebeab7ab31837bcfde0d2`。
- journals 仍只允许此前冻结的八个 extracted allowlisted roots；整份文件在 JSON parse 前做高置信
  credential scan。禁止打开 tar 其他 member、`env_variables.json`、first-960、prospective label vault 或
  frozen pair orientation。
- 统计单位为 `(role,parent_id)`。主分析只含 `source_incomplete=true`、
  `exact_identity_recoverable=true`，且 source set 中每个 child 均能唯一恢复 parent、代码与 status 的 parent。
  任一 child 未恢复或冲突即排除整个 parent，不把 unknown 猜成 failure。
- retained child 不能因“已进 cards”而直接假设成功：必须在唯一 source journal 中验证 parent、代码 SHA 与
  `exit_code==0`、official grade presence、normalization-threshold presence。missing child 的类别必须与冻结
  status registry 完全一致。

## 冻结标签、特征与模型

主标签是 `scoreable`：仅 `exit_code==0` 且 official grade 与至少一个 medal threshold 均存在时为 1；
execution error、grade absent、normalization metadata absent 与 unknown 均为 0。次标签 `exec_ok` 只作描述，
不替换主标签。部署效用定义为：scoreable child 的 card `y_norm∈[0,1]`，否则为 0。

执行前特征只允许：代码文本前 20,000 字符、代码长度/行数/import/CV/seed/ensemble/early-stop/
hyperparameter-search/augmentation/try/print/comment/显式 fold 与 epoch/GPU 与静态 leakage-risk 计数，
以及生成时已知的 task、operator、step、depth。禁止 runtime、stdout、self-report、exit status、numeric grade、
pair result 或 descendant outcome 进入特征。

固定模型如下，所有 vocabulary、scaler、encoder、权重和质量校准只在 role=train 拟合：

1. `random_expected`：逐 parent 对均匀随机选一个 source child 的解析期望，不抽单次随机样本；
2. `quality_static`：parent-equal sample weight 的固定 Ridge（`alpha=10`）预测成功候选 `y_norm`；
3. `quality_tfidf`：train-only `char_wb` 3–5 gram、`max_features=30000`、`min_df=3`、
   `sublinear_tf=true`，固定 Ridge（`alpha=10`）；
4. `scoreability_static`：相同 parent-equal weight 的 LogisticRegression（`C=1`，`max_iter=4000`）；
5. `scoreability_tfidf`：相同 train-only TF-IDF 与 LogisticRegression（`C=1`，`max_iter=4000`）；
6. `hurdle_static`：`P(scoreable|static) × clip(E[y_norm|scoreable,static],0,1)`；
7. **headline `hurdle_tfidf`**：`P(scoreable|tfidf) × clip(E[y_norm|scoreable,tfidf],0,1)`。

不按 frozen 结果选 arm、阈值、C、alpha、词表大小、ngram 或 feature subset。相同分数在 `1e-12` 内视为 tie，
指标对所有并列 argmax 候选取解析平均，禁止按真实标签破 tie。质量模型只用 train 中 scoreable candidates；
feasibility 模型只用 train candidates。每个候选训练权重为其 parent 内相应训练集合大小的倒数，使 parent 等权。

## 冻结指标、推断与裁决门

在 role=frozen 的 eligible parents 上报告：top-1 scoreability、失败记 0 的 top-1 utility、oracle utility、
random expected、parent/task/run 数、source-size 分布、每 task 方向和所有排除原因。主比较为
`hurdle_tfidf - quality_tfidf`；static 是预定 replication，不得在结果后与 headline 互换。

每个差异先形成 parent-level paired value。主区间为 task-cluster bootstrap 5,000 次、seed `20260815`；
次区间为 physical-run-cluster bootstrap；另报 parent bootstrap。支持任务定义为 frozen eligible parent 数至少 5。

在拟合前先过 construction gate：

- retained journal parent mismatch=0、retained code SHA mismatch=0、source-journal collision=0；
- train eligible parents≥350 且 tasks≥12；frozen eligible parents≥100 且 tasks≥8；
- train 与 frozen 的 exact-incomplete parent complete-status/code coverage 均≥0.60；
- train scoreability 标签必须同时有正负类，frozen 仅用于评测。

过 construction gate 后，固定三层结论：

- **方法正结论**：headline 相对 `quality_tfidf` 的 scoreability 与 utility 微平均增量均≥0.02，二者
  task-cluster 95% CI 下界均>0，且支持任务中 utility 差非负的比例≥0.60。
- **benchmark-useful feasibility signal**：`scoreability_tfidf` 相对 `random_expected` 的 scoreability
  增量≥0.03 且 task-cluster 95% CI 下界>0。它不等同于端到端方法收益。
- **仅机制/数据结果**：construction gate 通过但上述门不通过；诚实报告，不调参追正。

若 construction gate 失败，停止模型拟合并保留 coverage 结果；若 TF-IDF 数值/依赖失败，只允许修复实现并新增
回归测试，不允许改模型定义。retrospective 结果无论正负都不能替代 outcome-blind first-960 prospective utility。

## 13 项执行前检查

1. **唯一问题**：source-incomplete opportunities 上的 train→frozen scoreability→quality 部署效用。
2. **主自变量**：是否使用 train-only scoreability hurdle；headline 比较在结果前固定。
3. **公平性**：候选集、代码、质量模型、train/frozen role 和 tie 规则相同，只改变 scoreability 因子。
4. **泄漏隔离**：fit 路径断言没有 frozen label/sample weight；TF-IDF 仅 fit train 文本。
5. **后执行信号**：runtime/stdout/self-report/status/grade magnitude 不进入输入特征。
6. **完整 parent**：任一 unknown child 使整个 parent 排除；排除计数全部输出。
7. **结构完整性**：逐 child 校验 source parent；retained 再校验 journal/card code SHA。
8. **统计单位**：parent paired values；task cluster 为主，run cluster 为次，不用 child 微平均伪造样本量。
9. **任务异质性**：报告支持任务方向比例与逐任务表，不以单任务主导总体。
10. **正负控制**：random expected 为负控，oracle utility 为上界；label permutation 单元测试必须回到 chance。
11. **复现**：固定 commit、输入 SHA、Python/sklearn 版本、seed、命令、模型参数和输出 manifest。
12. **资源与安全**：CPU-only、GPU=0、API=0、底座 LLM 更新=0；journal scan-before-parse，产物再次凭据扫描。
13. **停止与失败**：一次正式 frozen 执行；不按结果换 headline/阈值/模型。失败实现和修复均保留。
