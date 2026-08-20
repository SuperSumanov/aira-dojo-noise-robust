# WLGraph 前瞻预测 v1：完成与独立复核

日期：2026-08-20。状态：`INDEPENDENT_PROSPECTIVE_WL_GRAPH_ESCROW_VERIFIED`。

## 完成链

结果前 commit `031edb34400781ca026bc9833ac7f850312ffb1c` 已固定四臂、唯一 primary、唯一
char-TFIDF comparator、时间分层、支持门与效果门。远端 focused `14 passed`、phase1 全套
`477 passed` 后，自动 activation receipt 在 `2026-08-20T05:20:27.656860Z` 生成；协议、bundle、build
summary、独立 bundle verification 与全部 source blobs 均绑定 SHA。旧手填未来时间戳继续永久作废，没有被复用。

固定 snapshot `88cb791...170c8` 的 producer 在 10 分 22.30 秒内完成 5,643 endpoints / 223 runs /
25 tasks / 1,473 canonical sibling pairs 的四臂预测；不 import producer 的 verifier 用独立 cohort 重建、独立
static helper 与独立矩阵拼接在 9 分 50.30 秒内逐项重算。四臂最大绝对分数差均为 0.0，两个进程退出码均为 0。

graph 模式为 AST=5,488、token fallback=150、raw-line fallback=5，159 个 endpoint 触发 8,192-node cap；
四臂 pair tie 均为 0。producer/verifier peak RSS 分别为 3,020,036/3,012,904 KiB。

## 时间裁决

activation 的唯一严格关系是 `generation_started_at_utc > activated_at_utc`。当前 223 runs 与 1,473 pairs
全部更早，所以全部固定为 `outcome_unread_support_only`；strict post-activation pairs=0。这是预期结果，不是
样本失败，也不能通过移动 activation、改为上传时间或把相等时间纳入来补数。

因此本轮不能计算或报告 accuracy、paired delta、CI 或 search utility。它只证明已经能在不读 outcome 的情况下，
把 graph/multi-view baseline 对现有前缀封成不可修改预测，并从自动时间边界开始等待真正未来的数据。

## 安全与复现

两份 syscall trace 的禁读路径 content opens=0、metadata observations=0；完整产物、activation 与 protocol 的
高置信 credential-shape scan=0。结果明确记录 v11 frozen/extension、0812 temporal vault、prospective outcome
均未读，effect metrics 为空，GPU/API/base-LLM update 均为 0。完整 tar 的 SHA256 为
`286677c36286566b5a2b0d3efb506e37648a041d8bbcdf9096b59dcb6e17ab00`。

## 后续唯一允许动作

继续 append-only 摄取 senior archives。每个新 snapshot 可在 outcome 仍封存时重复运行同一固定 scorer；只有
post-activation strict cohort 同时达到 1,500 finite non-tie pairs、150 finite-decision runs、15 tasks、最大任务
share≤0.25，才按预注册一次性比较完整多视图臂与既有 char-TFIDF。当前不加第五臂、不看 support prediction
margin 挑模型，也不因 Guided Evolution 的直接先例把 WL baseline 改写成方法 novelty。
