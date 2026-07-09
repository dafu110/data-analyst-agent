# 生产级端到端验证清单

这份清单用于确认 Data Analyst Agent 不只是本地演示可用，而是具备接近 SaaS 的真实运行能力。

## 1. 本地 FastAPI 主链路

```powershell
python -m unittest tests.test_fastapi_smoke
```

验证内容：

- 通过 FastAPI 上传真实 CSV
- 创建分析任务
- 轮询任务直到完成
- 确认结果里包含图表规格和 Markdown 报告
- 验证 Markdown、HTML、CSV、PDF、PPTX 报告导出接口可用
- PDF 导出依赖 `reportlab` 和可用中文字体；PPTX 导出依赖 `python-pptx`

## 2. PostgreSQL 存储

准备 PostgreSQL 后设置：

```powershell
$env:DATA_ANALYST_AGENT_DATABASE_URL="postgresql://user:password@localhost:5432/data_analyst_agent"
python -m backend.fastapi_app --host 127.0.0.1 --port 8002
```

检查项：

- `/api/health` 的 `database` 返回 `postgresql`
- 上传任务后能在 PostgreSQL 中看到任务记录
- 重启服务后任务历史仍然存在
- 管理员和普通用户的数据隔离仍然有效

## 3. Redis / RQ Worker

准备 Redis 后设置：

```powershell
$env:DATA_ANALYST_AGENT_REDIS_URL="redis://localhost:6379/0"
python -m backend.fastapi_app --host 127.0.0.1 --port 8002
python -m backend.worker
```

检查项：

- `/api/health` 的 `queue` 返回 `redis-rq`
- 上传任务后状态先进入 queued
- worker 拉取任务并执行完成
- worker 停止时任务不会丢失
- worker 恢复后任务可以继续被处理

## 4. Docker Python 沙箱

构建沙箱镜像：

```powershell
docker build -f docker/sandbox.Dockerfile -t data-analyst-agent-sandbox:latest .
$env:DATA_ANALYST_AGENT_EXECUTOR_MODE="docker"
python -m unittest tests.test_agent
python -m backend.production_check --require-external
```

检查项：

- Python 分析代码在容器内执行
- 禁止 import、open、eval、exec 等危险操作
- 超时任务会失败并返回明确错误
- 容器无法访问宿主机敏感路径
- `production_check --require-external` 会验证 Docker server、沙箱镜像以及一次 `--network none --read-only --cap-drop ALL --security-opt no-new-privileges` 的容器 smoke

## 5. 发布前门禁

每次上线前运行：

```powershell
python -m compileall data_analyst_agent backend evals
node --check frontend\app.js
python -m unittest discover -s tests
python -m evals.run_evals
```

如果生产 Compose 服务已经启动，可以继续运行真实端到端验证：

```powershell
python scripts\production_e2e_check.py --base-url http://127.0.0.1:8000 --token $env:DATA_ANALYST_AGENT_API_TOKEN
```

验证内容包括健康检查、真实 CSV 上传、任务轮询、Markdown/HTML/CSV 导出和 Prometheus 指标出口。

通过标准：

- 单元测试全部通过
- eval 全部通过
- FastAPI smoke 测试在安装生产依赖时通过
- Markdown / HTML / CSV / PDF / PPTX 报告导出可用
- 图表数量和关键洞察数量没有明显回退
