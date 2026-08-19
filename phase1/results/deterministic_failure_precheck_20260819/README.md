# Deterministic failure precheck v1

日期：2026-08-19。裁决：`INSUFFICIENT_DETERMINISTIC_PRECHECK_FEASIBILITY`。

结果前 commit `863a3b0c33784a00da7e6cc3614e5b8d65df5a1e` 固定了无学习规则和全部资格门。输入为
494 unique-parent train-only success/failure pairs、13 tasks、126 physical runs；frozen b0/b1/b2 runs 零交集。
规则只检查 Python AST 是否可解析以及是否静态出现保守的 artifact writer，不读取 numeric grade，不输出 raw code，
GPU/API/底座更新均为 0。

远端完整测试为 `389 passed in 36.84s`。producer 双跑三个产物逐字节一致，summary SHA256=
`3b738ea56f11b80cc40375bd669cd4fd78310f1baade3679ec75bb1c73547b54`；不 import producer 的 verifier
两次均给出 `INDEPENDENT_DETERMINISTIC_PRECHECK_ARTIFACT_VERIFIED`，verification SHA256=
`2a02170db3f37e2cf53b609307ff3fb3989a54e550021f03de96080f8f450f33`。

固定规则只拒绝 1/494 failures=`0.0020242914979757085`，同时误拒绝 1/494 successes=
`0.0020242914979757085`，balanced-pair precision=0.5、paired net=0.0。两次拒绝都来自
`denoising-dirty-documents` 的 `REJECT_NO_ARTIFACT_WRITER`；caught tasks=1。task/run-clustered paired-net CI 都是
`[0.0,0.0]`。failure catch、任务覆盖和 paired-net 三个核心门失败。

因此 v1 关闭。不得在旧 494 对上查看代码后增加 writer、改字符串匹配、筛任务或调门。结果说明这些真实 execution
failures 几乎都拥有语法正确且表面完整的 submission writer；廉价静态 contract check 不能替代 execution-aware
evaluator。由于本实验明确预注册为 retrospective feasibility，不产生前瞻方法、search utility 或跨 agent 主张。
