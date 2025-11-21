# 算法包测试策略与方案

本文档详细说明如何系统性测试算法SDK及算法包的功能、性能和稳定性。

---

## 1. 测试类型概览

| 测试类型 | 目标 | 自动化 | 频率 | 关键程度 |
|---------|------|--------|------|----------|
| **单元测试** | 验证SDK核心组件 | ✅ | 每次提交 | 🔴 必须 |
| **CLI验证测试** | 检查算法包结构 | ✅ | 每次提交 | 🔴 必须 |
| **集成测试** | 平台-算法端到端 | ✅ | 版本发布时 | 🔴 必须 |
| **性能测试** | 检测耗时、内存 | ⚠️ | 版本发布时 | 🟡 重要 |
| **压力测试** | 并发、稳定性 | ⚠️ | 定期 | 🟡 重要 |
| **兼容性测试** | 多平台支持 | ❌ | 版本发布时 | 🟡 重要 |

---

## 2. 单元测试（SDK核心）

### 2.1 测试文件结构

```
tests/
├── __init__.py
├── test_base.py              # 测试BaseAlgorithm
├── test_session.py           # 测试Session管理
├── test_cli_validate.py      # 测试CLI验证
├── test_shared_memory.py     # 测试共享内存读取（待实现）
├── test_runner.py           # 测试Runner协议（待实现）
└── test_integration.py       # 端到端集成测试
```

### 2.2 BaseAlgorithm测试（test_base.py）

```python
import pytest
from procvision_algorithm_sdk import BaseAlgorithm, Session


class MockAlgorithm(BaseAlgorithm):
    """Mock算法用于测试"""

    def __init__(self, pid):
        super().__init__(pid)
        self.setup_called = False
        self.teardown_called = False

    def setup(self):
        self.setup_called = True

    def teardown(self):
        self.teardown_called = True

    def on_step_start(self, step_index, session, context):
        session.set(f"start_{step_index}", True)

    def on_step_finish(self, step_index, session, result):
        result["debug"] = {"finished": True}

    def reset(self, session):
        session.delete("temp_data")

    def get_info(self):
        return {
            "name": "mock_algorithm",
            "version": "0.1.0",
            "steps": [
                {
                    "index": 0,
                    "name": "步骤1",
                    "params": [
                        {"key": "threshold", "type": "float", "default": 0.75}
                    ]
                }
            ]
        }

    def pre_execute(self, step_index, session, shared_mem_id, image_meta, user_params):
        return {"status": "OK"}

    def execute(self, step_index, session, shared_mem_id, image_meta, user_params):
        threshold = user_params.get("threshold", 0.75)
        return {
            "status": "OK" if threshold > 0.5 else "NG",
            "diagnostics": {"confidence": threshold}
        }


class TestBaseAlgorithm:
    """测试BaseAlgorithm生命周期"""

    def test_initialization(self):
        """测试初始化"""
        alg = MockAlgorithm("TEST-01")
        assert alg.pid == "TEST-01"
        assert hasattr(alg, "logger")
        assert hasattr(alg, "diagnostics")

    def test_lifecycle_hooks(self):
        """测试生命周期钩子"""
        alg = MockAlgorithm("TEST-01")
        session = Session("test-session")

        # setup
        alg.setup()
        assert alg.setup_called

        # on_step_start
        alg.on_step_start(0, session, {})
        assert session.get("start_0") is True

        # execute
        result = alg.execute(0, session, "mem", {"width": 640, "height": 480}, {"threshold": 0.8})
        assert result["status"] == "OK"

        # on_step_finish
        assert "debug" in result
        assert result["debug"]["finished"] is True

        # reset
        session.set("temp_data", "value")
        alg.reset(session)
        assert session.get("temp_data") is None

        # teardown
        alg.teardown()
        assert alg.teardown_called

    def test_abstract_methods(self):
        """测试抽象方法必须实现"""
        class IncompleteAlgorithm(BaseAlgorithm):
            def get_info(self):
                return {}
            # 缺少pre_execute和execute

        alg = IncompleteAlgorithm("TEST")

        # 应该能实例化（Python不会阻止）
        # 但调用未实现的方法会报错
        with pytest.raises(NotImplementedError):
            alg.pre_execute(0, Session("test"), "mem", {}, {})
```

### 2.3 Session状态管理测试（test_session.py）

```python
import pytest
from procvision_algorithm_sdk import Session


class TestSession:
    """测试Session隔离和状态管理"""

    def test_basic_operations(self):
        """测试基本的get/set/delete"""
        session = Session("session-001")

        # set and get
        session.set("key1", "value1")
        assert session.get("key1") == "value1"

        # delete
        session.delete("key1")
        assert session.get("key1") is None

    def test_session_isolation(self):
        """测试不同Session之间隔离"""
        session1 = Session("session-001")
        session2 = Session("session-002")

        # Session1写入
        session1.set("shared_data", "value_from_session1")

        # Session2应该看不到
        assert session2.get("shared_data") is None

        # Session2写入同名key
        session2.set("shared_data", "value_from_session2")

        # 两个Session值不同
        assert session1.get("shared_data") == "value_from_session1"
        assert session2.get("shared_data") == "value_from_session2"

    def test_reset(self):
        """测试reset清除所有状态"""
        session = Session("session-001")

        # 写入多个key
        session.set("temp1", "value1")
        session.set("temp2", "value2")
        session.set("temp3", "value3")

        # reset
        session.reset()

        # 所有key都被清除
        assert session.get("temp1") is None
        assert session.get("temp2") is None
        assert session.get("temp3") is None

    def test_context_field(self):
        """测试context字段"""
        context = {
            "product_code": "A01",
            "operator": "user001",
            "trace_id": "trace-1234"
        }
        session = Session("session-001", context=context)

        assert session.context["product_code"] == "A01"
        assert session.context["trace_id"] == "trace-1234"

        # context是只读的（不应被修改）
        # state_store与context分离
        session.set("temp_data", "value")
        assert session.get("temp_data") == "value"
        assert "temp_data" not in session.context
```

### 2.4 共享内存测试（test_shared_memory.py）

**注意**：当前shared_memory.py是stub实现，需要先实现真实版本。

```python
import pytest
import numpy as np
from procvision_algorithm_sdk import read_image_from_shared_memory
import tempfile
import os


class TestSharedMemory:
    """测试共享内存图像读取（待实现）"""

    @pytest.mark.skip(reason="shared_memory.py是stub实现，需实现真实版本")
    def test_read_image(self):
        """测试读取真实图像"""
        # 准备测试图像
        test_image = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)

        # 写入共享内存（这里需要SDK提供write函数）
        from procvision_algorithm_sdk import write_image_to_shared_memory
        shared_mem_id = "test_mem_001"
        write_image_to_shared_memory(shared_mem_id, test_image)

        # 读取
        image_meta = {
            "width": 640,
            "height": 480,
            "channels": 3,
            "dtype": "uint8"
        }
        result = read_image_from_shared_memory(shared_mem_id, image_meta)

        # 验证
        assert result.shape == test_image.shape
        assert result.dtype == test_image.dtype
        assert np.array_equal(result, test_image)

    @pytest.mark.skip(reason="shared_memory.py是stub实现")
    def test_different_formats(self):
        """测试不同图像格式"""
        formats = [
            (640, 480, 3, np.uint8),   # RGB
            (640, 480, 1, np.uint8),   # 灰度
            (640, 480, 3, np.float32), # 浮点
            (800, 600, 3, np.uint8),   # 不同分辨率
        ]

        for width, height, channels, dtype in formats:
            img = np.random.randint(0, 255, (height, width, channels), dtype=dtype)
            # ... 类似test_read_image

    @pytest.mark.skip(reason="shared_memory.py是stub实现")
    def test_concurrent_access(self):
        """测试多个算法实例同时读取"""
        # 模拟多工位同时检测
        import threading

        def read_thread(mem_id, result_dict):
            image_meta = {"width": 640, "height": 480, "channels": 3}
            img = read_image_from_shared_memory(mem_id, image_meta)
            result_dict[mem_id] = img.shape

        threads = []
        results = {}

        for i in range(5):
            mem_id = f"test_mem_{i}"
            t = threading.Thread(target=read_thread, args=(mem_id, results))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # 所有线程都成功读取
        assert len(results) == 5
```

---

## 3. CLI验证测试

### 3.1 验证算法包结构（test_cli_validate.py）

```python
import json
import os
import tempfile
import zipfile
from procvision_algorithm_sdk.cli import validate


class TestCLIValidate:
    """测试CLI验证功能"""

    def test_validate_complete_algorithm(self):
        """测试完整的算法包"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 1. 创建算法结构
            os.makedirs(f"{tmpdir}/wheels")

            # manifest.json
            manifest = {
                "name": "test_algorithm",
                "version": "0.1.0",
                "entry_point": "main:TestAlgorithm",
                "supported_pids": ["TEST-01"]
            }
            with open(f"{tmpdir}/manifest.json", "w") as f:
                json.dump(manifest, f)

            # main.py
            main_py = """
from procvision_algorithm_sdk import BaseAlgorithm, Session

class TestAlgorithm(BaseAlgorithm):
    def get_info(self):
        return {
            "name": "test_algorithm",
            "version": "0.1.0",
            "steps": [{"index": 0, "name": "检测", "params": []}]
        }

    def pre_execute(self, step_index, session, shared_mem_id, image_meta, user_params):
        return {"status": "OK"}

    def execute(self, step_index, session, shared_mem_id, image_meta, user_params):
        return {"status": "OK", "diagnostics": {"confidence": 0.9}}
"""
            with open(f"{tmpdir}/main.py", "w") as f:
                f.write(main_py)

            # requirements.txt
            with open(f"{tmpdir}/requirements.txt", "w") as f:
                f.write("")

            # 2. 执行验证
            report = validate(project=tmpdir, manifest=None, zip_path=None)

            # 3. 验证结果
            assert report["summary"]["status"] == "PASS"
            assert report["summary"]["failed"] == 0

            # 检查关键验证项
            checks = {c["name"]: c for c in report["checks"]}
            assert checks["manifest_exists"]["result"] == "PASS"
            assert checks["entry_import"]["result"] == "PASS"
            assert checks["io_contract_status"]["result"] == "PASS"

    def test_validate_missing_manifest(self):
        """测试缺少manifest.json"""
        with tempfile.TemporaryDirectory() as tmpdir:
            report = validate(project=tmpdir, manifest=None, zip_path=None)

            assert report["summary"]["status"] == "FAIL"
            assert report["checks"][0]["name"] == "manifest_exists"
            assert report["checks"][0]["result"] == "FAIL"

    def test_validate_missing_fields_in_manifest(self):
        """测试manifest缺少必需字段"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建缺少supported_pids的manifest
            manifest = {
                "name": "test",
                "version": "0.1.0"  # 缺少entry_point和supported_pids
            }
            with open(f"{tmpdir}/manifest.json", "w") as f:
                json.dump(manifest, f)

            report = validate(project=tmpdir, manifest=None, zip_path=None)

            checks = {c["name"]: c for c in report["checks"]}
            assert checks["manifest_fields"]["result"] == "FAIL"

    def test_validate_zip_package(self):
        """测试验证ZIP包"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 创建算法文件
            # ... 同上 ...

            # 打包成ZIP
            zip_path = f"{tmpdir}/algorithm.zip"
            with zipfile.ZipFile(zip_path, "w") as z:
                z.write(f"{tmpdir}/manifest.json", "manifest.json")
                z.write(f"{tmpdir}/main.py", "main.py")
                z.write(f"{tmpdir}/requirements.txt", "requirements.txt")
                # 创建空的wheels目录
                z.writestr("wheels/.gitkeep", "")

            # 验证ZIP
            report = validate(project=None, manifest=None, zip_path=zip_path)

            checks = {c["name"]: c for c in report["checks"]}
            assert checks["zip_manifest"]["result"] == "PASS"
            assert checks["zip_requirements"]["result"] == "PASS"
            assert checks["zip_wheels"]["result"] == "PASS"
```

### 3.2 端到端集成测试

```python
import subprocess
import time
import json
from procvision_algorithm_sdk import Session


class TestEndToEnd:
    """端到端集成测试（模拟平台-算法交互）"""

    @pytest.fixture
    def algorithm_zip(self):
        """创建测试用的算法ZIP包"""
        # 这里应该生成一个测试算法包
        # 或者使用sdk_sample（待创建）
        pass

    def test_algorithm_lifecycle(self):
        """测试算法完整生命周期"""
        # 1. 启动算法进程（模拟Runner）
        proc = subprocess.Popen(
            ["python", "-m", "main", "serve"],  # 假设main.py支持serve模式
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        try:
            # 2. 握手（待Runner实现）
            # stdin.write('{"type":"hello","sdk_version":"0.1.0"}\n')
            # response = stdout.readline()
            # assert "hello" in response

            # 3. 执行检测（模拟）
            request = {
                "type": "call",
                "request_id": "req-001",
                "method": "execute",
                "payload": {
                    "step_index": 0,
                    "session": {"id": "session-001", "state_store": {}},
                    "shared_mem_id": "shm001",
                    "image_meta": {"width": 640, "height": 480, "channels": 3},
                    "user_params": {"threshold": 0.75}
                }
            }

            # 4. 验证响应
            # ... 待Runner实现 ...

            # 5. 关闭
            # stdin.write('{"type":"shutdown"}\n')
            pass

        finally:
            proc.terminate()
            proc.wait(timeout=5)
```

---

## 4. 性能测试

### 4.1 检测耗时测试

```python
import time
import statistics
from procvision_algorithm_sdk import Session


class TestPerformance:
    """性能基准测试"""

    def test_detection_latency(self):
        """测试单次检测耗时"""
        # 加载算法
        from main import MyDetectionAlgorithm
        alg = MyDetectionAlgorithm("TEST-01")
        alg.setup()

        session = Session("test-session")
        image_meta = {"width": 640, "height": 480, "channels": 3}

        # 预热（排除首次加载延迟）
        for _ in range(3):
            alg.execute(0, session, "mem", image_meta, {"threshold": 0.75})

        # 正式测试
        latencies = []
        for i in range(100):  # 测试100次
            start = time.time()
            result = alg.execute(0, session, "mem", image_meta, {"threshold": 0.75})
            end = time.time()

            assert result["status"] == "OK"
            latencies.append((end - start) * 1000)  # ms

        # 统计分析
        avg_latency = statistics.mean(latencies)
        p95_latency = statistics.quantiles(latencies, n=20)[18]  # 95分位
        p99_latency = statistics.quantiles(latencies, n=100)[98]  # 99分位

        print(f"\n性能测试结果:")
        print(f"  平均耗时: {avg_latency:.2f}ms")
        print(f"  95分位: {p95_latency:.2f}ms")
        print(f"  99分位: {p99_latency:.2f}ms")
        print(f"  最小: {min(latencies):.2f}ms")
        print(f"  最大: {max(latencies):.2f}ms")

        # 断言性能达标（例如：平均<100ms，99分位<200ms）
        assert avg_latency < 100, f"平均耗时过高: {avg_latency:.2f}ms"
        assert p99_latency < 200, f"99分位耗时过高: {p99_latency:.2f}ms"

        alg.teardown()

    def test_memory_usage(self):
        """测试内存占用"""
        import psutil
        import os

        from main import MyDetectionAlgorithm

        process = psutil.Process(os.getpid())

        # 测试前内存
        mem_before = process.memory_info().rss / 1024 / 1024  # MB

        # 加载算法
        alg = MyDetectionAlgorithm("TEST-01")
        alg.setup()

        mem_after_setup = process.memory_info().rss / 1024 / 1024
        print(f"\n内存使用:")
        print(f"  Setup前: {mem_before:.2f}MB")
        print(f"  Setup后: {mem_after_setup:.2f}MB")
        print(f"  模型占用: {mem_after_setup - mem_before:.2f}MB")

        # 执行多次检测
        session = Session("test-session")
        image_meta = {"width": 640, "height": 480, "channels": 3}

        for _ in range(10):
            alg.execute(0, session, "mem", image_meta, {})

        mem_after_execution = process.memory_info().rss / 1024 / 1024
        print(f"  执行后: {mem_after_execution:.2f}MB")
        print(f"  增长: {mem_after_execution - mem_after_setup:.2f}MB")

        # 检查是否有内存泄漏（增长<50MB）
        assert mem_after_execution - mem_after_setup < 50

        alg.teardown()

    def test_throughput(self):
        """测试吞吐量（每秒检测次数）"""
        from main import MyDetectionAlgorithm

        alg = MyDetectionAlgorithm("TEST-01")
        alg.setup()

        session = Session("test-session")
        image_meta = {"width": 640, "height": 480}

        # 测试10秒内的检测次数
        duration = 10  # 秒
        start_time = time.time()
        count = 0

        while time.time() - start_time < duration:
            alg.execute(0, session, "mem", image_meta, {})
            count += 1

        throughput = count / duration
        print(f"\n吞吐量: {throughput:.2f} FPS")

        assert throughput > 5, f"吞吐量过低: {throughput:.2f} FPS"

        alg.teardown()
```

### 4.2 多场景性能对比

```python
@pytest.mark.parametrize("image_size", [
    (320, 240),   # 小
    (640, 480),   # 中
    (1280, 720),  # 大
    (1920, 1080)  # 超大
])
def test_performance_different_resolutions(self, image_size):
    """测试不同分辨率下的性能"""
    from main import MyDetectionAlgorithm

    alg = MyDetectionAlgorithm("TEST-01")
    alg.setup()

    session = Session("test-session")
    width, height = image_size
    image_meta = {"width": width, "height": height, "channels": 3}

    # 预热
    alg.execute(0, session, "mem", image_meta, {})

    # 测试
    start = time.time()
    for _ in range(10):
        alg.execute(0, session, "mem", image_meta, {})
    end = time.time()

    avg_latency = (end - start) / 10 * 1000
    print(f"{width}x{height}: {avg_latency:.2f}ms")

    # 确保大分辨率也能满足SLO
    if width <= 640:
        assert avg_latency < 50
    elif width <= 1280:
        assert avg_latency < 150
    else:
        assert avg_latency < 300

    alg.teardown()
```

---

## 5. 错误场景测试

### 5.1 可恢复错误测试

```python
import pytest
from procvision_algorithm_sdk import RecoverableError
from main import MyDetectionAlgorithm


class TestRecoverableErrors:
    """测试可恢复错误场景"""

    def test_insufficient_lighting(self):
        """测试光照不足"""
        alg = MyDetectionAlgorithm("TEST-01")
        alg.setup()

        session = Session("test-session")
        image_meta = {"width": 640, "height": 480}

        # 设置极低的亮度阈值（一定会触发错误）
        user_params = {"brightness_threshold": 999}

        result = alg.pre_execute(0, session, "mem", image_meta, user_params)

        # 验证返回错误信息
        assert result["status"] == "ERROR"
        assert result["error_type"] == "recoverable"
        assert result["suggest_action"] == "retry"
        assert "光照不足" in result["message"]

        alg.teardown()

    def test_camera_disconnected(self):
        """测试相机断开（模拟）"""
        alg = MyDetectionAlgorithm("TEST-01")
        alg.setup()

        session = Session("test-session")

        # 模拟共享内存ID无效
        result = alg.execute(0, session, "invalid_mem_id", {"width": 640}, {})

        # 应该返回recoverable error
        assert result["status"] == "ERROR"
        assert result["error_type"] == "recoverable"
        assert result["suggest_action"] == "retry"

        alg.teardown()

    def test_network_timeout(self):
        """测试网络超时"""
        # 如果算法依赖外部服务（不推荐）
        pass
```

### 5.2 不可恢复错误测试

```python
import pytest
from procvision_algorithm_sdk import FatalError
from main import MyDetectionAlgorithm
import os


class TestFatalErrors:
    """测试不可恢复错误场景"""

    def test_model_file_missing(self):
        """测试模型文件不存在"""
        # 临时重命名模型文件
        model_path = "assets/defect_detector.pt"
        if os.path.exists(model_path):
            os.rename(model_path, model_path + ".backup")

        try:
            alg = MyDetectionAlgorithm("TEST-01")

            # setup应该抛出FatalError
            with pytest.raises(FatalError):
                alg.setup()

        finally:
            # 恢复模型文件
            if os.path.exists(model_path + ".backup"):
                os.rename(model_path + ".backup", model_path)

    def test_invalid_model_format(self):
        """测试模型格式损坏"""
        alg = MyDetectionAlgorithm("TEST-01")

        # 创建一个损坏的模型文件
        with open("assets/corrupted_model.pt", "wb") as f:
            f.write(b"this is not a valid model")

        # 修改算法使用损坏的模型
        alg.model_path = "assets/corrupted_model.pt"

        with pytest.raises(FatalError):
            alg.setup()

    def test_unsupported_pid(self):
        """测试不支持的产品型号"""
        alg = MyDetectionAlgorithm("TEST-01")
        alg.setup()

        session = Session("test-session")

        # 在get_info中未声明支持的PID
        result = alg.execute(0, session, "mem", {"width": 640}, {})

        # 可以返回ERROR或抛出异常
        assert result["status"] in ["ERROR", "NG"]

        alg.teardown()
```

### 5.3 边界值测试

```python
@pytest.mark.parametrize("threshold,expected_status", [
    (0.0, "NG"),      # 阈值过低
    (0.49, "NG"),     # 略低于boundary
    (0.5, "OK"),      # 正好在boundary
    (0.51, "OK"),     # 略高于boundary
    (1.0, "OK"),      # 阈值过高
])
def test_threshold_boundary(self, threshold, expected_status):
    """测试阈值边界值"""
    from main import MyDetectionAlgorithm

    alg = MyDetectionAlgorithm("TEST-01")
    alg.setup()

    session = Session("test-session")
    image_meta = {"width": 640, "height": 480}

    result = alg.execute(0, session, "mem", image_meta, {"threshold": threshold})

    assert result["status"] == expected_status

    alg.teardown()
```

---

## 6. 并发与压力测试

### 6.1 Session并发测试

```python
import threading
from procvision_algorithm_sdk import Session
from main import MyDetectionAlgorithm


class TestConcurrency:
    """测试并发场景"""

    def test_concurrent_sessions(self):
        """测试多个Session同时运行"""
        results = {}
        lock = threading.Lock()

        def detect_thread(session_id):
            alg = MyDetectionAlgorithm("TEST-01")
            alg.setup()

            session = Session(session_id)
            image_meta = {"width": 640, "height": 480}

            # 写入Session特定数据
            session.set("thread_id", session_id)

            # 执行检测
            result = alg.execute(0, session, "mem", image_meta, {})

            with lock:
                results[session_id] = {
                    "status": result["status"],
                    "session_data": session.get("thread_id")
                }

            alg.teardown()

        # 启动10个并发线程
        threads = []
        for i in range(10):
            t = threading.Thread(target=detect_thread, args=(f"session-{i}",))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # 所有线程都完成
        assert len(results) == 10

        # 每个Session的数据是隔离的
        for session_id, result in results.items():
            assert result["session_data"] == session_id

    def test_algorithm_instance_reuse(self):
        """测试同一算法实例处理多个产品"""
        from main import MyDetectionAlgorithm

        alg = MyDetectionAlgorithm("TEST-01")
        alg.setup()

        # 模拟100个产品连续检测
        for i in range(100):
            session = Session(f"session-{i}")
            image_meta = {"width": 640, "height": 480}

            result = alg.execute(0, session, "mem", image_meta, {})
            assert result["status"] in ["OK", "NG"]

            # 每次检测后清理Session
            alg.reset(session)

        alg.teardown()
```

### 6.2 24小时稳定性测试

```python
import time


def test_long_running_stability():
    """24小时稳定性测试（简化版）"""
    from main import MyDetectionAlgorithm

    alg = MyDetectionAlgorithm("TEST-01")
    alg.setup()

    start_time = time.time()
    duration = 24 * 60 * 60  # 24小时

    count = 0
    errors = 0

    while time.time() - start_time < duration:
        try:
            session = Session(f"session-{count}")
            image_meta = {"width": 640, "height": 480}

            result = alg.execute(0, session, "mem", image_meta, {})

            if result["status"] == "ERROR":
                errors += 1

            count += 1

            # 每1000次报告状态
            if count % 1000 == 0:
                elapsed = time.time() - start_time
                print(f"已运行 {elapsed/3600:.1f} 小时，检测 {count} 次，错误 {errors} 次")

        except Exception as e:
            errors += 1
            print(f"异常: {e}")

    alg.teardown()

    print(f"\n24小时稳定性测试结果:")
    print(f"  总检测次数: {count}")
    print(f"  错误次数: {errors}")
    print(f"  成功率: {(count-errors)/count*100:.2f}%")

    # 成功率应>99.9%
    assert (count - errors) / count > 0.999
```

---

## 7. 测试覆盖率目标

```bash
# 使用pytest-cov测量覆盖率
pip install pytest-cov

# 运行测试并生成覆盖率报告
pytest --cov=procvision_algorithm_sdk --cov-report=html --cov-report=term-missing

# 覆盖率目标（建议）
# - 语句覆盖率: >85%
# - 分支覆盖率: >75%
```

**示例输出：**
```
Name                                          Stmts   Miss  Cover
-----------------------------------------------------------------
procvision_algorithm_sdk/__init__.py             10      0   100%
procvision_algorithm_sdk/base.py                 35      2    94%
procvision_algorithm_sdk/cli.py                  85     15    82%
procvision_algorithm_sdk/session.py              20      1    95%
procvision_algorithm_sdk/errors.py                4      0   100%
procvision_algorithm_sdk/logger.py               25      3    88%
procvision_algorithm_sdk/diagnostics.py          10      1    90%
procvision_algorithm_sdk/shared_memory.py         8      8     0%  # 待实现
-----------------------------------------------------------------
TOTAL                                           197     30    85%
```

---

## 8. 回归测试策略

### 8.1 版本发布前测试清单

```bash
# 每次发布新版本时执行

# 1. 单元测试（快速）
pytest tests/ -v

# 2. CLI验证（快速）
procvision-sdk validate --project sdk_sample

# 3. 性能测试（中等）
pytest tests/test_performance.py -v

# 4. 错误场景测试（快速）
pytest tests/test_errors.py -v

# 5. 集成测试（可选，需要Runner实现）
# pytest tests/test_integration.py -v

# 6. 覆盖率检查
pytest --cov=procvision_algorithm_sdk --cov-report=term-missing --cov-fail-under=85
```

### 8.2 GitHub Actions自动化

```yaml
# .github/workflows/test.yml
name: SDK Test Suite

on:
  push:
    branches: [ main, dev ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
    - uses: actions/checkout@v3

    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.8'

    - name: Install dependencies
      run: |
        pip install -e .
        pip install pytest pytest-cov

    - name: Run unit tests
      run: |
        pytest tests/test_base.py tests/test_session.py tests/test_errors.py -v

    - name: Run CLI tests
      run: |
        pytest tests/test_cli_validate.py -v

    - name: Run performance tests
      run: |
        pytest tests/test_performance.py -v --benchmark-autosave

    - name: Check coverage
      run: |
        pytest --cov=procvision_algorithm_sdk --cov-fail-under=85

    - name: Upload coverage to Codecov
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
```

---

## 9. 测试数据管理

### 9.1 测试图像数据集

```
tests/
└── data/
    ├── ok/
    │   ├── product_001.jpg    # 合格品图像
    │   ├── product_002.jpg
    │   └── ...
    ├── ng/
    │   ├── scratch_001.jpg    # 有划痕
    │   ├── stain_001.jpg      # 有污点
    │   └── ...
    └── edge_cases/
        ├── dark_image.jpg     # 光照不足
        ├── blurry_image.jpg   # 模糊
        └── overexposed.jpg    # 过曝
```

### 9.2 Mock数据生成

```python
import numpy as np
import cv2


def generate_test_image(width=640, height=480, defect_type=None):
    """生成测试图像"""
    # 创建基础图像
    img = np.ones((height, width, 3), dtype=np.uint8) * 200

    if defect_type == "scratch":
        # 添加划痕
        cv2.line(img, (100, 100), (300, 100), (50, 50, 50), 2)
    elif defect_type == "stain":
        # 添加污点
        cv2.circle(img, (200, 200), 30, (100, 100, 100), -1)
    elif defect_type == "dark":
        # 降低亮度
        img = (img * 0.3).astype(np.uint8)

    return img
```

---

## 10. 测试报告示例

每次测试运行后应生成详细报告：

```
============================= TEST REPORT =============================
测试时间: 2025-11-20 14:30:00
SDK版本: 0.1.0
算法包: my_algorithm-v1.0.0-offline.zip

【单元测试】
  总用例: 45
  通过: 43
  失败: 2
  覆盖率: 87.3%

【性能测试】
  平均耗时: 52.3ms
  95分位: 68.5ms
  吞吐量: 18.5 FPS
  内存占用: 145.6MB

【错误场景测试】
  可恢复错误: ✅ 通过
  不可恢复错误: ✅ 通过
  边界值: ✅ 通过

【集成测试】
  平台通信: ⚠️ 跳过（Runner未实现）
  Session隔离: ✅ 通过

【回归测试】
  与上一版本对比: 性能提升 12%

结论: 测试通过 ✅
=======================================================================
```

---

## 11. 关键测试指标（KPI）

| 指标 | 目标值 | 测量方法 | 频率 |
|------|--------|----------|------|
| **单元测试覆盖率** | >85% | pytest-cov | 每次提交 |
| **平均检测耗时** | <100ms | 性能测试 | 版本发布 |
| **95分位耗时** | <150ms | 性能测试 | 版本发布 |
| **吞吐量** | >10 FPS | 性能测试 | 版本发布 |
| **Session隔离性** | 100% | 并发测试 | 版本发布 |
| **24h稳定性** | >99.9% | 压力测试 | 版本发布 |
| **CLI验证通过率** | 100% | 自动化 | 每次提交 |

---

## 12. 问题追踪与修复

### 12.1 测试失败分类

```python
# pytest标记失败用例

@pytest.mark.xfail(reason="shared_memory未实现")
def test_shared_memory_read():
    # 已知问题，待修复
    pass

@pytest.mark.flaky(reruns=3)  # 偶尔失败的用例
def test_concurrent_access():
    pass

@pytest.mark.skipif(
    os.environ.get("CI") is None,
    reason="仅在CI环境运行"
)
def test_integration():
    pass
```

### 12.2 问题修复流程

1. **发现问题**：测试失败 → 创建Issue
2. **分析原因**：查看日志、复现问题
3. **编写测试**：添加回归测试用例
4. **修复代码**：实现修复
5. **验证**：测试通过 → 提交PR
6. **Code Review**：至少1人审查

---

## 13. 总结

### 13.1 当前测试状态

| 测试模块 | 状态 | 备注 |
|---------|------|------|
| BaseAlgorithm | ✅ 已实现 | tests/test_base.py |
| Session | ✅ 已实现 | tests/test_session.py |
| CLI验证 | ✅ 已实现 | tests/test_cli_validate.py |
| 共享内存 | ❌ 待实现 | 依赖真实实现 |
| Runner协议 | ❌ 待实现 | 依赖真实实现 |
| 性能测试 | ⚠️ 已实现 | tests/test_performance.py |
| 错误场景 | ⚠️ 部分实现 | tests/test_errors.py |

### 13.2 下一步行动

1. **立即行动（本周）**：
   - 编写完整的sdk_sample算法包
   - 修复CLI测试中的失败用例

2. **短期行动（本月）**：
   - 优化性能测试，添加更多场景
   - 实现并发测试和压力测试
   - 添加覆盖率检查到CI

3. **长期行动（下版本）**：
   - 等待shared_memory和Runner实现后，补充集成测试
   - 添加兼容性测试（多平台）
   - 建立性能基线数据库

---

**文档版本**: v1.0
**最后更新**: 2025-11-20
**测试框架**: pytest 7.0+
