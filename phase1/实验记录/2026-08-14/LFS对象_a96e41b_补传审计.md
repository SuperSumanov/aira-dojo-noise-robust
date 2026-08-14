# LFS 对象 `a96e41b…` 补传审计（2026-08-14）

## 触发

在精确 commit `59b5b8c698c6d687510cc184034d887619324243` 创建全新远端 worktree 时，GitHub 对
`phase1/results/heterogeneous_oof_v11_20260814/full_artifacts.tar.gz` 返回 LFS 404。
对应 OID 为 `a96e41b9f72c56c49b9af60ed1eead0d1b6daf21efe365a0f1a732590fc5eae4`。

## 补传前审计

- 本地 payload 大小：`1119807` bytes；
- 本地 SHA-256 与 OID 完全一致；
- tar 可完整列出：43 members、32 regular files；
- 可疑成员名命中：0；
- 流式高置信凭据文件命中：0；
- staged 可疑文件名命中：0。

扫描没有解压到工作区，也没有打印成员内容。通过后只补传这个既有 OID，没有创建或修改 Git commit。

## 补传后独立验证

在集群端从 `fork` 对精确 commit `59b5b8c698c6d687510cc184034d887619324243` 和精确路径做
include-only LFS fetch。对象落盘大小仍为 `1119807` bytes，重新计算 SHA-256 仍等于完整 OID，状态：

`VERIFIED_REMOTE_LFS_OBJECT`

这只修复仓库可获取性，不改变 `heterogeneous_oof_v11` 的既有科学裁决。
