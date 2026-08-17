# 学长 Qwen checkpoint：冻结测试污染与方向裁决

日期：2026-08-17。裁决：原计划“复用已锁定 4B/8B checkpoint 对 v11 frozen b0/b1/b2 一次性评分”撤回。
学长日志仍可作探索性证据，但这些 checkpoint 不能作为冻结确认实验。

## 直接证据

学长分支 `dojo-reproduce` 的报告 commit 为
`7372b4eddc7dcadd84bf72edcce1daabb81d575c`，报告说明训练运行使用 commit
`ba81b102282f252e3d7f8a1374ff55b73fd740ce`，并每 10 optimizer steps 在
`decision_pairs_runsplit.jsonl` 的 test split 上评估。

当前仓库逐行 multiset 复核得到：`decision_pairs_runsplit.jsonl` 的 test 恰为 2,087 行；
`decision_clean_b0/b1/b2` 合并也恰为 2,087 行，二者 exact JSON-line multiset diff=0，且两边均有 2,087
个唯一行。因此所谓后续 frozen b0/b1/b2 并不是 checkpoint 未见测试，而是训练过程中反复查看过的同一测试集分桶。

训练配置另有方向错误：`metric_for_best_model=eval_pair_accuracy`，但
`save_strategy=best` 与 `greater_is_better=False` 同时存在，会把更低 accuracy 当成更优 checkpoint。
无论是否实际使用该错误保存的 checkpoint，频繁 test evaluation 已足以使冻结确认无效。

学长报告的数字仍诚实记录为探索性结果：decision→decision 四规模 final 均值 50.97%，value→decision
51.35%，value→value seed-7 final 均值 59.48%；没有稳定规模效应。这些数字支持“加 context/参数未救活局部
decision critic”的描述，但不支持新的 frozen confirmation。

此外，commit `7372b4e` 的 `build_cards.py` 会直接打开并 `json.load(env_variables.json)` 读取 HARDWARE。
学长 tarball 的该文件可能含 raw API key，违反本项目 scan/redact-before-parse 规则；该入口不得用于我们的
语料 ingestion，必须改为安全元数据来源或先整文件凭据扫描并拒收。

## 方向影响

1. 撤回 CURRENT_DIRECTION 较早小节中的 4B/8B one-shot support experiment；不得为“路径已给”而恢复。
2. 学长建议的 RL 不自动采用：项目 hard NO 是不微调/RL-finetune 底座 LLM，且旧 RL/TD 主线已关闭。
   若研究轻量搜索控制器，必须有新预注册、公平契约和预算批准。
3. 新 checkpoint 若要用于冻结确认，必须在任何 frozen row evaluation 前锁定，训练/选择只用 train/validation，
   并提供 checkpoint SHA、数据 split SHA、选择指标方向与零 frozen-access 收据。
