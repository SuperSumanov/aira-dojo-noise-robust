# Prospective intake：0812 全量影子回放

> 本目录保留首次真实 schema 安全回放证据；最终、带完整代码元数据并与 accumulator 串联的回放见
> `../prospective_intake_shadow_0812_v4_20260814/`。本结果未被删除或改写，但不再是当前入口。

日期：2026-08-14。协议：`prospective_drop_intake_v1`。代码 commit：
`e8d0ba26791acdc7ebae7b485eca6c5b63d32a25`。

## 裁决

正式状态为 **`SHADOW_REPLAY_PASS`**。这只是用 pre-activation 0812 tar schema 检验收样、安全与防泄漏链，
不是 prospective 科学结果，也没有计算任何 scorer-vs-grade metric。

- 10 个唯一 archive（已冻结排除 1 个字节重复且错命名的 archive）包含 60 个 run roots；
- 57 个 checkpoint physical runs、3 个 live-only runs 显式排除、9 tasks；
- 1,304 个非空 code endpoints、286 个结构 sibling pairs；
- 全部 run 的 root creation time 均早于激活时刻，因此 eligible runs/endpoints/pairs 均为 0；
- 16,012 个 pre-cutoff endpoint IDs 与 15,912 个 exact-code SHA 均完成检查，两层 overlap 都为 0。

## 安全与盲态

intake 不 extract tar，只流式 materialize `checkpoint/journal.jsonl`；`env_variables.json` 与 live event journal
均未读取或提取。checkpoint bytes 在 JSON parse 前完成 credential-shape 扫描，命中数为 0；raw journal 不落盘。
label 不参与 run/endpoint 选择，summary 的 metric 列表为空。label vault 仍封存在远端，未在本目录复制或打开。
源 archive 的前后 SHA manifest 逐字节相同。

关键哈希：

- `summary.json`：`a4d480eca383e8769c65efd8e2966baaeda58952069367e5cbc526a0528e9858`；
- `archive_audits.json`：`54727df401645d5a769754ced412d3173ec073bcfa2be3b9556f6db735a59b13`；
- `source_provenance.json`：`c1e75e5ab072c544f7e268b99ae0205cb1b24e321018fd7b0c93f79b54cb9f8a`；
- before/after source manifests：
  `60de19da3d5b49387680d9179a3bf668e395b3b9156b15f47b554a14c9cf2a80`。

## 失败链与边界

正式 producer 前保留了三次工程预检失败：远端 GitHub 暂不可达、隔离 checkout 节点缺少 `git-lfs`、系统
Python 缺少 pytest。三次均发生在科学计算前；前两次没有创建 artifact root，第三次 root 只含预检日志。
最终 denylist 改用精确增量 Git bundle、禁用隔离 worktree 的 LFS smudge，并在 `exp` venv 完成；影子回放在
`critic` venv 完成。没有删除或覆盖失败现场。

语料发布继续遵守学长的 LFS 设计：只上传一次写入的不可变分批文件；在有 `git-lfs` 的环境执行
`git lfs pull` 后，以同一 manifest 驱动 `rebuild_corpus.sh`，再用行数与 SHA 验证重建版本逐字节一致；不重复
上传每版合并后的大文件。
