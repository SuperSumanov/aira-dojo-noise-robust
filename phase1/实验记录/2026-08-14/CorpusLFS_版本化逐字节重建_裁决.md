# Corpus LFS 版本化逐字节重建：裁决

日期：2026-08-14。学长确认的发布契约是：Git LFS 只保存一次写入、之后不再修改的分批
JSONL；每个语料版本由这些分批组合得到；`git lfs pull` 后运行 `rebuild_corpus.sh` 应当
得到逐字节一致的目标版本，而不是反复上传每个 merged corpus。

## 裁决

该契约现已对 **v6–v11** 真正落地并通过原始文件 `cmp`；**v4/v5 仍不可恢复，不能伪装成
可复现版本**。稳定论文主线没有改变；这是数据发布与可复现性资产，不是新的方法收益。

## 为什么原脚本还不够

原实现只有会持续增长的 `corpus_manifest.txt`，没有版本选择、分批 hash lock、输出 byte
count 或输出 SHA；而且 `add_run_id.py` 后续改变过 provenance、task type 和非有限标签处理。
直接用最新 transformer 重放 v9 时，行数仍为 14,323，但比冻结 v9 多 744,500 bytes，SHA
不同。因此“批次不可变”是必要条件，但版本还必须冻结**顺序、批次内容、变换协议和输出**。

## 新发布契约

1. `phase1/corpus_releases/batch_registry.json` 是 append-only registry；每条记录固定 filename、
   SHA-256、bytes 和 rows。
2. 每个 `vN.json` 只选择 registry 的固定前缀，并保存该有序前缀的 canonical lock SHA；以后
   追加新 batch 不会改变旧版，插入或修改旧记录会立即失败。
3. v6–v9 绑定 `legacy-run-id-v6-basic`；v10 和 v11 分别绑定自己的 sanitized taxonomy，防止
   新任务改变旧版字节。
4. builder 在落盘前验证每个 batch 的三元组和 legacy segmentation V1/V2；使用同目录临时文件
   原子写出；只有输出 rows/bytes/SHA 三者全等才 promote。
5. 未 smudge 的 LFS pointer、错误 remote、缺批、batch 漂移、未知任务、重复 card ID、输出漂移
   均 fail closed。
6. `.gitattributes` 从过宽的 `cards_*.jsonl` 收窄到真实 LFS family，避免 16 个历史普通 Git blob
   在 fresh worktree 中被误报为“应为 pointer”。另有两个旧 runsplit 普通 blob 警告，不属于本轮
   corpus batch 契约，未重写历史。

## 原始目标逐字节复核

| 版本 | batches | rows | bytes | runs | SHA-256 | `cmp` |
|---|---:|---:|---:|---:|---|---|
| v6 | 23 | 9,433 | 160,043,881 | 457 | `f535df76…9aa2` | PASS |
| v7 | 25 | 10,755 | 184,329,618 | 515 | `32d0ebff…f93d0` | PASS |
| v8 | 26 | 12,383 | 214,866,914 | 553 | `d0cd34ea…9b4f2` | PASS |
| v9 | 27 | 14,323 | 271,496,136 | 586 | `daeb29fc…9407f` | PASS |
| v10 | 28 | 15,158 | 287,373,736 | 624 | `836c2ace…60d74` | PASS |
| v11 | 29 | 16,012 | 305,750,663 | 667 | `6794acbf…01b75` | PASS |

最终实现 commit 为 `73fd5f6a927e8deeb07d84372e1ba87fb7d2b3c5`。远端最终相关测试 46 项
通过；所有正式回放均为 0 GPU、0 API、未做 outcome/label 分析。合并输出仅在经过绝对路径检查的
临时目录生成，`cmp` 后删除；永久保留 receipt、summary 与失败日志。

## v4/v5 的不可恢复缺口

- v4 历史记录 8,607 行；现存 22-batch 前缀只有 8,579 行。
- v5 历史记录 9,323 行；现存 23-batch 前缀有 9,433 行；原 0805 版本应贡献 716 行，但首次
  LFS 发布时同名 payload 已是 854 行。
- LFS 契约直到 commit `da27852` 才开始，且没有找到旧 merged 备份。因此不能为 v4/v5 补写
  “同名不同字节”的假版本。只有找回原 payload 或原 merged artifact 才能改变此裁决。

## 诚实失败记录

1. 临时 worktree 首次向 Facebook upstream 拉 LFS，0809 object 404；改为显式 fork remote。
2. 最新 transformer 重放 v9 行数相同但 SHA 不同；由此增加 release-specific protocol。
3. 一次 helper 假定不存在的 `/research/.../tmp`，在重建前停止；改用已存在且路径检查过的目录。
4. 第一个 sanitized snapshot 漏掉 v11 新任务 `dogs-vs-cats-redux-kernels-edition`；v6–v10 通过、
   v11 fail closed。随后拆分 v10/v11 taxonomy 并增加回归测试，v11 才逐字节通过。
5. v10 最终确认 helper 首次漏写 `cd`，rc=127 且 builder 未运行；修复后在 final commit 通过。

## 学长可直接使用

```bash
git lfs install --local
git lfs pull --include='phase1/cards_*.jsonl'
bash phase1/rebuild_corpus.sh v11 /tmp/cards_current_v11.jsonl
```

若仓库配置为 `origin=facebookresearch`、`fork=SuperSumanov`，第二行改为
`git lfs pull fork --include='phase1/cards_*.jsonl'`。脚本会在输出旁写 receipt。

直接证据：

- `phase1/corpus_releases/`
- `phase1/results/corpus_release_contract_20260814_73fd5f6/`
- `phase1/results/balanced_manifest_e0_20260814_4ff44dd/`
