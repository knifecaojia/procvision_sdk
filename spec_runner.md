# 工业视觉平台生产级 Runner 规范 (v0.1.0)

## 1. 概述

### 1.1. 目的
本文档定义了工业视觉平台**生产级 Runner (Production Runner)** 的设计规范。生产级 Runner 是主平台（Host Application）的一部分，负责在生产环境中管理算法进程的生命周期、调度执行任务、监控资源使用以及处理异常情况。

### 1.2. 定位
*   **Dev Runner (SDK内置)**: 侧重于开发体验、协议验证和单次调试。
*   **Production Runner (平台侧)**: 侧重于高并发、高稳定性、容错恢复和资源隔离。

## 2. 核心职责

Production Runner 必须实现以下核心功能：

1.  **进程管理**: 负责算法子进程的启动、停止、重启和僵尸进程清理。
2.  **通信调度**: 实现基于 Stdin/Stdout 的 JSON 协议，管理请求队列和并发控制。
3.  **共享内存管理**: 负责申请、复用和回收共享内存块，确保零拷贝传输。
4.  **健康监控**: 实时监控算法进程的 CPU、内存使用率和心跳响应。
5.  **异常处理**: 实现重试策略、熔断机制和错误上报。

## 3. 架构设计

### 3.1. 模块结构

```text
Production Runner
├── ProcessManager       # 进程生命周期管理 (启动/停止/重启)
├── ProtocolHandler      # 协议层 (JSON序列化/反序列化/粘包处理)
├── SharedMemoryPool     # 共享内存池 (RingBuffer设计)
├── TaskScheduler        # 任务调度器 (队列管理/超时控制)
└── HealthMonitor        # 健康监控 (心跳/资源/看门狗)
```

### 3.2. 关键流程

#### 3.2.1. 启动流程
1.  读取算法包 `manifest.json`，获取 `entry_point` 和依赖配置。
2.  配置 Python 解释器环境（虚拟环境路径）。
3.  启动子进程，重定向 Stdin/Stdout/Stderr。
4.  等待算法发送 `{"type": "hello"}` 握手消息。
5.  发送 `{"type": "hello"}` 确认握手。
6.  启动心跳定时器。

#### 3.2.2. 执行流程 (Execute)
1.  从相机获取图像数据。
2.  从 `SharedMemoryPool` 申请一块空闲内存。
3.  将图像数据写入共享内存。
4.  构造 `call` 消息，包含 `shared_mem_id` 和 `image_meta`。
5.  将消息写入子进程 Stdin。
6.  启动超时计时器 (Timeout Timer)。
7.  等待子进程返回 `result` 消息。
8.  解析结果，释放共享内存块回池。

#### 3.2.3. 异常恢复流程
1.  **超时**: 若算法在规定时间内未响应，发送 `SIGTERM` 尝试优雅关闭。若无效，发送 `SIGKILL` 强制杀死。
2.  **崩溃**: 监听 `SIGCHLD` 信号或管道断开事件。
3.  **重启策略**:
    *   立即重启（最多重试 3 次）。
    *   若短时间内连续崩溃（如 1 分钟内 5 次），进入"熔断状态"，报错并停止服务。

## 4. 接口定义 (Host -> Runner)

Runner 应向主平台提供以下高级接口（C# / C++ 伪代码）：

```csharp
interface IAlgorithmRunner {
    // 初始化
    void Initialize(string algorithmPackagePath);

    // 执行检测
    AlgorithmResult Execute(Image image, Dictionary<string, object> userParams);

    // 预执行 (可选)
    AlgorithmResult PreExecute(Image image, Dictionary<string, object> userParams);

    // 销毁
    void Dispose();
}
```

## 5. 性能要求

*   **启动时间**: 冷启动 < 2秒。
*   **通信延迟**: 协议序列化+传输 < 1ms。
*   **吞吐量**: 支持流水线模式，在多核 CPU 上不成为瓶颈。
*   **内存开销**: Runner 自身管理开销 < 50MB。

## 6. 安全性

*   **权限控制**: 算法子进程应以低权限用户运行，限制文件系统访问（仅允许读取模型和写入临时目录）。
*   **资源配额**: 使用 Cgroups (Linux) 或 Job Objects (Windows) 限制子进程的最大内存和 CPU 使用率，防止算法内存泄漏导致系统崩溃。
