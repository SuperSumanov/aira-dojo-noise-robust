# RPM Qwen tokenizer-only synthetic smoke：13 项预飞（2026-09-02）

> 状态：`READY_AFTER_EXACT_PUBLIC_COMMIT`。本预飞只授权一次无结果、无模型权重、无 GPU/API 的合成 tokenizer
> smoke；不授权真实 panel、模型调用、预测生成或结果 join。启动时若不能绑定刚推送的 exact public commit，立即停止。

1. **问题 / 决策** — 验证 hash-bound Qwen tokenizer、官方 chat template、AB/BA 完整渲染与 whole-node prefix
   packing 能在固定远端解释器上由 producer 和独立 verifier 逐字节重建。`PASS`。
2. **Estimand** — 工程 estimand 仅为合成输入的 packed-prefix identity、两个 orientation 的 token counts 与 hashes；
   不是 accuracy、utility、latency 或模型质量。`PASS`。
3. **输入** — 只使用仓库内 frozen prompt、合成 task/candidate/context，以及 pinned revision 的五个非权重公开文件；
   不打开 first-960/Target-300/Target-522 或任何 outcome vault。`PASS`。
4. **泄漏 / 隔离** — 合成输入不含真实 candidate identity、label、outcome、prediction、accuracy 或 utility；所有输入先过
   credential-shape gate。`PASS`。
5. **对照 / 阳性控制** — A/B 重跑必须逐字节相同；独立 verifier 不 import producer/prompt renderer；额外测试
   empty-context、首个 overflow、非 canonical line、credential shape、权重文件拒绝。`PASS`。
6. **样本量** — 一个多节点合成 request 足够验证确定性路径；它不用于统计推断，禁止从单例推断数据覆盖或效果。`PASS`。
7. **随机性** — tokenizer 与 packing 完全确定；无 sampling、seed、temperature 或模型 generation。`PASS`。
8. **推断 / 报告** — 只报告 exact bytes/SHA、token counts、included/eligible node counts、测试 pass/fail；不得报告或暗示
   predictor 效果。`PASS`。
9. **成本 / 配额** — 下载约 13 MB tokenizer/config/card；预计 CPU <5 分钟、GPU=0、paid API=0、model fit=0。
   如出现权重下载或费用请求立即停止。`PASS`。
10. **恢复 / 幂等** — 使用 fresh detached no-smudge exact checkout、独立临时 root、原子输出与 A/B 文件；已有输出
    拒绝覆盖。失败保留日志，不在原位修补成功记录。`PASS`。
11. **环境** — 固定 `/research/d7/spc/yzyang4/venvs/exp/bin/python`，运行时版本必须精确为
    transformers/tokenizers/huggingface-hub=`4.57.1/0.22.1/0.36.0`；版本漂移 fail-closed。`PASS`。
12. **安全** — 下载 allowlist 只有五个非权重文件；本地路径与 changed paths 执行 filename/content credential scan；
    不读取或回显任何密钥。`PASS`。
13. **晋级 / 停止** — 只有 exact commit、artifact hashes、A/B、独立 verifier、focused/full tests、stderr、changed-file
    security scan 全部通过才记录 receipt。即便通过，也只关闭 transfer tokenizer/prefix packing；parent-BFS/non-buggy、
    live calls 与 Table 4B 保持 blocked/sealed。`PASS`。
