# Raw choice-set completeness：全量执行前检查

冻结时间：2026-08-15（结果前）。实现验收 commit：
`5bc3e4b8b1cc8411bc20c580079a03141b5b32bf`。该 commit 已在全新 Linux worktree 通过 10 项聚焦测试和
全部 285 项 `phase1/tests`；安全扫描可疑文件名与高置信凭据均为 0。

## 配置与预算

固定输入为 v11 `cards_current_v11.jsonl`、`card_run_map.json` 和 train/frozen/extension 三个 b0 文件。
只运行一个 deterministic producer 和一个不导入 producer 的 independent verifier；不做 sweep、bootstrap、
模型拟合或重试。预计顺序读取约两遍 306 MB cards，CPU 墙钟小于 10 分钟，GPU=0、API=0、底座更新=0。

## 13 项 preflight

1. **唯一问题**：发布 b0 是完整 source sibling choice set，还是有限标签过滤后的 labeled sibling fragment。
2. **分析单位**：固定为 `(release_role, parent_id)`；不得改成 pair-weighted headline 掩盖 parent 缺失。
3. **输入版本**：只接受上述 commit 所引用的 v11 inputs；每个输入在产物中记录 SHA-256。
4. **结果隔离**：禁止读取 first-960、prospective label vault、冻结模型预测、pair gap 或 better/worse 方向。
5. **card 隔离**：禁止使用 code、stdout、runtime、submission 或 label 数值大小；只允许有限/非有限 availability bit。
6. **source 证据**：只使用 card 构建前已计算的 `n_siblings+1` 和 parent `children_ids`；不从均值反推 source size。
7. **完整性门**：endpoint 必须是同 task/run/parent 的 finite retained child；`set_size` 必须等于 finite child 数。
8. **完整 source 门**：每个 parent 的 `n_siblings+1` 必须一致、不小于 retained children，且 raw/finite retention 均为 1。
9. **>5 处理**：即使结构完整，只要 source size>5 仍进入 provenance hold，不自动放行完整 choice-set 主张。
10. **正负控制**：合成完整 3-child set 必须 PASS；2-of-source-5 必须判 fragment；6-child 完整 set 必须 provenance hold。
11. **独立复核**：verifier 不 import producer，重建每个 parent、role aggregate、criteria、hash 和最终 verdict。
12. **失败保留**：不得按 task、run、set size、tie 或结果删行；结构错误判 INVALID，不把坏数据美化为 fragment。
13. **原子产物**：输出目录必须预先不存在；producer manifest、独立 receipt、命令和完整 per-parent CSV 全部保留。

## 冻结裁决

- 全部 integrity、endpoint coverage 和 source retention 通过，且无未解释的 source size>5：允许完整 source choice-set 主张。
- integrity 通过但 endpoint/source retention 任一不满 1：统一改称 **labeled sibling fragment**。
- endpoint、声明、source metadata、run/task 或 parent metadata 任一错误：发布结构判 INVALID，先修数据再做科学解释。

阈值在全量结果产生后不得修改。该审计本身不是方法收益实验；无论结果好坏，都不能用它解锁 E2/E3。
