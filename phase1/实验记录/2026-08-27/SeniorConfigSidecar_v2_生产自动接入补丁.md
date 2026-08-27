# Senior config-v2：真实 producer 自动接入补丁

日期：2026-08-27
状态：`PATCH_VERIFIED_NOT_DEPLOYED`
上游 base：`dojo-reproduce@61459c0a1248900079dafed7c505afa87e476b40`

## 1. 本轮解决了什么

8 月 25 日已有单-run exporter、原子 batch exporter、consumer validator 和 prompt-sensitive solver 指纹，但真实
producer 一直没有生成 `*.config_v2.jsonl`；截至本轮最新 monitor 仍为 `sidecar_count=0`。本轮没有再造第三个离线
exporter，而是在学长最新分支的 detached worktree 中把同一 v2 协议接入 `dojo.main_run` 的 outcome-before 路径，形成
维护者可 review/cherry-pick 的 patch，未直接改写学长分支。

补丁：`phase1/upstream_patches/0001-Add-prospective-config-v2-producer-hook-18-tests.patch`
SHA-256：`56a3e4b61918e1b06830712d418ed27ef5135017eab2b9e833b92c626054c9a5`

## 2. 运行语义与公平边界

- 默认 `DOJO_CONFIG_V2_SIDECAR` 缺失或为 `0`，行为逐字节保持原路径；
- 只有设为精确字面量 `1` 才启用，其他值按拼写错误拒绝；
- 启用时必须显式给 `DOJO_GENERATOR_RELEASE`，`unknown` 可诚实保存 provenance，但不能通过 interaction completeness；
- `HARDWARE` 继续由既有 `main_run` 在 hook 前生成，不读取 `env_variables.json`；
- hook 位于 `cfg.save()` 之后、环境 dump 与 task/solver 构造之前，因此不读任何运行结果；
- sidecar 只写 10 个公开字段与两个 SHA-256，完整 solver projection 只在内存 canonicalize/hash，不落盘；
- prompt、operator、client、search、retry、memory、package 或 budget 任一变化都会改变 solver hash；只删除
  `solver.exp_name` 与 `solver.checkpoint_path` 两个 run-specific 路径；
- 混合 operator clients、凭据形状、非法 ID/date、非正/非有限 timeout、schema/hash 异常均在输出前失败；
- 完整临时文件先 fsync，再以 no-clobber hard link 原子发布，消除 check-then-replace 覆盖竞态；
- checkpoint/resume 只允许只读复用逐字节完全相同的 sidecar；不同字节永不覆盖；
- collector 只接受调用者显式列出的单-run sidecar，不扫目录、不打开 tar、不推断缺行，整批排序、去重、验 hash 后
  原子发布 archive sibling。

这些改动不改变 task、operator、agent model、搜索预算、evaluation 或 agent 底座，也不训练模型、不提交 GPU。

## 3. 验证链

本地 Windows：`18 passed, 1 skipped`；skip 仅因当前用户无 symlink 创建权限。独立 cross-implementation check 在
128 个合法变体上证明 upstream row 与 `phase1/senior_experiment_config_v2.py` 的 dict/canonical bytes 完全相同；
mixed client、credential-shaped prompt、坏 run ID、NaN limit 四类非法输入两边都拒绝。

远端失败史没有覆盖：

1. v1 在 checkout 前因 `env_setup.sh` 与 caller `nounset` 冲突失败；
2. v2 完成 apply/compile 后，因 `/usr/bin/python` 没有 pytest 而未启动测试；
3. v3 focused=`19 passed`，但 full collection 因验证环境未设 `LOGGING_DIR` 出现 6 个同源错误；
4. v4 使用既有 `/research/d7/spc/yzyang4/venvs/aira/bin/python`，并把所有测试目录变量限定在 fresh formal root，
   显式 `CUDA_VISIBLE_DEVICES=""`、`WANDB_MODE=disabled`，最终 focused=`19 passed in 0.26s`，full=
   `84 passed, 1 skipped, 26 warnings in 32.69s`，128/4 等价审计通过，工作树前后 clean，filename/blob secret
   hits=`0/0`。

正式根：`/research/d7/spc/yzyang4/config-v2-producer-hook/verify_fa2151b_v4`
正式 `SHA256SUMS` 自身 SHA-256：`fbb9536c760c9a14ba9e7da044d1f32fe7f748ff54298f27fb1951bbe743c2b0`
本地镜像包：`phase1/results/senior_config_v2_producer_hook_20260827_56a3e4b/`；其 `SHA256SUMS`
SHA-256=`816ca815e9614aaa762227a58f8f7d8a46e3c5bf218d36bf3aa807ddcf3f1b53`。

## 4. 与 8 月 19 日旧 patch 的关系

`0001-Enforce-exact-experiment-strata-6-focused-tests-pass.patch` 处理的是 Cards 已生成后的 v1 tuple 同层配对与 pair
receipt；它不记录 generator release、不覆盖 prompt/完整 solver，也不在 producer outcome-before 写 sidecar。本轮补丁
解决更早的配置可识别性与生产部署缺口，两者不是重复实现。未来完整链应为：producer v2 sidecar → immutable archive
sibling → source/expected-run/config composition receipt → outcome-blind support gate → 另行批准 clean scaling 矩阵。

## 5. 当前不能说什么

- 尚未部署到学长分支，真实 sidecar 仍为 0；
- 不能回填 0825 或更早 archives，不能把它们变成 exact-stratum confirmation；
- patch/test 不是 scaling 正结果、predictor accuracy 或 search utility；
- 不自动授权训练或 GPU。只有学长 review/cherry-pick 后的**下一批**真实 runs 能进入 config-v2 支持审计；支持门通过后
  仍需先提交模型×数据×seed×GPU·时矩阵。
