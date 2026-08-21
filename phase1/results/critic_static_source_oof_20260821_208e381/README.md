# Parent-closed static-source OOF：正式裁决

- 正式代码 commit：`208e38135c0dc10d8430095a41c8008c063ff8a0`
- 证据层级：retrospective outer-train parent-closed component OOF
- 数据：5,240 pairs、28 tasks、1,711 parents、152 parent-closed supercomponents、5 folds
- 正式状态：`STATIC_SOURCE_OOF_INDEPENDENTLY_VERIFIED_NO_NARROW_POSITIVE`
- 结论：预注册的“code-only 信号不能由 lineage shortcut 解释”窄正面门未通过。

核心结果：

| arm / paired delta | task-macro point (95% task CI) | pair/parent point (95% parent CI) |
|---|---|---|
| code-only | 0.529716 [0.497905, 0.566335] | 0.520420 [0.503049, 0.537910] |
| lineage-only | 0.521325 [0.499948, 0.545014] | 0.505630 [0.490855, 0.520632] |
| all-static | 0.534409 [0.507148, 0.563707] | 0.528435 [0.511247, 0.545622] |
| code − lineage | +0.008391 [-0.031204, +0.047777] | +0.014790 [-0.008262, +0.037835] |
| code − all | −0.004693 [-0.018386, +0.011119] | −0.008015 [-0.020497, +0.004262] |

code − lineage 的 leave-one-task-out 最小点估计为 −0.003203。code-only 的 task CI 跨 0.5，
code − lineage 的两类配对 CI 均跨 0，code − all 的两类非劣门也失败。因此不得声称 code-only
独立解释已有静态信号。all-static 的两类 chance CI 下界高于 0.5，说明 parent closure 后仍有弱的联合静态
信号，但本实验没有把它归因到代码、lineage 或两者交互中的任何单一来源。

完整性：producer×2 与不 import producer 的 full-refit verifier×2 精确一致；逐 pair/fold/task/parent/
summary 最大绝对差均为 0。40-entry output manifest 全部通过，7 个 diff/stderr 文件为空，目录不可写，
credential-shape 扫描为 0；focused tests 8 passed，phase tests 558 passed。

完整只读产物位于：
`/research/d7/spc/yzyang4/critic-static-source-oof/208e381-v2`。
`output_manifest.sha256` 自身 SHA256 为
`27257d96bdcc32417333e8786237be38d6a84fa68e145db1ecc0f8a2067acff4`。

本目录只提交紧凑裁决与验证凭证；逐 pair/fold 产物以只读远端目录及 manifest 为准。
