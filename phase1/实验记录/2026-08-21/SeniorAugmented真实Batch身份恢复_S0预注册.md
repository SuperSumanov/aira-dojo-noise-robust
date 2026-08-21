# Senior Augmented 真实 Batch 身份恢复 S0：执行前冻结

日期：2026-08-21。状态：`V3_VERIFIER_CORRECTION_FROZEN_NOT_RUN`。

## V1 结果前工程纠错（不改变科学门槛）

commit `7f01946a163b3897d6c19fb2f8bba7a5c13ae8ea` 的第一次正式尝试在 producer 1 后停止，目录为
`senior-true-batch-identity-support/7f01946-v1`。当时尚未运行 verifier，也未读取任何效果；producer 只给出
全零支持。原因是实现把正则第一组写成 `_seed_...` 之前的 batch 前缀，却把该组当作完整 source run basename，
导致 tar header 明明存在仍然 676/676 未匹配。

V2 在再次读取有效支持结果前冻结两项纯工程纠正：

1. 正则改为 `^(.+_seed_[0-9]+_id_[0-9a-f]+)__(YYYY-MM-DD)$`，第一组逐字对应 tar 中 run-directory
   basename；producer 与独立 verifier 都新增真实形状回归测试。
2. V1 的 producer 会把被拒绝归档写成确定性错误行，但 verifier 遇到同一错误会立即退出，无法独立确认
   fail-closed 结论。V2 让 verifier 用同一规范错误码重建错误行；错误仍触发原身份门，不会被忽略。

V1 同时暴露了两个 source archive scan errors；header 复核显示其中存在原协议明确拒绝的 link 类成员。V2 不把它们
重解释为无害旧格式，也不缩小 archive inventory：link/device/fifo、缺少权威 journal 与其他真实扫描错误继续按原门
fail closed。

日期集合、输入 SHA、batch 定义、split domain、20% 规则以及全部身份/支持阈值均不变；协议标识升级为 v2。

## V2 verifier 工程失败与 V3 纠正

commit `a70232af40b7f6e45e87997a1d193835cd9ce863` 的 producer×2 已 byte-identical，并首次产生非零结构支持；
但第一次 verifier 在独立重建两个规范错误行后，错误地对 rejected archive 访问 `run_batches`，以 `KeyError`
退出。因此 `a70232a-v2` 没有完成独立验证、没有正式科学裁决，也未读取效果。

在再次正式运行前，V3 冻结以下 verifier-only 加固：

1. rejected archive 保留在 inventory/error gate 中，但不进入 run→batch join，与 producer 行为一致；
2. verifier 不再只比较 manifests 与 support，而是独立重算整份 summary 的 inventory、identity criteria、support
   criteria、status、输入绑定、配置和 scope，并要求逐字段相等；
3. verifier 显式绑定 expected source commit；新增 rejected-row join 反例测试。

已看到并披露 V2 的 outcome-blind 结构数，但 V3 不修改日期、输入、身份规则、batch key、split、阈值或停止规则；
协议标识升级为 v3。V2 的描述性数字不得替代 V3 正式结论。

## 问题与边界

学长的 augmented pair producer 在每个日期目录的直接子目录内单独构造 pair，但发布后的
`batch_value_pairs_filtered_runsplit.jsonl` 没有保留原始 batch path。此前只能用 run-family/date
做代理，因此 708 个 config-mismatch pair 的来源只能写成 `BATCH_CONTENT_MIXING_LIKELY`。本轮尝试从原始
归档的 **tar header 路径**恢复真实 batch 身份，并判断原始 train 部分是否足以构造 batch-closed dev。

本轮是 outcome-blind 身份与支持审计，不评估 predictor，不读取 pair 朝向、numeric grade、gap、code、stdout、
runtime 或 frozen-test 效果。即使通过，也只允许进入下一份结果前冻结的 train-only CPU 效果协议；不能追认学长
现有 scaling 曲线为确认性结果。

## 固定输入

- 匿名 run manifest SHA256=`bd707dd992a131d03dc20bdc981626826325f461e086a945b2f85fc41c2c171b`；
- 匿名 pair structure SHA256=`52ffcdc0b7cc4486b61de0c664c7c057c26171a520372ca2071d55f2fb7a127b`；
- 上游 support summary SHA256=`7745dd157e41dc96a00ac76979afa6369f06395b0aa8ad67756de4d84e7297e8`；
- 学长数据代码 commit=`92a9651f2e13a9e43623235b82c07c19721bc2ee`；
- source root=`/research/d7/spc/yzyang4/external/senior_data/mle`；启动前监控到的全目录 metadata
  inventory=`3f23943b81f8d39367a4e503dfbf5de2d78b65fc36a1918499a722e689dbb5b3`，文件数 186。

只纳入学长 `build_batch_cards_all.sh` 在固定 commit 明确列出的 21 个日期目录：0726--0731、0801--0804、
`0805-这里开始进一步压低任务限时和子节点数`、0806--0809、
`0810-明天的任务将降低单次run时长来提高run产量`、0811--0815。0724、重复说明目录和 0816 之后来源不进入
这版已发布 augmented 数据身份恢复。

## 固定身份规则

1. run manifest 的 run ID 必须唯一匹配正则
   `^(.+_seed_[0-9]+_id_[0-9a-f]+)__(YYYY-MM-DD)$`；第一组是完整 source run-directory basename。
2. 每个 source 文件先绑定 path/size/mtime/SHA256；tar 仅流式读取 header，禁止调用 `extractfile`、禁止提取，
   禁止读取任何 member payload。所有路径必须相对、无 `..`、无反斜线/NUL，link/device/fifo 均拒绝。
3. 只认 `<batch>/<run>/checkpoint/journal.jsonl` 的 header；真实 batch 键固定为
   `(source-date-directory, first-path-component)`。重复归档若落到同一键可折叠；同一 run 前缀若命中多个真实 batch
   即为歧义。
4. 每个匿名 run 必须恰好命中一个真实 batch；每条匿名 pair 的全部 endpoint run 必须属于同一 batch，task 必须
   一致。不得用 family/date/config 代理填补缺失或歧义。
5. batch ID 对外只写 domain-separated SHA256；原始 archive/member path 只进入只读审计 manifest，不进入效果输入。

## 固定 experiment-closed 支持切分

- 只使用 `original_split==train` 的结构；`original_split==test` 只计数并验证未进入角色分配，不读取效果。
- experiment 单位=`(task, true_batch_sha256)`；有 train pair 的 task 若 experiment 数少于 5，整 task 标为
  `excluded_low_support`。
- 其余 task 以固定 domain `senior-experiment-closed-dev-v1|20260821` 对 experiment 排序，
  `max(1,floor(0.2*n))` 个为 dev，其余 train。pair 不删除后再随机分；其所属 experiment 决定角色。

## 资格门与停止规则

以下全部通过才记为 `EXPERIMENT_CLOSED_TRAIN_DEV_SUPPORT_FEASIBLE`：

1. 三个输入 SHA/schema 精确；原始 train/test 结构计数精确复现上游；
2. source archive 扫描错误=0，member 路径/类型错误=0；
3. run 未匹配=0、run 多 batch 歧义=0；
4. pair 跨 batch=0、pair task mismatch=0；
5. train/dev experiment overlap=0，frozen-test experiment 被用于角色分配=0；
6. dev pairs≥400；dev tasks≥8；
7. dominant dev task share≤0.35；dev 中 pairs≥20 的 task≥6；
8. experiment-closed train pairs≥2,000；
9. train 与 dev 均至少 5 个 experiment；
10. tar member payload reads=0、env payload reads=0、GPU/API/model fit=0。

任一身份门失败，状态为 `IDENTITY_UNAVAILABLE`；身份通过但支持门失败，状态为
`INSUFFICIENT_EXPERIMENT_CLOSED_SUPPORT`。不得改日期目录、正则、batch 定义、hash domain、20% 规则或阈值追救。

## 十三项执行前检查

1. 方向：服务 Predictor Benchmark 的 split/shortcut 审计，不恢复 HCE/TD/多保真。
2. 代码：单用途 producer、独立 verifier、合成反例测试；新目录输出，不覆盖旧结果。
3. 输入：三份匿名结构 SHA、学长 commit、source metadata inventory 固定。
4. 单位：physical run、真实 batch/experiment、task；pair 不当 iid 效果样本。
5. 已见结果：披露旧 proxy 结论和 708 mismatch，不据此改变新身份规则。
6. 特征：只用 run ID/task/role 与 tar header path；不读 outcome/code/config value。
7. 泄漏：原始 test 只做结构计数，不能进入 train/dev 分配或任何拟合。
8. 安全：raw tar 不提取；member payload、env payload、credential value 读取均为 0；结果再做凭据扫描。
9. 统计：S0 仅精确计数/share/support gate，不报 predictor 指标或显著性。
10. 复现：固定排序/JSON、producer 双跑、独立 verifier 双跑、完整 SHA manifest。
11. 资源：CPU-only，预计 20--60 分钟；GPU=0、API=0、底座更新=0。
12. 失败：SHA/schema/archive/path/join/pair/batch/support 任一不符即 fail closed。
13. 停止：S0 一次性裁决；只有全门通过才另立 S1 效果预注册。
