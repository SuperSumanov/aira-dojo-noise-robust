# SourceChoiceDecisionView S2v2：修复协议与执行前冻结

日期：2026-08-21。状态：结果前冻结。该协议由 0DL 的模型前完整性审计触发，只修复已确认的
`operator` 大小写 provenance proxy，不是结果 rescue，也不允许借机改样本或标签。

## 唯一科学问题与允许 diff

能否在不改 3,000 groups、8,027 candidates、candidate/group identity、winner、数组顺序、完整 code bytes、
`step/depth`、train/frozen/extension role 和 cluster metadata 的条件下，把原始 operator 大小写规范化为固定
`Draft/Improve` 枚举，并从 model JSONL 中彻底消除 journal-recovery proxy？

唯一允许的字段变换是：先验证 operator 为非空字符串，再做 Unicode `casefold()`；`draft -> Draft`、
`improve -> Improve`，其他值 fail closed。model schema 升为 `source-choice-decision-group-v2`，旧 v1 evaluator
不再接受。不得删除 899 个恢复候选，不得根据 winner 改字段，不得读取 frozen/extension vault。

冻结输入计数：

- train：`Draft`=93、`Improve`=4,949、`improve`=697；输出必须为 93/5,646；
- frozen：29/1,820/192；输出必须为 29/2,012；
- extension：12/225/10；输出必须为 12/235；
- canonicalized 必须为 train/frozen/extension=697/192/10，合计 899；输出小写或未知 operator=0。

## 13 项预检

1. 方向：只执行 0DL input-integrity correction；不恢复 HCE、TD/RL、probe、多保真或旧 selector。
2. 问题：验证 operator proxy 的 schema-level removal；不估 predictor accuracy 或搜索收益。
3. 输入：只读 S1v2 `5d6de6e-v2` 的 public role files 与 summary/manifest/independent verification；六个 SHA
   继续绑定在 protocol；不读取 senior tarball 或 raw API credential。
4. 单位：3,000 groups / 8,027 unique candidate IDs；group、candidate、winner、role、顺序逐项闭合。
5. 标签：只复制 2,109 个 public train winners；frozen/extension public winner fields 必须为 0/0，vault 路径
   syscall 命中必须为 0。
6. 旋钮产物验证：summary 必须逐 role 报 raw/canonical operator counts；不是只相信配置值。
7. 泄漏三查：blocked candidate fields 为 0；输出 operator 只允许 `Draft/Improve`；group/candidate/code SHA 与
   source 一致，run/parent 只在 cluster manifest。
8. 顺序与 RNG：无抽样、无 RNG、无 shuffle；candidate SHA 字典序逐行保留；producer 两次必须 byte-identical。
9. 独立复核：verifier 不 import producer，独立重建每个 candidate 的 operator 规范化与全部 census；运行两次。
10. 评估器：sealed evaluator 只接受 v2 schema 和固定 operator 枚举；extra field、v1 schema 或未知枚举失败。
11. 训练侧功效：本轮 model fits=0，故不作功效/性能结论；v2 通过后才另立 train-only OOF 协议。
12. 资源/墙钟：CPU only、GPU=0、API=0、base LLM update=0；focused smoke 已 10 passed，正式预计 10 分钟内；
    runner 每步由 `set -eo pipefail` fail closed，失败 staging 保留真实 rc。
13. 发布：producer×2、verifier×2、focused/full tests、forbidden path、credential filename/content、clean worktree、
    read-only 与 SHA manifest 全通过才晋升；否则保留失败目录，不发布模型视图。

## 裁决门

只有全部预检和正式门同时通过，状态才可为 `SOURCE_CHOICE_DECISION_VIEW_V2_READY`。任何计数、身份、代码、
winner、顺序、vault-path、测试、重复性或秘密扫描失败均为 `BLOCKED`；不允许第三套映射或删除候选补救。
