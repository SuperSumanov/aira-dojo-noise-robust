# SourceChoiceOOF TF-IDF v1：预注册与预检

日期：2026-08-22。状态：结果前冻结。输入只允许 S2 v2 train SHA
`e5ca6dc94f59d54fe31d4b1c4e796deef0006f489fd76a05663410d4911aa6e1` 与公开 cluster manifest SHA
`a8f328a3972708e52126157774204647698d2f8b00cc5f7ad06fd8b1d38b4035`。

## 问题与主张边界

唯一问题是：在完全看不到 held-out task 或 held-out physical run 的候选代码时，固定低成本 char-TFIDF
pairwise ranker 能否比 choice-set 的 exact uniform expectation 更可靠地预测 status-certified source winner？
标签是 agent/source-selection outcome，不等同于最终 Kaggle quality；即使 GO 也只能主张 source-choice
predictability，不得偷换成“选到全局最好解”或搜索 speedup。

主结果是 23 个 whole-task leave-one-task-out；secondary 才是 physical-run-grouped 5-fold。普通随机 group/card
split 禁止。模型只读每个 candidate 的前 20,000 字符 code；task、run、parent、数组位置、candidate hash、operator、
step、depth 都不进 TF-IDF 特征。vectorizer 每折只 fit train candidates，再 transform held-out。每个 choice set 的
winner-vs-loser pairs 总权重恰为 1，并加入完全相反 orientation，避免 arity 与方向偏置。

## 冻结模型与门

`char_wb` 3–5 grams、max_features=30,000、min_df=3、sublinear TF、float64；LR C=0.5、lbfgs、
max_iter=1,500、random_state=0。无超参搜索。controls 固定为 min-SHA、max-step、max-code-length 和
winner oracle；control 不参与模型选择。

primary estimand 为逐 task 先平均 `hit - 1/source_size` 再 task-macro。20,000 次 task bootstrap seed=20260822；
run-clustered micro bootstrap seed=20260823；另报 one-sided exact task sign test、micro/run macro、MRR、逐 task 和
source-size strata。

- `GO_CROSS_TASK`：task-LOTO task-macro delta≥0.03、task CI 下界>0、one-sided task sign p<0.05；
- 否则仅当 run-OOF delta≥0.03 且 task CI 与 run-clustered micro CI 下界都>0，记 `GO_RUN_ONLY`；
- 其他为 `NO_NARROW_POSITIVE`。不得在看到结果后改 +0.03、换 seed、删小任务或增加模型 rescue。

## 13 项预检

1. 当前方向：0DM 后的 train-only baseline；不恢复 HCE、TD/RL、probe、多保真或 score selector。
2. 问题/标签：预测 certified source winner；不声称最终质量或成本收益。
3. 输入：精确 SHA/bytes/rows；frozen/extension model 与 vault 路径 forbidden。
4. 单位：2,109 groups、5,739 unique candidates、23 tasks、275 physical runs。
5. 分布：source sizes 2/3/4/5/7/8/11 = 1,014/884/7/201/1/1/1；逐 task/run 报告，不只报均值。
6. 配平：task-LOTO headline；run-fold assignment 先按 task 内 run 负载，再全局负载与 SHA tie break。
7. 泄漏三查：每折 group/candidate/run（或 task）零交集；code SHA 跨 held-out unit 必须为 0。
8. 旋钮验证：每折记录 train/test groups/candidates、vocabulary size、LR iterations、coefficient SHA。
9. RNG：唯一 split seed=20260822；bootstrap seeds 固定；candidate ties 用 min SHA；无 shuffle sampling。
10. 训练量/功效：每个 LOTO fold 训练至少 1,733 groups；全训练有 3,630 winner-loser relations，双 orientation
    7,260 rows；按 group 等权，避免大 choice set 主导。
11. 资源：28 CPU fits、GPU=0、API=0、base LLM update=0；预计 60–120 分钟。
12. 失败处理：任何身份、schema、收敛、coverage、oracle、非有限值或 forbidden path 失败即 ABORT；不换模型续跑。
13. 发布：结果无论 GO/KILL 都保存逐 group/task/run/arity、确切命令、版本与 hash；秘密四扫后立即 push。
