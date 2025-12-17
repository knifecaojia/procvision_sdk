# 工业视觉平台 Runner 规范 (v1.0.0)

## 1. 概述

### 1.1. 目的
本文档定义了工业视觉平台**生产级 Runner (Production Runner)** 的设计规范。生产级 Runner 是主平台（Host Application）的一部分，负责在生产环境中管理算法进程的生命周期、调度执行任务、监控资源使用以及处理异常情况。

### 1.2. 定位
- **Dev Runner (SDK内置)**: 侧重开发体验、协议验证和单次调试；已在 `procvision-cli` 集成。
- **Production Runner (平台侧)**: 侧重高并发、高稳定性、容错恢复和资源隔离；与包管理/上报集成。

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

## 7. 遥测与工件上报

### 7.1. 边端采集器（轻量）

- 采集范围: 算法与 Runner 的结构化日志（JSON），NG 图片与派生图（缩略、标注），轻量报告（result_status, ng_reason, defect_rects_count）。
- 缓存与重试: 本地持久队列（SQLite/LevelDB），断网离线缓存；指数退避重试；队列大小与磁盘占用阈值可配置。
- 优先级: 健康/告警 > 业务日志 > 诊断日志；图片与日志独立限流，避免相互阻塞。

### 7.2. 传输策略

- 日志: REST 批量上报（HTTP/2 + TLS）。接口 `POST /v1/logs/batch`，Body 为 JSON 数组，批量窗口按条数/时间/字节三阈值控制（如 100 条/1s/256KB）。
- 图片: 首选对象存储直传（MinIO/S3）+ 预签名 URL；兜底 REST 传图。流程：
  - 预签名: `POST /v1/artifacts/presign` → 返回 `upload_url,key,headers`
  - 上传: 客户端 `PUT upload_url`
  - 索引提交: `POST /v1/artifacts/commit`（`artifact_id, session_id, pid, result_status, ng_reason, s3_key, size_bytes`）
- 幂等: 每条日志与工件包含 `ingest_id=<workstation_id>/<session_id>/<step>/<timestamp_ms>`；服务端按此幂等。

### 7.3. 数据契约

- 日志字段（JSON 行）: `timestamp_ms, workstation_id, session_id, step_index, pid, trace_id, status, latency_ms, model_version, result_status, ng_reason, defect_rects_count`
- 工件元数据: `artifact_id, session_id, pid, type(ng_image|roi_crop|report), content_type, size_bytes, result_status, ng_reason, camera_id, width, height`

### 7.4. 安全与合规

- 传输: 全链路 TLS；Token 或 MTLS；超时与重试可控。
- 隐私: 图片剥离敏感元数据；按需裁剪与缩略；访问审计与签名 URL 下载。

## 8. 桌面集成（PySide6）

- 线程模型: Runner 与上报在后台线程执行；UI 显示网络状态、队列深度、失败计数；支持暂停上传、立即重试、导出日志。
- 配置: 对象存储域名、证书路径、租户/工位 ID、批量窗口、带宽上限；支持热更新与持久化。
- 轻量 Collector 接口: `send_logs(batch)` 与 `send_artifact(path, meta)`；内部统一队列与重试逻辑。

## 9. 上行 API 合同（简化）

- `POST /v1/logs/batch`
  - 请求: `[{log...}]`
  - 响应: `{status:"OK"}`
- `POST /v1/artifacts/presign`
  - 请求: `{content_type, size_bytes, session_id, pid}`
  - 响应: `{upload_url, key, headers}`
- `POST /v1/artifacts/commit`
  - 请求: `{artifact_id, session_id, pid, result_status, ng_reason, s3_key, size_bytes}`
  - 响应: `{status:"OK"}`

## 10. 可靠性与回压

## 11. 算法包管理

### 11.1. 包格式与来源
- 输入为离线 zip 包（由 `procvision-cli package` 生成）：包含源码目录、`manifest.json`、`requirements.txt`、`wheels/` 与可选 `assets/`。
- 禁止在线拉取依赖；仅使用包内 `wheels/`。

### 11.2. 安装流程
1. 校验：打开 zip 并检查必须文件是否存在；运行 SDK 校验（入口导入、`supported_pids` 一致性、`get_info` 返回结构）。
2. 展开：解压到 `algorithms/deployed/<name>/<version>/`，创建隔离 `venv/` 并仅使用 `wheels/` 安装依赖。
3. 注册：写入 `runtime_store/registry.json`：`{ name, version, supported_pids, state: installed, created_at }`。

### 11.3. 激活/切换/回滚
- 激活：将包绑定到指定 `pid` 范围，写入 `active/<pid>.json`。
- 切换：预热新版本进程，完成握手后在下一周期切换映射；旧进程优雅退出。
- 回滚：选择历史版本重新激活；保留最近 N 个版本。

### 11.4. 卸载与清理
- 卸载前解除激活；删除 `deployed` 目录与注册记录；保留日志与审计信息。

### 11.5. 存储布局
```
runtime_store/
  algorithms/
    zips/
    deployed/<name>/<version>/
      src/
      manifest.json
      requirements.txt
      wheels/
      assets/
      venv/
  active/
    <pid>.json
  registry.json
  logs/
```

### 11.6. API/CLI（平台侧）
- 安装：`POST /algorithms/install`
- 激活：`POST /algorithms/activate`
- 切换：`POST /algorithms/switch`
- 卸载：`DELETE /algorithms/{name}/{version}`
- 查询：`GET /algorithms`, `GET /algorithms/active`
- 校验：`POST /algorithms/validate`

### 11.7. 错误码（包管理 2xxx）
- 2001 invalid_zip, 2002 manifest_missing, 2003 incompatible_python, 2004 wheels_missing,
- 2005 install_failed, 2006 activation_conflict, 2007 unsafe_uninstall

- 传输保证: 日志至少一次（中心幂等），工件分块校验与原子索引提交。
- 回压策略: 队列超阈值降级（摘要日志、缩略图）；恢复后补传。
- 监控: `trace_id` 贯穿算法、Runner、Collector 与服务端；暴露延迟、失败率、队列深度指标。
