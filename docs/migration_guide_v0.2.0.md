# ProcVision SDK v0.2.0 升级指南（Execute-only，重大变更）

## 变更摘要
本版本为一次性硬切的重大变更：
- 删除算法接口中的 `get_info`、`pre_execute` 与所有生命周期/钩子（`setup/teardown/reset/on_step_*`）。
- 算法入口类仅需继承 `BaseAlgorithm` 并实现 `execute`。
- 适配器协议从多阶段 `phase` 调用改为单次 `execute` 调用。
- CLI `run/validate` 同步改为仅驱动 `execute`。

## 你需要做什么（算法团队）

### 1) 删除多余方法，仅保留 execute
旧代码（示意）：
```python
class Algo(BaseAlgorithm):
    def get_info(self): ...
    def pre_execute(...): ...
    def execute(...): ...
    def setup(self): ...
```

新代码：
```python
from typing import Any, Dict
from procvision_algorithm_sdk import BaseAlgorithm, Session, read_image_from_shared_memory

class Algo(BaseAlgorithm):
    def execute(
        self,
        step_index: int,
        session: Session,
        user_params: Dict[str, Any],
        shared_mem_id: str,
        image_meta: Dict[str, Any],
    ) -> Dict[str, Any]:
        img = read_image_from_shared_memory(shared_mem_id, image_meta)
        if img is None:
            return {"status": "ERROR", "message": "图像数据为空", "error_code": "1002"}
        return {"status": "OK", "data": {"result_status": "OK", "defect_rects": []}}
```

### 2) 保持 manifest.json 最小字段
```json
{
  "name": "your_algo",
  "version": "1.0.0",
  "entry_point": "your_pkg.main:YourAlgorithm"
}
```

### 3) 本地验证
```bash
procvision-cli validate ./your_algo
procvision-cli validate ./your_algo --full --tail-logs
procvision-cli run ./your_algo --image ./test.jpg --params "{\"threshold\":0.8}"
```

