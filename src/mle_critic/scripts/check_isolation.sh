#!/bin/bash

# K8s Pod 环境隔离能力诊断脚本
# 用于探测是否具备运行 AI Agent 隔离沙盒的条件

echo -e "\n============================================="
echo "   AI Agent Sandbox 环境隔离能力诊断报告"
echo -e "=============================================\n"

# 1. 基础权限检查
echo "[1/5] 基础用户权限检查..."
if [ "$(id -u)" -eq 0 ]; then
    echo "  [+] 结果: 当前是 ROOT 用户 (UID 0)"
else
    echo "  [-] 结果: 当前是非 root 用户，许多隔离方案受限"
fi

# 2. 命名空间 (Namespaces) 测试
# Agent 最佳隔离方式，类似于轻量级容器
echo -e "\n[2/5] Linux 命名空间 (Namespaces) 隔离检查..."
# 尝试创建一个新的 User 和 Mount 命名空间
unshare --user --mount -r echo "success" > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "  [+] 结果: 支持 User 和 Mount 命名空间 (Unprivileged Namespaces 可用)"
    echo "  [💡] 建议: 可以使用 bubblewrap (bwrap) 或 proot 创建极轻量、高度安全的沙盒，完全不影响宿主机。"
else
    echo "  [-] 结果: 命名空间创建失败 (可能被 K8s SecComp 或 AppArmor 拦截)"
    echo "  [!] 降级: 无法使用原生容器级隔离，需依赖传统用户权限控制。"
fi

# 3. Cgroups 资源限制检查
# 用于限制 Agent 的 CPU 和内存使用，防止跑死共享机器
echo -e "\n[3/5] Cgroups 资源隔离检查..."
if [ -w "/sys/fs/cgroup" ]; then
    echo "  [+] 结果: /sys/fs/cgroup 目录可写"
    CGROUP_VERSION=$(stat -fc %T /sys/fs/cgroup/)
    if [ "$CGROUP_VERSION" == "cgroup2fs" ]; then
        echo "      -> Cgroup v2 可用"
    else
        echo "      -> Cgroup v1 可用"
    fi
    echo "  [💡] 建议: 可以创建独立的 cgroup slice 来限制 Agent 训练和编译的资源消耗。"
else
    echo "  [-] 结果: /sys/fs/cgroup 目录只读 (Read-Only)"
    echo "  [!] 降级: K8s 锁死了 Pod 内的 cgroup 挂载，无法为 Agent 单独做硬件资源硬限制 (只能依赖用户态的 ulimit)。"
fi

# 4. Chroot 文件系统隔离检查
echo -e "\n[4/5] Chroot 文件系统隔离检查..."
mkdir -p /tmp/chroot_test_dir
if chroot /tmp/chroot_test_dir /bin/sh -c "echo 1" > /dev/null 2>&1 || [ $? -eq 127 ]; then
    # 127 意味着 chroot 成功但找不到 /bin/sh，说明 chroot 系统调用是通的
    echo "  [+] 结果: chroot 系统调用可用"
    echo "  [💡] 建议: 可以配合新建普通用户 + chroot 制作一个假的根目录，防止 Agent 乱改系统代码或影响其他人的工作空间。"
else
    echo "  [-] 结果: chroot 被禁用 (Pod 权限极低)"
fi
rm -rf /tmp/chroot_test_dir

# 5. 可用沙盒工具探测
echo -e "\n[5/5] 用户态沙盒工具探测..."
TOOLS=("bwrap" "proot" "fakeroot" "docker" "apptainer" "singularity")
for tool in "${TOOLS[@]}"; do
    if command -v $tool >/dev/null 2>&1; then
        echo "  [+] 发现已安装工具: $tool"
    fi
done

echo -e "\n============================================="
echo "诊断结束。"
echo "============================================="