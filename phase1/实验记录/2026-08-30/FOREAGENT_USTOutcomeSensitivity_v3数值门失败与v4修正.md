# FOREAGENT UST outcome sensitivity：v3 数值门失败与 v4 修正

时间：2026-08-30

## 裁决

v3 是第三个无结果 formal 根：代码与身份修正均通过测试，producer 只因 raw reproduction 的 `1e-15` 绝对容差
比合法 binary64 求和误差更窄而 fail-closed。v4 把该生产门改为公式化的 `64 × binary64 epsilon`，不修改任何指标。

## v3 证据

- exact commit：`93154e54987c3fec720f50b754785737f3e0a1c2`
- root：`/research/d7/spc/yzyang4/foreagent-ust-outcome-sensitivity/formal-93154e5-v3`
- focused/full：`12 passed` / `1772 passed, 48 warnings`
- failure：`ValueError: raw reproduction`
- `FAILED_RC=1`，`COMPLETE` 不存在
- result/verification 文件数：0
- 完整 UST result 生成/读取：否/否

证据 SHA-256：

```text
fa5ac165718fcca81a82d8a7c576325dbe72d5de8c00c5677cc9f3704d04d303  FAILED_RAW_REPRODUCTION_NUMERIC_TOLERANCE.txt
3097c3ce19ea72132e66805211193bd17b6210db7d3483f4be4e923008b821c6  known_raw_reproduction_numeric_diagnostic.json
ff1f8fbeee19be692886362c7c74788db0969e9a92990ef9e27b18ba694f3896  producer_a.stderr
034a8427f1a7f102be682a51bab10ce56d7318ddff2d89a51c4b8295f4c42143  full_tests.txt
```

## 精确重算

诊断仍绑定 manifest/master SHA，只重算协议已经公开的 raw reproduction；没有构造新 UST graph/outcome，也没有输出
task/path identity。

| 指标 | 精确分数 | 普通求和值 − 冻结值 | ε 倍数 |
|---|---|---:|---:|
| DeepSeek pair micro | `1616/2627` | `-3.9968028886505635e-15` | 18 |
| DeepSeek task macro | `37777818629854788093261688571/62267959142734032839845293600` | `-2.2204460492503131e-16` | 1 |
| GPT pair micro | `32477/55143` | `-2.7755575615628914e-15` | 12.5 |
| GPT task macro | `9323612458796464987461732053/16073341117180164123845338800` | `0` | 0 |

四项都与整数成功数/总预测数的精确有理数相符；问题只在不同求和路径的末位舍入。

## v4 固定修正

```text
RAW_REPRODUCTION_TOLERANCE = 64 * np.finfo(np.float64).eps
                           = 1.4210854715202004e-14
```

选择 64ε 是输入位于 `[0,1]` 时可解释的 binary64 数值门，仍远小于会掩盖数据或算法漂移的 `1e-12` 量级。
新增控制固定：观察到的 18ε 差必须通过，128ε synthetic drift 必须失败。

没有改变：四个 KNOWN raw constants、`source_grid_reproduction` 输出、18,381 common support、endpoint identity、
effective-resistance/UST 权重、四个 headline、paired delta、20,000 task bootstrap、LOTO、独立 verifier tolerance、
prior `INSUFFICIENT-SUPPORT` 或科学分类。

focused=`13 passed in 0.30s`；numeric addendum SHA-256=
`5a47d185fb210027ade9c9eee7c23ac0fbc6857e05f63e7e99a30ac77383fb69`。

## 下一步

公开 v4 exact source，使用 fresh detached worktree/root 第四次运行完整 formal；v1/v2/v3 根永久保留且不得复用。
