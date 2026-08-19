# Senior Augmented Train/Dev Support v1：执行前冻结

日期：2026-08-19。状态：`FROZEN_NOT_RUN`。本轮只审计学长 augmented value-pair 数据能否在完全不使用原
`intask_split=="test"` 做 validation 的条件下，形成 physical-run-clean train/dev learning-curve benchmark。
不训练模型，不启动 GPU/API，不产生 critic/search-utility 主张。

## 已知信息与固定输入

学长文档已公开全文件约 6,976 pairs、平均 context 3,787 tokens；这些不是未见结果。尚未计算的是 train-only
dev 划分后的 pair/task/config 支持及 nested learning-curve 各层训练 pair 数。

- senior commit=`92a9651f2e13a9e43623235b82c07c19721bc2ee`；
- cards SHA256=`5fd24c8e545a67e1048f8a67b23bcb64605b9ad584a4fbaa44aa1b1f1b6e1afb`；
- pairs SHA256=`c669d672d0a2aeee6da97393e3e832a312295aa5aebd7cd457ff297a27d4d9d2`；
- runsplit SHA256=`1323a43b2f52722a66c3fc84fb48e6d8d208c8b8c096eccf4bc7dc14937bb5de`；
- 四个 LFS 文件在解析前已完成静默高置信 credential scan，命中数=0。

## 固定划分与统计

1. 从 cards grouped JSON 建立 card→physical run，以及每 run 的 task、client、hardware、time_limit、
   execution_timeout；同 run 内这些字段必须一致，card ID 必须全局唯一。
2. 原 runsplit 的 `hold` 是冻结 test runs；任何 `intask_split==train` pair 的两端必须都不在 hold，任何 test pair
   的两端必须都在 hold。只统计 test 数量和结构一致性，不把 test orientation/code 写入任何输出。
3. 对每个至少 5 个非-hold runs 的 task，按
   `SHA256("augmented-dev-v1|20260819|task|run_id")` 升序，把 `max(1,floor(0.2*n))` 个 runs 固定为 dev；
   其余为 train。少于 5 runs 的 task 不进入 learning-curve pool。
4. 原 train pair 两端都在 dev 才是 dev pair；都在 train 才是 full-train pair；跨 train/dev pair 丢弃。
5. nested fractions 固定为 0.25/0.50/0.75/1.00。每 task 的 train runs 按
   `SHA256("augmented-curve-v1|20260819|task|run_id")` 排序，各层取 `ceil(fraction*n)`；只有两端 runs 都入层的
   full-train pair 才计入该层。
6. same-experiment contract 定义为 pair 两端 run 的 `(client,hardware,time_limit,execution_timeout)` 完全相同。
   只报 share，不读取 label value/gap/category。

## 固定资格门

全部通过才允许另立 train/dev-only TF-IDF learning-curve 预注册：

1. original train pairs≥2,500，original split inconsistency=0，train/dev 与 hold run overlap=0；
2. dev pairs≥400、dev tasks≥8、dominant dev task share≤0.35；
3. full-train pairs≥2,000，quarter-train pairs≥300，四层 pair 数严格递增；
4. full-train 与 dev 的 same-experiment contract share 均≥0.95；
5. dev 每个任务≥20 pairs 的任务数≥6。

失败不改 seed/fraction/阈值、不按 task/client 筛选。通过也只授权 CPU light-predictor 设计，不授权使用 frozen test、
8B 训练或 search utility。

## 十三项执行前检查

1. 方向：近期 D&B/学长 augmented scaling 接入，不恢复旧 HCE/TD/多保真。
2. 代码：结果前 clean commit；新目录输出，禁止覆盖。
3. 输入：commit、四个 LFS SHA 与 size 固定。
4. 单位：physical run 划分；pair 只作结构支持，不当 iid。
5. 已见结果：只披露文档中的全文件 pair/context 数；train/dev support 未看。
6. 特征：本轮不训练；仅 identity、split 与 run config。
7. 泄漏：hold test runs 永不进入 train/dev；test orientation/code 不输出。
8. 安全：credential-first scan 已过；不读取 `.env`，不输出 code/label/gap。
9. 统计：精确计数/share，无效果 CI。
10. 复现：固定 hash 排序；producer 双跑；匿名 run/pair support 由独立 verifier 重算。
11. 资源：CPU-only，预计<10分钟；GPU=0、API=0、底座更新=0。
12. 失败：SHA/schema/split/identity 不一致立即 fail closed。
13. 停止：资格不足即关闭；资格通过后仍需另立效果预注册，不能直接看 frozen test。
