# 给学长：最新 outcome 的执行交接与三个待确认项

日期：2026-08-30

当前公开可见的最新 outcome 仍是 `src/mle_critic/docs/outcomes/0828/MIXED_PAIRWISE_REWARD_AND_RL_EXPERIMENTS.md`，
`dojo-reproduce` head=`5baccb170ce287f9c8eed7b23ccf693a0268515a`。若另有 0829/0830 outcome，请 push 到同一路径；当前没有
读取到比 0828 更新的公开文件。

## 已执行

1. 全上下文 evaluator 诊断已冻结为 8 historical pairs × 4 models × AB/BA=`64 calls`，scheduler stop=`2 USD`，0 GPU。
   panel、完整 task/resource/code prompt、模型顺序、解析与顺序稳定门均冻结；accuracy 不作 smoke gate。
2. live transport 已有 ZDR、deny collection、单 endpoint/no fallback、router metadata、context-compression kill、pre-call
   intent journal、逐调用 cost upper bound 与 ambiguous-call no-retry。
3. 2026-08-30 公共 catalog 复查发现 DeepSeek V4 Flash 价格漂移；已追加式刷新而未覆盖旧协议。远端 fixed venv 回归
   focused/full=`9/1680 passed`，尚未发任何 API 请求。
4. config-v2 producer hook 对最新 5baccb clean apply，focused=`19 passed`；但尚未部署，所以当前新语料不能用于
   exact-stratum clean scaling confirmation。

## 请学长处理/确认

1. 请在远端 `/research/d7/spc/yzyang4/aira-dojo/.env` 中直接增加 `OPENROUTER_API_KEY`，并保持文件 mode 0600。
   不要把值再发到 Git、命令或日志；安装后只需告知“变量已就绪”。当前只核变量名仍为 absent，因此 smoke fail-closed。
2. 请 review/apply `0001-Add-prospective-config-v2-producer-hook-18-tests.patch`（SHA-256=
   `56a3e4b61918e1b06830712d418ed27ef5135017eab2b9e833b92c626054c9a5`），未来生产显式设置
   `DOJO_CONFIG_V2_SIDECAR=1` 与稳定 `DOJO_GENERATOR_RELEASE`；否则 0.6B→8B scaling 仍无法做无 cross-config 的正式确认。
3. outcome 的 Qwen generator 微调会更新 agent 底座，与项目长期 hard NO 冲突；当前执行边界保持 fixed generator +
   independent critic/verifier。若你想改变这一项目级边界，请明确说明它是独立 demo/论文支线，并先和用户确认；在此之前不启动。

RL trajectory 比较只接收脱敏导出；请不要提供带访问凭据的 W&B URL。建议导出 run/config、可公开 prompt、final answer、
reward/grade metadata 和资源回执，隐藏 reasoning 与所有 token。当前不会访问 outcome 中已有的 credential-bearing 链接。

科学上我们不会把 generic active learning 或 generator-verifier self-improvement 当 novelty。可保留的窄主张是：面对真实 MLE
execution labels 的成本、sibling graph label amplification、task/run heterogeneity 与 run-clean future confirmation，能否在固定
generator 下提高每个 executed endpoint 的 downstream critic label efficiency。OpenRouter smoke 只验证 evaluator 是否有资格成为
该 acquisition prior，不本身声称搜索提升。
