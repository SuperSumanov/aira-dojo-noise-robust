# FOREAGENT UST outcome sensitivity：v1 线程过订阅失效与 v2 执行修正

时间：2026-08-30
论文容器：Decision Corpus + Predictor Benchmark + Audit Protocol

## 裁决

第一次 formal **不是科学失败，也不是可引用结果**。它在生成任何 `result_a/b.json` 或
`verification_a/b.json` 之前，因为未限制 BLAS 线程而出现严重过订阅；作业已终止，原根完整保留。
v2 只增加执行线程上限，所有科学 estimand、支持集、bootstrap、verifier 与分类政策不变。

## v1 证据

- exact commit：`5abfbd44d1459f9170904e0c8e1b954ead5628df`
- 父科学协议 SHA-256：`7d47b1aa6ef3ffb61c47f1fe3d6631a5bb7b2c97228de8a7c9192b9fc557a425`
- 保留根：`/research/d7/spc/yzyang4/foreagent-ust-outcome-sensitivity/formal-5abfbd4-v1`
- focused：`11 passed in 0.36s`
- full suite 已完成：270 个测试
- 终止时 active test：`test_critic_component_static_suite.py::test_hash_gate_and_tamper_detection`
- 终止时进程：119 threads，`2948%` CPU，elapsed=`00:09:08`，CPU time=`04:29:28`
- `COMPLETE`：不存在
- result/verification 文件：0
- 科学结果生成/读取：否/否

`FAILED_RC=0` 是 shell 在等待子进程时被终止后由 EXIT trap 写出的不充分状态，不能覆盖显式的
`ABORTED_ENGINEERING_OVERSUBSCRIPTION` 标记。后续任何自动验收必须先拒绝带该标记的根。

## 单线程因果对照

在同一 exact worktree 对同一 active test 显式设置：

```text
OPENBLAS_NUM_THREADS=1
OMP_NUM_THREADS=1
MKL_NUM_THREADS=1
NUMEXPR_NUM_THREADS=1
```

复跑得到 `1 passed, 4 warnings`，pytest=`2.95s`，总墙钟=`10.14s`，CPU=`65%`，max RSS=`262848 KiB`。
这支持“线程过订阅导致工程性停滞”，而不是测试逻辑、输入或科学协议错误。

## v2 唯一改动

1. runner 在加载远端环境后、运行任何测试或 analyzer 前 export 四项 `*_NUM_THREADS=1`；
2. 新增 additive execution addendum，并把其 SHA 作为 formal CLI 和 `source_bindings.txt` 的必检项；
3. 测试明确验证线程上限、父协议不可变、producer/verifier 不变和 addendum 当前源绑定。

没有修改：

- exact common finite support=`18,381 pairs / 26 tasks`；
- raw pair micro、UST rank micro、raw task macro、UST task macro；
- DeepSeek−GPT paired estimands；
- 20,000 次 task bootstrap 与 seeds；
- LOTO tolerance；
- producer/verifier；
- prior `INSUFFICIENT-SUPPORT`；
- 任何成功阈值（仍然没有）；
- GPU、付费 API、model fit、base update（均为 0）。

## 证据 SHA-256

```text
f09b8476cc87586231ef1a10bf1ecf56099c26eb07c3b7dbdd172badbe833429  ABORTED_ENGINEERING_OVERSUBSCRIPTION.txt
0e2d31ce7d838369b75541b28a49785da6b4f3d0f11d8cea4a5e46c5e5bd2521  abort_process_before.txt
6d98ae01fdac71a343c8d34d308645e4d308680ff8e737f23c1cd4a87882549e  aborted_at_utc.txt
a4057385d721cbf43b0d5689af9d064525f5df10db7ed802497e0465b3a873be  single_thread_control.txt
673646b345fca1d5a4161b680ef4ea691c352affe7048633823d59ce0f3e18c3  single_thread_control_time.txt
```

## 下一步

先公开 v2 exact source，再用 fresh detached worktree 和 fresh output root 执行 13 项 pre-flight、focused/full tests、
producer A/B、independent verifier A/B、trace/security/manifest/mode/read-only 全门。只有全部完成后才允许读取历史公开 aggregate。
