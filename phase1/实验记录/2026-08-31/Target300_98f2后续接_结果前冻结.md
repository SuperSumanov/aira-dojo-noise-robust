# Target-300：从 `98f2` 的 193-run 前缀续接（结果前冻结）

## 问题

Target-300 固定时间序身份 cohort 在 `98f2` 已由 producer/verifier A/B 正式确认到 193 runs、60 archives、30 tasks，
还差 107 runs。原 12 小时 quiescent monitor 完成后没有继续运行，而当前 outcome-blind LATEST 已增长到
`30945550...104f`，first-960 公共结构总量为 494 runs。现在需要恢复身份闭合链，但不能让当前 snapshot、边界 overshoot、
候选身份或后续 truth 反向影响协议。

## 结果前冻结

新增 `target300_continuation_after_98f2_v1`，在读取当前 successor 的 Target-300 selected runs、boundary overshoot、
candidate profile/private selection 前固定：

- science commit=`ab59a011d945e4a96daf7dbbbc927a59027da077`；原 scientific protocol SHA-256=
  `54187f386e...377d`；runner SHA-256=`c6f6ed7abd...660e`；
- base LATEST=`98f2cba9...765fa`；previous formal manifest=`81831f68...cb2e`；
- previous summary/verification=`01d67cec...8b42` / `59624c59...ee12`；安全白名单重新确认
  `193 runs / 60 archives / 30 tasks / remaining 107`、prefix survived、truth unread；
- continuation protocol SHA-256=`3a9027792d9d0b6a5466788007b363a9472b62f26409f2fc13eff88987670f97`；
- monitor SHA-256=`e35ea6e2ed7cb243e93e20acc1edecbd655155033fb9c5fa4b86ffc453a1be7b`；
- trigger 是部署后第一个被观察到的非 `98f2` LATEST，必须连续 5 次、每次 300 秒相同；变化即重置；调用者不能传
  snapshot，formal 失败不能换候选或重试；
- fixed runner 必须把 previous 193 runs/60 archives 作为逐行 exact prefix，继续按既有 archive 时间序达到 target=300，
  保留完整 boundary archive overshoot，不允许 partial archive salvage；
- producer A/B、独立 verifier A/B、focused/full tests、file trace、forbidden-open、clean worktree、secret gate 全保留；
- CPU 单线程；GPU/API/model fit/base update=`0/0/0/0`。

第一次 closed result 仍只能写 fixed one-time anchor。助手后续只允许读取 status、totals、hash 与 blindness receipt；不得打开
candidate identity/profile/private selection，也不得读取 truth、outcome、prediction、accuracy 或 utility。身份闭合只是一项结构
里程碑，不自动授权 truth-support、replay、effect、GPU 或付费 API；Target-300 与 first-960 estimand 继续分离。

当前尚无 successor Target-300 scientific result。
