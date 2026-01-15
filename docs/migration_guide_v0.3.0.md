# ProcVision SDK v0.3.0 迁移指南（execute 入参硬切）

## 你会遇到什么（必改）

### 1) execute 签名变化
旧版（v0.2.x）：
```python
def execute(self, step_index, session, user_params, shared_mem_id, image_meta): ...
```

新版（v0.3.0）：
```python
def execute(self, step_index, step_desc, cur_image, guide_image, guide_info): ...
```

### 2) 不再需要在算法中读共享内存
- 共享内存的写入由 Runner/CLI 负责。
- 图像的读取与解码由 adapter 负责。
- 算法 `execute` 会直接收到 `cur_image/guide_image` 的 ndarray。

## 你需要怎么改（算法团队）

### A. 替换入口类的 execute
```python
from typing import Any, Dict
from procvision_algorithm_sdk import BaseAlgorithm


class Algo(BaseAlgorithm):
    def execute(
        self,
        step_index: int,
        step_desc: str,
        cur_image: Any,
        guide_image: Any,
        guide_info: Any,
    ) -> Dict[str, Any]:
        if cur_image is None or guide_image is None:
            return {"status": "ERROR", "message": "图像数据为空", "error_code": "1002"}
        return {"status": "OK", "data": {"result_status": "OK", "defect_rects": []}}
```

### B. guide_info 结构
平台会按以下结构传入（示例）：
```json
[
  {"label":"1","posList":[{"x":94,"y":269,"width":319,"height":398}]},
  {"label":"2","posList":[{"x":797,"y":242,"width":250,"height":283}]}
]
```

## 本地验证方式变化（CLI）

### validate
```bash
procvision-cli validate ./your_algo
procvision-cli validate ./your_algo --full --tail-logs
```

### run
```bash
procvision-cli run ./your_algo --cur-image ./cur.jpg --guide-image ./guide.jpg --step-desc "Step 1" --guide-info @guide.json --json
```
