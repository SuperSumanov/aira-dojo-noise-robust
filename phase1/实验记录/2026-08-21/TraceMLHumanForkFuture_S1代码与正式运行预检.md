# TraceML Human Fork Future：S1 代码与正式运行预检

日期：2026-08-21。状态：`CODE_FROZEN_BEFORE_REAL_SUPPORT_READ`。本记录和两套实现必须先提交；真实 graph
column values、fork/support/outcome 聚合数只允许在该 commit 的干净远端 worktree 中读取。

## 固定设计与 13 项预检

1. 当前方向：Decision Corpus + Predictor Benchmark 的 frozen future-potential extension，不恢复旧 HCE/TD/probe；
2. 唯一问题：TraceML canonical human forks 是否有足够 task-unseen、parent-balanced、finite eventual support 进入 S2；
3. 输入：S0 固定 revision 与 9 文件 size/SHA，训练 train/dev SHA 分别固定为 `0ec49d76...` / `3b3fb53f...`；
4. 划分：从 train+dev JSONL 的 `task` 并集排除 competition，绝不读取 frozen test；
5. 样本：共享精确 parent 的全部不同 first-version fork child kernel 无序组合，不按 outcome 抽样；
6. 模型：S1 不训练、不评分 predictor；GPU/API/底座更新均为 0；
7. 统计：固定 tasks≥20、parents≥100、finite non-tie pairs≥500、dominant share≤0.20；
8. RNG：无随机过程；producer/verifier 应逐字节复现；
9. 资源：CPU-only；只读约 52MB graph tables，不下载 2.9GB raw notebook；
10. 完整性：node/kernel/tree/manifest 唯一 join、score direction、depth+1、first version、edge-table exact multiplicity、
    child-kernel uniqueness、credential-shaped identity 拒绝均由两套不互相 import 的实现重算；
11. 失败：任何 identity/join/direction 门失败，不打开 score columns；任何 support/raw-path declaration 门失败，不进 S2；
12. 恢复：fresh output + detached no-smudge worktree，不覆盖旧 artifact；
13. 封存：完整命令、环境版本、focused/full tests、两次 producer、两次 verifier、syscall 禁止路径计数、凭据扫描、
    SHA manifest 与只读权限同时保存。

故障注入测试固定覆盖：duplicate node、wrong depth、non-first fork、direction mismatch、missing edge、duplicate child
kernel、task overlap/dominance、tie/nonfinite、missing raw path、credential shape。Windows focused=9/9；本机全量收集因
缺少 scipy/sklearn 而不能代表目标环境，正式 launcher 强制在既有远端实验 venv 中先跑 focused 与全部 `phase1/tests`，
任一失败即在读取真实 graph values 前停止。

## 预读 attempt erratum

commit `878e719...` 的 launcher 先通过 focused tests，随后在 full suite 24% 后暴露 CPU 线程合同遗漏：一个仅
60-row 的既有合成 HGB 测试启用了约 30 核，持续高 CPU 而没有失败。该 attempt 在 producer command 生成前被
中止；远端不存在 `summary_1.json`，所以 graph column values、score columns、support 与 effect 读取均为 0。
旧目录原样标记 `ABORTED_BEFORE_GRAPH_READ_THREAD_OVERSUBSCRIPTION`。正式重跑在新 commit 中显式固定
OpenBLAS/OMP/MKL/NumExpr/BLIS/vecLib=1 与 `PYTHONHASHSEED=0`，阈值、数据、模型和统计均不改变。
