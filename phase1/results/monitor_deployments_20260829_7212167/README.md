# 2026-08-29 outcome-blind monitor deployments

本目录只记录结构 monitor 的公开来源与远端不可变回执，不含 prospective label、outcome、prediction、accuracy、utility
或 endpoint/task/run identities。

## Target-522 yield-guarded breadth

- source commit：`219438e65d1275498e44a650306ce561696fdb8c`
- post-push manifest：`88eaba3f220fdb6574f64e0d0550fcffdebccb6fad0d4a90820964fab68ef0a4`
- monitor source SHA-256：`4346ccf0ea8dc31ffc850d402d680c77e936e6f95fa44555185166c7ca9ae4c5`
- deployed PID：`283216`
- deployment manifest：`5eb77817aa2bb7626aae888bc500303194cba296b319c2640ae248d1f860c8d8`
- start gate：selection candidate/READY/COMPLETE 与失败 markers 全不存在；首轮 `selection_complete=false`。

## Outcome-blind supervisor v2

- source commit：`7212167f0bf39e0be95b07085baca4208f8fbc6a`
- post-push manifest：`98555ae901bc7f631274c6ac40c6ae9665e0f7cfc58968bb243892f2c4b4e86c`
- supervisor source SHA-256：`51a9a99e75e8a1e24e5cc3b24fb75f249a07f3b500ca74e90b6baa14abffb5a0`
- supervisor / guard v4 PID：`289403` / `289483`
- deployment manifest：`0bed43b90e0b01ef2cd5eb76ea7470e99516b42dac809568b94b28fc5c893469`
- first postflight：两把 exclusive lock held，LATEST exact 887 baseline，sidecar filename count=0。

两条链的 `prospective_values_read=false`，GPU/API/model-fit/base-update=`0/0/0/0`。PID 是部署时回执而非永久身份；
后续状态以各自 immutable root、source commit、SHA256SUMS 与 marker 为准。
