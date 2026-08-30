# Prospective score identity migration v2 正式入库

日期：2026-08-31

方向：Decision Corpus + Predictor Benchmark + Audit Protocol

裁决：`FORMAL PASS + PRODUCTION LATEST PROMOTED`

## 1. 结论

学长最新的 4-run archive 已从 fail-closed 状态安全进入 append-only 生产语料。新不可变 snapshot 为：

`0c0584b87140d9a3242f2aa59920829e07e9178749880e3c1f3bd0d065e0b07a`

新 snapshot 的结构库存是：

| 项目 | 上一 snapshot | 新 snapshot | 增量 |
|---|---:|---:|---:|
| transactions | 118 | 119 | +1 |
| eligible runs | 469 | 473 | +4 |
| eligible endpoints | 12,536 | 12,680 | +144 |
| eligible structural pairs | 3,144 | 3,151 | +7 |
| eligible tasks | 34 | 34 | 0 |

当前 all physical runs=`499`。这是一项数据与审计基础设施的正进展，不是 predictor accuracy 或 search utility 的正结果。

## 2. 暴露的问题

第一次共识修复已使 4 个 checkpoint journals 中 2 个显式 task identity、2 个缺失 identity 的情形通过独立 verifier；
但生产重试在 `validate-registry` 处停止。根因是迁移只覆盖了 intake identity，没有覆盖历史 score transaction 的两个代码层：

- 118 个 historical top-level score summaries 共享一个且仅一个 exact legacy `(commit, source SHA)`；
- 其中 117 个 nested scorer summaries 共享另一个且仅一个 exact legacy `(commit, source SHA)`；
- 另 1 个 transaction 没有 eligible endpoint，因此按协议没有 nested score；
- 新失败尝试的 top/nested 各自也只有一个 exact current identity。

元数据审计只打开 summary JSON，receipt SHA-256=
`9688d3544268a84d4b7073fcba1d470ab74a330c57b4f99d2a65a04c81840102`。blind-score CSV、label vault、
outcome、prediction values、accuracy、utility、candidate identities 均未读取或输出。

## 3. 固定修复

结果前冻结 `prospective-score-identity-migration-v1`：

1. top-level score identity 只能是唯一 exact legacy tuple，或当前 fresh exact commit/source tuple；
2. 非空 transaction 的 nested scorer 必须与 top-level 属于同一 epoch；
3. mixed、partial、unknown、caller-supplied 或推断出来的 tuple 全部 fail-closed；
4. intake 的 exact legacy/current schema 校验继续独立执行，不被 score 迁移放宽；
5. 新增独立 verifier，它不导入 production pipeline，只读取 registry 与 top/nested summary 元数据；
6. 上一次失败后遗留在 live `intakes/`、`scores/` 的目录先按 registry SHA 验证，再无删除地移回原 failed attempt。

恢复 evidence 的 `SHA256SUMS` SHA-256=
`ef9d573040b499f67d07324f9bc6b38301fc65116ccd8007a6770d85a443cfae`。

## 4. 两次 formal

### v1：执行环境失败，无结果

- exact commit：`d414676c8e354b9dd58377c86eaec655567186b8`
- focused：`72 passed`
- full：`1813 passed / 1 failed / 48 warnings`
- 失败原因：远端默认 `umask=0022`，一个历史 OpenRouter 隐私测试创建的 synthetic tempfile 为 `0644`；测试正确拒绝过宽权限。
- 停止位置：所有 intake/score/registry/accumulator/verifier producer 之前。
- disposition manifest：`87bd5f0e364bfbeaca777227c7f6e56fdbb3c709e4ef56b8954328614fdb60ec`

v2 addendum 只增加 `umask 0077`；协议、代码白名单、输入、测试范围、门和解释均不改。

### v2：正式通过

- exact scientific commit：`5ed1988045a3fd8c365d001c87977314572383d9`
- focused：`72 passed`
- full：`1814 passed / 48 warnings`
- A/B：intake、archive verifier、score、registry validator、independent epoch verifier、accumulator 六层逐字节一致
- epoch counts：top legacy/current=`118/1`；nested legacy/current=`117/1`；without nested=`1`
- formal manifest：`06a877e2fe3e9ee34122cb3f7f3fe9b112e0124fdd74a7f1fcc56e556700f65f`
- GPU / paid API / model fit / base update：`0 / 0 / 0 / 0`

## 5. 生产部署与下游

- control commit：`c8e6775d11d20d5008add11763b93e7d6c99362d`
- deployment manifest：`108c01fac59fc8e00b84bad5f1cd9104220dfad7c66ab9c3a3f7f5f9b72896fb`
- continuous intake monitor：已存活，并在首个 poll 原子提交新 LATEST
- transition：`0c0584...b07a` snapshot chain 已完成并独立复核；selected/added/removed runs=`473/4/0`，common pairs=`3,144`，outcomes/effect metrics=`false/0`
- WL：相对其正式 state 的新增 runs 为 5，低于冻结门 12，故正确 deferred；已续挂 96×300s monitor
- Target-522：观察到 runs=473，尚无 candidate，不触发选择或揭盲
- receipt-support：等待 WL 与 transition 指向同一 snapshot 后才会生成结构 receipt

## 6. 论文意义与边界

正面资产是：benchmark 的生产语料链已实际经受两类真实漂移——archive 内 task metadata 缺失与历史 score code epoch
迁移——并展示了 fail-closed、恢复、exact allowlist、独立 verifier、A/B、全套回归、hash/trace/security 与不可变 snapshot
promotion 的完整闭环。这能直接支撑 Dataset & Benchmark 论文的 provenance/audit protocol 贡献。

本次没有读取冻结结果，因此不能声称 critic 更准、scaling 成立、search 更好或方法取得 effect。下一次科学正结果仍只能来自
预注册 cohort 闭合后的独立评估，而不是这次结构增长本身。
