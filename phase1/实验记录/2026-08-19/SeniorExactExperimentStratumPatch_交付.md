# Senior exact experiment-stratum patch：交付

日期：2026-08-19。该补丁面向学长 `dojo-reproduce`，没有直接改写或推送对方分支。

## 交付物

- base commit：`92a9651f2e13a9e43623235b82c07c19721bc2ee`；
- detached implementation commit：`50b37a355931351c1d8a57b615ff20c44d445b2e`；
- patch：`phase1/upstream_patches/0001-Enforce-exact-experiment-strata-6-focused-tests-pass.patch`；
- patch SHA256=`9f1445ae331846a4748cf82a41bebec7fd19fc28d28b4d8821c9f9333fa20f0a`；
- 在未修改 base worktree 上 `git apply --check` 通过；
- 6 个新增 focused producer/verifier/security tests：`6 passed in 0.15s`。

## 精确改动

1. pair candidate 在 shuffle 与 per-task cap **之前**按
   `(task.name, client, hardware, time_limit, execution_timeout)` 分层；只允许同 stratum 配对。
2. cap 仍按 task 应用，不因一个 task 有多个 strata 而倍增，保持其他旋钮不变。
3. 同一 physical run 内 task/config 不恒定立即失败。
4. 每条 pair 写 `experiment_stratum_sha256` 与 `batch_cards_sha256`，不暴露配置原值。
5. 新独立 verifier 不 import producer，逐条重算 endpoint/task/stratum/batch receipt；拒绝未知 endpoint、self-pair、
   重复 unordered pair、跨 stratum 或 receipt 不一致。
6. batch shell 在 producer 解析 cards **之前**先做高置信 credential scan，在 concat 之前生成
   `batch_value_pairs_receipt.json` 并 fail closed。

## 测试边界

新增 6 个 focused tests 全过：跨配置不配对、同配置仍配对并带 receipt、run 内混配失败、独立 verifier 通过、
tampered receipt 拒绝、credential-shaped bytes 在 JSON parse 前拒绝。

精确 base commit 自带的 `test_build_subtree_pairs.py` 在零改动 worktree 上是 `5 failed, 1 passed in 0.18s`；
补丁后的同一 legacy 文件加新测试为同样 5 个旧失败，未新增 legacy failure。这五个失败来自 node-value eligibility 与
旧测试预期不一致，早于本补丁，不能被写成“补丁导致”，也不能顺手修正，因为那会改变本轮唯一旋钮。

## 使用与裁决

学长审阅后可在 `92a9651` 或其兼容后继上执行：

```bash
git am 0001-Enforce-exact-experiment-strata-6-focused-tests-pass.patch
```

补丁只授权 future-only 数据生产。不得用它过滤已经查看过结果的 708 条 mismatch 后追认旧 scaling；新 cohort 必须
重建 pairs、保存 receipts、重新冻结 train-only dev，checkpoint 只按 dev 选择，最后一次性触碰 frozen test。
