# Prospective 0823：六归档预摄取观察与 producer 边界

日期：2026-08-25

状态：`OBSERVED_NOT_INGESTED / BYTES_UNOPENED / CONFIG_UNKNOWN`

## 1. 当前观察

连续 outcome-blind intake 的 metadata registry 从 212 增至 218 个 archive。新增六项均位于 `0823/`：

| 归档 | bytes |
| --- | ---: |
| AI4Code-8seeds.tar.gz | 82,377,109 |
| alaska2-image-steganalysis-4seeds.tar.gz | 8,849,428 |
| lmsys-chatbot-arena-8seeds.tar.gz | 22,329,733 |
| plant-pathology-2021-fgvc8-8seeds.tar.gz | 6,513,877 |
| ranzcr-clip-catheter-line-classification-8seeds.tar.gz | 6,004,475 |
| tensorflow-speech-recognition-challenge-8seeds.tar.gz | 20,675,682 |

合计 146,750,304 bytes。只读取了路径、size、mtime 与 observations registry；没有打开 tar member、journal、env、code、
stdout、grade、metric、prediction 或 outcome。

截至 `2026-08-24T19:34:32Z`，六项均为 `pending`，每项已有 20 次稳定观察；accepted=74、rejected=10 未变，snapshot
仍为 `f109ac...`。first-960 仍为 328/960，target-300 仍为 53/300。

## 2. 稳定门与 ETA

生产 runner 的 ready 条件同时要求：

- 当前时间减文件 mtime ≥21,600 秒；
- stable observations ≥3；
- 当前时间减 `first_stable_at_epoch` ≥600 秒。

六项最晚 mtime 为香港时间 `2026-08-25 00:16:28 +08:00`；观察次数与 600 秒跨度已满足。如果 bytes/mtime 不再变化，
年龄门最早在 `2026-08-25 06:16:28 +08:00` 满足，之后 monitor 每轮最多处理一个 ready archive。这个时间不是接纳保证：
任何 bytes 变化会重置稳定身份，未知结构/身份问题会 fail closed 或进入精确拒收流程。

## 3. 新 generator stratum 边界

学长 `dojo-reproduce@b80c0566eca3a335a619d1b9c165a9f050e2f218` 于香港时间 `2026-08-24 23:21:06` 提交：

- AIRA/AIDE 各 operator 新增静态 system policy；
- 原动态任务/code/output/memory context 移入 initial user message；
- 新测试要求 system prompt 无模板变量、动态上下文只位于 user prompt；
- 同一提交还改了 mixed decision/value 训练数据文件和默认 seed，但没有新增 outcome 文档。

归档 mtime 比该 commit 晚约 55 分钟，但 mtime 只代表 tar 文件时间，不是每个 run 的启动 commit。`0823` 目录没有
`senior-experiment-config-manifest-v1` 或等价 outcome 前 sidecar，故不能判断这些 runs 是否使用 `b80c056`，也不能恢复
每 run 的 exact generator/config stratum。

因此边界固定为：若后续 credential-first/结构摄取通过，六项可按预注册时间序进入自然前瞻 Decision Corpus；但不得用于
确认 0.6B→8B exact-stratum scaling、prompt 分离 A/B、producer-config interaction 或单变量因果效应。上述确认仍要求下一批
在 outcome 前写 commit/model/context/operator/hardware/time-limit 等 sidecar，并在 train-run dev 上选 checkpoint 后评估全新
frozen cohort。
