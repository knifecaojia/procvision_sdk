# 构建与 GitHub Workflow 使用指南

## 本地构建

- 创建虚拟环境
  - `python -m venv .venv`
  - Windows 激活：`.\.venv\Scripts\activate`；Linux/Mac：`source .venv/bin/activate`
- 安装构建与测试工具
  - `pip install --upgrade pip`
  - `pip install build pytest`
- 运行单元测试
  - `pytest -q`
- 构建发行包（wheel + sdist）
  - `python -m build`
- 本地安装验证
  - `pip install dist/procvision_algorithm_sdk-<version>-py3-none-any.whl`
- 版本号位置
  - `pyproject.toml` 中 `project.version`
- 常见问题
  - 缺少依赖：检查虚拟环境，确保 `numpy` 已安装或由 `pyproject.toml` 依赖自动拉取
  - 测试失败：先运行 `procvision-cli validate --project ./algorithm-example` 自查接口实现

## Dev Runner（本地验证算法包）

- CLI 程序名：`procvision-cli`
- 校验项目：
  - `procvision-cli validate --project ./algorithm-example`
- 本地运行：
  - `procvision-cli run ./algorithm-example --pid p001 --image ./test.jpg --params '{"threshold":0.8}'`
- 说明：
  - 使用本地图片写入共享内存（`shared_mem_id = dev-shm:<session-id>`）
  - 统一传递 `image_meta = {width, height, timestamp_ms, camera_id}`

## 远程发布（GitHub Workflow）

- 工作流文件：`.github/workflows/sdk-build-and-publish.yml`
- 触发条件：
  - 推送 `dev` 分支：发布到 TestPyPI
  - 推送 `v*` 标签（如 `v1.0.0`）：发布到 PyPI
- 必需 Secrets：
  - `PYPI_TOKEN`：PyPI 的 API Token（User 为 `__token__`）
  - `TEST_PYPI_TOKEN`：TestPyPI 的 API Token（User 为 `__token__`）
- 发布步骤（自动执行）：
  - Checkout 代码
  - 设置 Python 3.10
  - 安装 `build`
  - `python -m build` 生成发行包到 `dist/`
  - 使用 `pypa/gh-action-pypi-publish` 上传到对应仓库
- 使用示例：
  - 开发验证：
    - `git checkout -b dev`
    - 修改并推送：`git push origin dev`
  - 正式发布：
    - 更新 `pyproject.toml` 版本号
    - 打标签并推送：
      - `git tag v1.0.0`
      - `git push origin v1.0.0`
    - 等待 Actions 完成后在 PyPI 查看包

## 发布前检查清单

- 版本号与变更日志已更新（`pyproject.toml`）
- 本地测试通过（`pytest -q`）
- 示例算法包可通过 `procvision-cli validate` 与 `run`
- README 与说明文档已同步到最新接口规范

## 故障排查

-- 构建失败：检查 `pyproject.toml` 字段完整性；确保 `project.dependencies` 安装成功
- 发布失败：检查 Secrets 是否配置；确认标签名以 `v` 开头；查看 Actions 日志
- 运行失败：确保图片路径存在；`--params` 为合法 JSON；`--pid` 在 `manifest.json.supported_pids` 中