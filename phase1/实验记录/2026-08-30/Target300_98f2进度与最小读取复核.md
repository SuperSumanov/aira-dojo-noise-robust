# Target-300 `98f2` 进度与最小读取复核

## 结果

固定 quiescent monitor 在 snapshot
`98f2cba9ca4b3ac6404305da2528a4e8c391ba795f74438a5e4cca1a162765fa` 连续稳定 5×300 秒后，于
`2026-08-30T02:38:22Z` 正常完成 formal，rc=`0`、stderr=`0 bytes`。exact control commit=
`ab59a011d945e4a96daf7dbbbc927a59027da077`；focused/full=`12/965 passed`，47 warnings。

白名单结构总量为：

- selected physical runs：`160→193`；
- selected archives：`49→60`；
- selected tasks：`30`；
- target=`300`，remaining=`107`；
- previous exact prefix survived=`true`；
- boundary archive 不存在，first-closed anchor 不存在。

producer 状态为 `FUTURE_COHORT_COLLECTING`；独立 verifier 为 `PASS_COLLECTING_TRUTH_UNREAD`。因此这只是 33 个新增
target-eligible physical runs，不是 cohort closure，也不授权 truth support、replay、effect、
GPU 或付费 API。first-960 与 Target-300 estimand 继续分离。

## 复现与安全

结果根：
`/research/d7/spc/yzyang4/score-channel-future-identity-cohort/ab59a01-98f2cba9ca4b-9f69935923f7`。
producer A/B 与 verifier A/B diff 均为 `0 bytes`；52-entry manifest 全部复核，`SHA256SUMS` SHA-256=
`81831f68055cef1fcae654b8adad3d71c8bf2893a57ef4ba0785e2c2b475cb2e`，结果根 mode=`555`。forbidden open、
credential filename/content=`0/0/0`。truth/label、prediction values、accuracy/search utility 均未读。

第一次检查直接打印了 runner 官方 `formal.stdout`；其中 aggregate inventory 附带 task-level 结构 run counts。它不含
run/Card identity、label、outcome、prediction、accuracy 或 utility，但超出了原计划的 totals-only 最小读取。该偏差已在
机器回执中诚实记录；不复制 task-level 表、不据其选 task/阈值，后续复核改成固定 JSON 白名单，只输出 totals、status、
closure 和 verification status。

机器回执：`phase1/target300_progress_98f2_safe_receipt_20260830.json`。
