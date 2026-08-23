# Clean critic scaling：confidence--cost 二级扩展 v1

状态：`ANALYZER_READY_EFFECT_ASSETS_PENDING`。本扩展只冻结未来 clean scaling 同一批 predictions 的二级分析，
不授权 GPU、API、模型拟合、底座更新或真实 future truth 读取，也不修改 primary contract。
机器契约 SHA-256=`00ba64a222ae793c3f5d196ee754f0af9e2f01986ad85ed78c11b6f570da665b`。

## 1. 问题与不可越界的主张

primary clean scaling 只问 task-macro pair accuracy、TF-IDF 基线与 component utility。学长 0820 探索表同时出现一个
值得确认但不能事后追认的现象：accuracy 改善有限时，pairwise eval loss 随模型规模更平滑地下降。未来同一批一次性
endpoint scores 可回答两个二级问题：

1. 模型容量增加是否先体现在 proper scores（log loss、Brier），而不只在 0/1 accuracy；
2. critic confidence 能否把候选分成“只执行一个”和“两个都执行”，形成可审计的执行成本--regret 曲线。

这不是新 calibration 或 abstention 方法。CAMEL 已用 verdict-token margin 对低置信 preference 判断调用更贵的
reflection；Calibrated Preference Learning 已把 reward-model calibration 定义为独立于 top-1 accuracy 的质量维度。
本项目只主张 MLE-agent physical sibling、pristine execution grade 与真实执行次数口径下的 benchmark/deployment
证据，且不写 `first/only`。

最重要的禁止项：本扩展的任何 PASS 都不能把 primary FAIL 改写成 clean scaling PASS；它只能在 primary 结论旁边
单独报告。历史 test-touched checkpoint、旧 b0/b1/b2 和 score-channel prospective vault 全部禁用。

## 2. 结果前锁定与 dev-only calibration

扩展机器契约必须绑定 primary contract SHA-256
`579771ac1b90b1022bdded1182ce5c5a17780a741dc95d82a53f5f91d577a568`、同一 primary pre-test lock、同一 test bundle、
同一 TF-IDF 与 `Qwen3-Base {0.6,1.7,4,8}B × seeds {6,7}`。不得增加、删除或替换 predictor。

在任何 test ledger 进入 `STARTED` 前，另建 `critic-scaling-confidence-cost-lock-v1`，锁定 dev truth、全部 dev
endpoint scores、checkpoint manifests 与 primary lock SHA。dev 至少 200 pairs/8 tasks，最大任务占比不超过 0.35；
dev/test endpoint、physical run 与 unordered pair 三种交集都必须为零。

每个 predictor 单独拟合一个无截距、保持交换反对称的标量映射：先用 dev 非零绝对 margin 的中位数归一化，再在
`beta ∈ [0,100]` 上以固定 100 次凸导数二分最小化 dev binary log loss。边界解必须显式报告。test label 不得用于
温度、阈值、coverage 或 checkpoint 选择；test 只使用已经锁定的 beta。

## 3. proper-score estimand

每条 raw sibling 的正确方向 margin 为 `better_score-worse_score`；预测正确方向概率为
`sigmoid(beta * margin / dev_scale)`。primary 为 task 内先平均、再 task-macro 的 log loss 与 Brier；micro、10-bin
ECE 和 accuracy 只作 secondary。区间只做 10,000 次 task bootstrap（seed=`2026082301`），禁止 pair-i.i.d. CI。

proper-score scaling 门要求：四规模两-seed mean 的 log loss 与 Brier 均单调不升；8B−0.6B 在每个 seed 上两项均
严格为负；两-seed mean 的 task-bootstrap CI 上界也对两项严格小于零。8B 超 TF-IDF 是另一个更强门，不能用它替换
capacity 门。

## 4. confidence--execution frontier

coverage 固定为 `{0.25,0.5,0.75,1.0}`；headline coverage 在结果前固定为 `0.5`。每个 task 内按
`abs(calibrated_logit)` 从高到低接收 `max(1, round-half-up(c*n_task))` 条；完全同分时，用
`task/parent/component/sorted(endpoint IDs)` 的 SHA-256 排序，hash 不含 better/worse 方向。

- accepted pair：只执行 critic 选择的一个 endpoint，成本 1；
- deferred pair：两个 endpoint 都执行，成本 2，并由 pristine grade 选择较好者；
- execute-both reference：每 pair 成本 2。

因此实际节省由结果文件中的 realized coverage 精确计算，而不是硬写 25%。grade 只在 task 内形成 gap-weighted
error/regret，再 task-macro；禁止跨任务混 raw grade。除 accepted error 外，还报告相对同 coverage 随机接收的 excess
gap regret，避免“少接收自然少后悔”被误写成 confidence 有效。

selective 正门固定为 8B 两 seed 在 50% target 下：实际 coverage 落在 `[0.45,0.55]`；accepted error 都低于各自
100% coverage；两-seed mean 的 half−full error task-bootstrap CI 上界小于零；相对随机接收的 excess gap-regret
CI 上界也小于零。若失败，完整曲线仍报告，但不得挑 25%/75% coverage 救结果。

## 5. 双实现、发布和当前权限

producer 与不 import producer 的 verifier 必须分别从 dev lock 与 primary source bundle 重建温度、逐 pair proper
score、task-level risk/coverage、所有 CI 和 gates；篡改 summary/CSV 后同步更新派生 manifest 仍必须被 source
reconstruction 拒绝。正式结果目录不可覆盖，所有输入/输出 SHA 与行数写入 manifest。

当前权限仍是 GPU/API/model fit/future truth=`0/0/0/false`。合成正负控、hash-seed 确定性、身份交集攻击、晚锁攻击、
checkpoint/matrix 攻击与独立 verifier 已通过，故 analyzer 状态已升级；真实执行仍要等 primary 训练预算另报并获批。
