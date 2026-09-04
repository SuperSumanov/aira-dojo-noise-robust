# 0903归档成熟后一次性摄取预检

冻结时间：2026-09-04 22:02 UTC；执行窗口：2026-09-05 00:10--00:40 UTC。

1. **唯一目标**：在九个0903压缩归档全部越过既有六小时age gate后，调用一次原摄取transaction。
2. **不提前**：已绑定最晚文件成熟时间为00:09:48.832417 UTC；successor最早00:10:00执行。
3. **不延续旧窗口冒名**：原六小时窗口23:53:04结束；新脚本使用独立输出根和独立时间租约。
4. **复用逻辑**：仅导入已验证foreground driver，运行前核其完整SHA；不复制或修改摄取算法。
5. **控制绑定**：底层driver仍核control commit、原monitor脚本、派生run-once脚本及clean worktree。
6. **状态绑定**：起点LATEST固定为`bc9833...9456`；外部未知变化、PID/log/hash漂移即fail-closed。
7. **并发**：需取得同一runner lock；不启动PID、tmux、nohup或后台monitor。
8. **安全**：底层仍做credential-shape、trace/security和summary白名单；不显示raw stdout/stderr。
9. **数据边界**：不读取标签、预测、accuracy、utility、candidate/task/private identity；不触碰保护vault。
10. **资源**：CPU单次；GPU/API/model fit/base update均为0；不自动重试。
11. **验收**：只接受return code 0、新snapshot原子LATEST、结构summary及独立既有verifier；失败根保留。
