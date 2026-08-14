# Corpus Git LFS 发布契约审计

日期：2026-08-14。目标：核验“不可变分批文件只上传一次，checkout/pull 对应版本后由
`rebuild_corpus.sh` 逐字节重建”的设计是否已被当前 Git 历史真实实现。

## 裁决

发布设计正确，且今后必须遵守；但 **legacy Corpus v4/v5 目前不能由 Git 中现存分批逐字节复原**。
不能把设计意图写成已经验证的 provenance 事实。

## 证据

1. v4 commit `05f9eb5` 和 v5 commit `a619324` 的 `rebuild_corpus.sh` 确实固定了分批顺序，但两个 tree 中
   没有 `.gitattributes`，也没有后来脚本引用的 0802–0805/deep/VALb 分批文件。
2. 分批首次整体进入 Git LFS 是后续 commit `da27852041c131ce9ca609078559ee48482f547a`。因此从该点开始
   才有“Git object 锁定 immutable bytes”的技术事实，不能倒推覆盖更早版本。
3. 在远端以当前 payload、严格按历史脚本顺序流式拼接（不落 merged 文件）：

| 版本顺序 | 文件数 | 当前重放行数 | 当前重放 SHA-256 | 历史记录行数 |
|---|---:|---:|---|---:|
| v4 | 22 | 8,579 | `72505ac667161ae9516ae75d47501fabfc01f767aecd1a909a242fa23ce1b3d6` | 8,607 |
| v5 | 23 | 9,433 | `4f97dce56d388068664d89683133943d62d3eac47108f194906d89e283299fd5` | 9,323 |

4. 在项目、experiments 与 incoming 的有限定深度备份搜索中，没有找到 8,607/9,323 行的 legacy merged
   文件；只找到 9,433 行的 `cards_current.jsonl`。因此当前不能恢复旧版 expected SHA。
5. 当前 manifest 已列 `cards_senior_0809.jsonl`，但 Git tree 此前没有该文件。远端 payload 为
   56,424,624 bytes、1,940 行、1,940 个唯一 ID、0 invalid/duplicate、0 高置信 credential shape，SHA-256
   `133500c0fd731201bde35f44598ada17430684ed2b762326ae006101722a3094`。本轮把它作为单个 immutable
   LFS object 补入，不上传新的 merged corpus。
6. commit `8b38d9acbe68bb2c66825b8f4dce99496f23aedf` 推送后，在集群全新 clone 中执行
   `git lfs install --local` 与 path-scoped pull，得到同一 1,940 行、56,424,624 bytes 和 SHA，证明学长不依赖
   我方 big-data-storage 即可获取。此前两次因 `set -u`/未 local-install 失败的尝试也保留在 receipt，未隐藏。

## 从现在起的发布门

- 新 batch 先在远端隔离提取、redact-before-read、JSON/ID/credential 检查，通过后再 `git add`；LFS pointer
  和 payload SHA 同时记录。
- manifest 只能引用已跟踪且 LFS object 可拉取的 batch；缺失或 pointer-only 必须 fail closed。
- 每次版本发布要保存 manifest SHA、ordered batch payload SHA、重建脚本 commit、输出行数与输出 SHA。
- merged corpus 可作为历史兼容资产保留，但不再为每一版新增/上传，也不充当唯一 source of truth。
- v4/v5 标记 `LEGACY_NOT_BYTE_REPRODUCIBLE_FROM_CURRENT_GIT`；除非找回当时原始 payload/merged hash，
  不补造一个“同名但不同字节”的版本。
