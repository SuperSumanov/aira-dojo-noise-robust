# Exact-same-pool heterogeneous predictors：train-only 预注册

状态：**outcome 前冻结**。协议名：`heterogeneous_oof_v11_discovery_v1`。本协议晚于
`TaskTopCentered_RunOOF_裁决.md`，但不改变稳定论文伞：run-clean、NAS-Bench-style 的
MLE-agent 搜索树数据集与真实 sibling 决策 benchmark。

## 1. 问题与边界

已关闭 fixed frozen global head、sparse line patch 和 task-conditioned/top-centered linear head。本轮只问：
在同一 v11 train-only pair pool 与同一 physical-run outer folds 上，执行前可得的异构代码/动作特征是否
（a）独立有信号，（b）与 frozen embedding 的错误互补，从而授权下一轮严格 nested ensemble。

异构 predictor 与 ensemble 在 NAS 已有先例，**不是单独 novelty**；若成立，它只是增强方法资产。禁止读取
`decision_frozen_v11_b*`、任何 test/held pair 文件、stdout、runtime、self-report、external score 或标签派生
post-execution feature。底座不更新。

## 2. 锁定输入与切分

- pairs：`phase1/v11_decision/decision_train_v11_b0.jsonl`，SHA-256
  `bd31b4679c7b4405703b976921df0bc63acba4fc0c4a002f4b8f36d171251fca`；
- run map：`phase1/card_run_map.json`，SHA-256
  `3d774d8414e7b0553e4efdab9410b06aa67ed80cac48fff2d69cbe056baa0e30`；
- train endpoint manifest：SHA-256
  `8c9621dd9d863d5640c54d1eefee42f5c170bbaf5d7bceceda7aa372ac1afc19`；
- source cards：SHA-256
  `6794acbf1dbc21ca75bed5899f4dd071b4b0d1a5b092c2e60bc634a8c5701b75`；
- locked frozen-head OOF：SHA-256
  `083f4daa23ab3f8b1d9e412184fbe9ee06d891385e8f66e0bbbb29b3e3055a96`；
- exact pool：4,263 pairs / 333 physical runs / 23 tasks / 2,293 parents / 5,499 endpoints；
- outer fold 逐行继承 locked OOF 的 5-fold assignment；任何 physical run 跨 fold 立即失败。

cards corpus 虽含全语料，loader 只允许 manifest 中 5,499 个 train endpoints 进入内存输出；逐 endpoint 验证
code SHA/长度/task/run。pair/frozen/test/held 文件名 guard 必须 fail closed。本轮的
`frozen_read` 固定为 false，指没有打开任何冻结 pair 文件。

## 3. outcome 前固定的 arms

共同训练方式：每个 outer fold 只用其余 run；每个有向 `better-worse` 训练样本同时加入相反顺序与负标签，
避免位置捷径；候选 score 必须反对称或由完整 parent 内的 pairwise logit 聚合得到。

1. `fixed_frozen_global`：只读、hash-locked 的历史 OOF anchor；
2. `op_only_lr`：`Draft/Debug/Improve/Other` one-hot，pair-difference logistic；
3. `static_lr`：只含执行前代码统计、library/method flags、lineage depth/step/sibling count 与上述 op one-hot；
4. `static_gbm`：与 `static_lr` 完全相同输入的 symmetric pair-difference HistGBM；
5. `char_tfidf_lr`（唯一 primary discovery arm）：字符 `char_wb` 3–5 gram，30,000 features，
   `min_df=3`、`sublinear_tf=true`；每个 outer fold 的 vocabulary/IDF 只在 outer-train endpoint 代码上 fit。
   代码超过 20,000 chars 时固定取前 5,000 + 后 15,000；LR 固定 `C=0.5`、无 intercept；
6. `equal_rank_frozen_tfidf`：部署时可实现、无标签的 parent 内 percentile-rank 等权平均；只作 secondary，
   不能替代 primary unlock arm。

固定参数：seed=887；`static_lr C=1.0`、无 intercept；`static_gbm max_iter=300`、
`learning_rate=0.08`、`early_stopping=false`；不做 outcome 后超参网格。

## 4. 指标与推断

每个 arm 全量报告：pair accuracy、complete-parent top-1、parent-equal gap utility、task consistency、coverage、
query/init cost。top-1/utility 的所有模型差异都做 paired run-clustered 与 task-clustered 10,000 次 bootstrap；
不只报微平均。

互补性对每个新 base 与 anchor 报：pair disagreement、parent top-1 weighted rescue/harm、correctness phi、
oracle-union top-1 与 oracle headroom。oracle 只描述上界，不能当可部署结果。

## 5. outcome 前固定 gates

### 5.1 Frozen unlock gate（只适用于 primary `char_tfidf_lr`）

全部同时成立才输出 `DISCOVERY_UNLOCK_RECOMMENDED`：

- pair accuracy ≥ 0.52；
- complete-parent top-1 ≥ 0.50，且相对 anchor 微平均增量 ≥ 0.03；
- gap utility ≥ 0.55，且相对 anchor微平均增量 ≥ 0.02；
- top-1 与 utility 的 paired run/task CI 下界四项全部严格 > 0；
- supported tasks ≥ 15，nonchance share ≥ 0.60；
- run overlap=0、coverage exact、orientation oracle=1、随机 pair control ∈[0.47,0.53]、所有 fits accepted、
  input hashes exact、`frozen_read=false`。

通过也只表示另立协议进行一次 frozen look；本程序没有 frozen 参数。

### 5.2 严格 nested ensemble 授权门

对预声明 base 集 `{op_only_lr, static_lr, static_gbm, char_tfidf_lr}` 逐一报告，并允许“存在至少一个”满足：

- base pair ≥ 0.52、top-1 ≥ 0.46、utility ≥ 0.525、task nonchance share ≥ 0.60；
- 与 anchor 的 pair disagreement ≥ 0.15；
- weighted parent rescue ≥ 0.08；
- oracle-union top-1 相对两者较优者 headroom ≥ 0.05；
- base-anchor 的 top-1 与 utility paired run/task CI 下界均 ≥ -0.02。

只有存在这样的 base 且全部 integrity gates 通过，才输出 `GO_NESTED_ENSEMBLE`。这只是授权另立协议，在每个
outer fold 内重新生成 inner-run OOF 来训练 meta-head；严禁在本轮同一 OOF 行上 fit 并回报 stacking。

`equal_rank_frozen_tfidf` 另报直接可部署证据：top-1 delta ≥0.015、utility delta ≥0.01，且两指标的
run/task CI 下界均 ≥-0.01。它不影响上述授权门，也不允许 outcome 后改权重。

## 6. Kill / 解释规则

- primary 未过 unlock：继续封存 frozen，不得用 secondary 代替；
- 无 base 过 nested-ensemble 门：关闭当前 code-stat/char-TFIDF ensemble 路线；
- static 强而 TF-IDF 弱：只能在新协议中以 static 为 primary，不得追认本轮 frozen unlock；
- task/operator 强只说明 action prior 有数据内效力，必须单列，不得冒充普适代码理解；
- 任何 hash、fold、coverage、optimizer 或 verifier 失败均为 `INVALID`，不解释科学结果。
