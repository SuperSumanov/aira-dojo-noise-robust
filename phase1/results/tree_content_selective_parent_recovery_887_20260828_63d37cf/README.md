# Selective parent recovery：snapshot 887 正式证书

正式分类：`DEVELOPMENT_TIME_SPLIT_HIGH_PRECISION_SELECTIVE_PARENT_RECOVERY`

本包记录一个结果盲、run-disjoint 的开发审计：只用时间序较早的 290 个 physical runs 选择 exact-Jaccard
top-vs-second margin 阈值，再在较晚且完全不重叠的 145 个 runs 上评估一次。它验证的是语料中已记录、两端均存在且
满足 exact preceding-depth 的 parent pointer；不是语义/因果 ancestry 真值，不覆盖 orphan，不推断 predictor accuracy
或 search utility，也不授权静默改写 canonical graph。

## 冻结规则与正式结果

- 固定 snapshot：`887491a021d75d889c00a5af672a11b8b06e249d98e84fd91288534080f62697`；
- protocol SHA-256：`a9fe1b26cec20b6725f19e30e605755aa2e854033ec0462c4a39d18e0f80f97c`；
- source commit：`63d37cf6985a3b95c955a9d2d4c44c51aab8d152`；
- train-only 选中阈值：`1006/16929 = 0.059424655915883987`；
- train：接受 `5769/6832`，正确 `5712/5769`，precision=`1904/1923 = 0.99011960478419136`；
- test：接受 `2691/2907`，coverage=`299/323 = 0.92569659442724461`；
- test：正确 `2684/2691`，precision=`0.99739873652917133`，仅 7 个错误；
- 无 reject 的 test unique-top precision：`2845/2907 = 0.97867217062263501`；
- 25/25 个可条件化任务达到 0.95 precision reference，138/138 个可条件化 runs 达到 0.90 reference；
- 最大 accepted contribution share：task=`44/207`，run=`55/897`，均通过结果前 anti-dominance 门；
- 所有 hard-support 与 primary gates 均为 true。

错误 parent 的三个分母分别为：

- all-alternative micro FPR：`7/11257 = 0.00062183530247845781`；
- uniform one-wrong-per-child expected FPR：`58/43605 = 0.0013301226923517946`；
- child-level adversarial vulnerability：`7/2907 = 0.0024079807361541109`。

三者不可互换。尤其不能把 micro FPR 单独写成任意 corruption 的总体失败概率。

## 复验与安全

- producer 两个不同 `PYTHONHASHSEED` 输出逐字节一致；
- 不导入 producer 的 verifier 两次输出逐字节一致，并独立重算 snapshot、split、fingerprint、候选集、阈值和门；
- focused/full tests：`23/1448 passed`；
- formal producer / verifier / summary / remote manifest SHA-256：
  `750ebd33306fa44e9421e1d421e8631c7ade7eae95f53b9adb854abc0c7e3c06` /
  `50b3a280ffbc4ea7d404065a97a7450b41c18ec5a89c95bc5644b88bfdbe2955` /
  `2aca589f7d8f943360e9d1d7c3716744b0357d99918913729aecf898a59a2690` /
  `c51ad0948510a2d092bf3aa9db905558fbb645454296b587c921d973e6b2e281`；
- prospective label/grade/outcome/prediction values 与 raw senior archives 均未读取；
- GPU/API/model-fit/base-update=`0/0/0/0`。

`formal_summary.json` 是匿名 aggregate 主结果；`verification.json` 是独立核验回执。其余文件保存 preflight、测试与安全回执。
