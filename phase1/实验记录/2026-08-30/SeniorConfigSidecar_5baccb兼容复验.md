# Senior config-v2 sidecar：5baccb 最新分支兼容复验

日期：2026-08-30
状态：`PATCH_COMPATIBLE_WITH_LATEST_SENIOR_COMMIT_NOT_DEPLOYED`

## 1. 为什么这是当前正方向的必要门

学长 0820 的 experiment-level value scaling 是目前最强容量信号，但旧数据仍有 cross-config rows、周期 outer-test eval、
训练未完整结束等问题。现有确认契约只接受 outcome-before 的 exact producer stratum；事后用 archive mtime、文件名或
历史 config 回填均不合法。因此最新语料即使更大，只要没有 config-v2/generator-release sidecar，就不能升级为 clean
scaling confirmation。

## 2. 最新分支与补丁兼容性

学长最新 commit 为 `5baccb170ce287f9c8eed7b23ccf693a0268515a`。代码树中没有
`DOJO_CONFIG_V2_SIDECAR`、`DOJO_GENERATOR_RELEASE` 或 config-v2 producer hook；当前 outcome-blind source 的
`*.config_v2.jsonl` 文件名计数也仍为 0。

既有补丁 `0001-Add-prospective-config-v2-producer-hook-18-tests.patch` 的 SHA-256 为
`56a3e4b61918e1b06830712d418ed27ef5135017eab2b9e833b92c626054c9a5`。在 Linux sparse checkout 中只取
`src/dojo`、`docs`、`tests`，完全排除 data/LFS；补丁对 5baccb `git apply --check` 与 apply 均无冲突。结果：

- 4 个预期变更路径；
- focused=`19 passed in 0.26s`，Python compile 通过；
- credential filename/blob=`0/0`；
- senior branch modified/pushed=`false/false`；
- prospective values/GPU/API/model fit/base update=`false/0/0/0/0`。

远端回执：`/research/d7/spc/yzyang4/sidecar-patch-compatibility/5baccb-r1`。

## 3. 给学长的最小下一步

请学长先 review/apply 该补丁；生产时显式设置 `DOJO_CONFIG_V2_SIDECAR=1` 和一个公开、稳定的
`DOJO_GENERATOR_RELEASE` 标签。它默认关闭，不含环境 dump、凭据、outcome 或 label。只有下一批真实 sidecar 与 archive
在 outcome-blind intake 中配对成功，才能冻结 0.6B/4B/8B × seeds 的 GPU 矩阵。当前新 LFS 语料不能回填为 exact
stratum，也不启动 GPU。
