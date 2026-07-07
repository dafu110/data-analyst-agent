# 运维指南

## 本地运行

```powershell
python -m backend.server
```

健康检查：

```text
GET /api/health
```

## Docker 运行

```powershell
docker compose up --build
```

打开：

```text
http://127.0.0.1:8000
```

## 生产架构模式

本项目现在支持两种运行模式：

```text
本地模式：stdlib HTTP server + SQLite + in-process thread
生产模式：FastAPI/OpenAPI + PostgreSQL + Redis/RQ worker + optional Docker sandbox
```

生产依赖：

```powershell
pip install -e ".[prod]"
```

FastAPI：

```powershell
python -m backend.fastapi_app --host 0.0.0.0 --port 8000
```

OpenAPI 文档：

```text
GET /docs
GET /openapi.json
```

RQ Worker：

```powershell
$env:DATA_ANALYST_AGENT_REDIS_URL="redis://localhost:6379/0"
python -m backend.worker
```

PostgreSQL：

```powershell
$env:DATA_ANALYST_AGENT_DATABASE_URL="postgresql://user:password@localhost:5432/data_analyst_agent"
```

Docker Compose 生产模板：

```powershell
docker compose -f docker-compose.prod.yml --env-file .env.prod up --build
```

生产模板中只有 `worker` 服务挂载 Docker socket，用于创建隔离的 Python 沙箱容器；`api` 服务不挂载 Docker socket，避免对外 HTTP 入口持有宿主机 Docker 控制权限。

`.env.prod` 至少需要：

```text
POSTGRES_PASSWORD=change-this
DATA_ANALYST_AGENT_API_TOKEN=change-this
DATA_ANALYST_AGENT_ADMIN_ACTORS=admin
```

## API 鉴权和租户隔离

生产环境建议启用 API Token：

```powershell
$env:DATA_ANALYST_AGENT_API_TOKEN="change-me"
```

客户端请求应发送：

```text
Authorization: Bearer change-me
X-Actor: alice
X-Org: acme
X-Workspace: finance
X-Role: analyst
X-Trace-ID: trace-20260630-001
```

访问规则：

- 普通 actor 只能读取、取消、导出同组织、同工作区内自己的任务。
- `DATA_ANALYST_AGENT_ADMIN_ACTORS` 中的 actor 可以查看全局任务和指标，默认是 `admin,local`。
- 角色权限：`viewer` 只读；`analyst` 可创建/取消任务；`admin` 可查看审计和清理终态任务。
- 任务列表、任务详情、报告导出和指标都会按 organization/workspace 过滤，避免跨组织或跨工作区泄漏。
- 审计日志会记录 actor、动作、目标、IP、trace id 和摘要信息。

## 运行 API

```text
GET  /api/health        健康、数据库和容量状态
POST /api/analyze       创建分析任务
GET  /api/jobs          当前 actor 的任务列表
GET  /api/jobs?scope=all 管理员查看全量任务
GET  /api/jobs/{id}     查询任务状态和结果
DELETE /api/jobs/{id}   取消排队或运行中的任务
DELETE /api/jobs?older_than_days=30 管理员清理终态任务记录
GET  /api/reports/{id}  导出 Markdown 报告
GET  /api/reports/{id}?format=html 导出 HTML 报告
GET  /api/reports/{id}?format=csv 导出 insight CSV 摘要
GET  /api/reports/{id}?format=pdf 导出 PDF 报告
GET  /api/reports/{id}?format=pptx 导出 PPTX 报告
GET  /api/metrics       任务总量、状态分布、容量和运行配置
GET  /api/metrics.prometheus Prometheus 文本指标
GET  /api/audit         最近审计事件
```

`POST /api/analyze` 支持可选字段：

```text
workspace=default
data_dictionary={"收入额":"revenue","成交日期":"date"}
```

## 发布门禁

发布前执行：

```powershell
python -m unittest discover -s tests
python -m evals.run_evals
python -m compileall data_analyst_agent backend evals
```

## 运行产物

任务和报告存储在：

```text
storage/agent.sqlite3
storage/reports
```

生产环境应把 `storage/` 挂载为持久卷。任务、结果、审计事件默认存储在 SQLite。

## 安全控制

- 设置 `DATA_ANALYST_AGENT_API_TOKEN` 后，API 路由要求 `X-API-Token` 或 `Authorization: Bearer ...`。
- 发送 `X-Actor` 标识用户或租户。
- 发送 `X-Role` 标识调用角色，默认是 `analyst`。
- 发送 `X-Trace-ID` 关联客户端请求、审计事件和任务活动。
- SQL 只允许 `SELECT`。
- Python 执行器通过 AST 策略阻止 import、open、eval、exec、文件写入等危险操作。
- 报告 HTML 导出会转义 Markdown 内容，避免脚本注入。
- 不同 actor 的任务和报告默认隔离。

## 运行限制

可配置项：

```text
DATA_ANALYST_AGENT_MAX_UPLOAD_MB
DATA_ANALYST_AGENT_MAX_CONCURRENT_JOBS
DATA_ANALYST_AGENT_JOB_TIMEOUT_SECONDS
DATA_ANALYST_AGENT_API_TOKEN
DATA_ANALYST_AGENT_ADMIN_ACTORS
DATA_ANALYST_AGENT_LLM_PROVIDER
DATA_ANALYST_AGENT_LLM_MODEL
DATA_ANALYST_AGENT_STORAGE_DIR
DATA_ANALYST_AGENT_DB
DATA_ANALYST_AGENT_DATABASE_URL
DATA_ANALYST_AGENT_REDIS_URL
DATA_ANALYST_AGENT_QUEUE
DATA_ANALYST_AGENT_EXECUTOR_MODE
DATA_ANALYST_AGENT_ALLOWED_DB_HOSTS
DATA_ANALYST_AGENT_RATE_LIMIT_PER_MINUTE
DATA_ANALYST_AGENT_MAX_ACTIVE_JOBS_PER_ACTOR
```

生产环境不要把 `local` 放入 `DATA_ANALYST_AGENT_ADMIN_ACTORS`；管理员权限只授予明确配置的 actor，普通请求即使发送 `X-Role: admin` 也不会获得管理员权限。

## Python Docker 沙箱

构建沙箱镜像：

```powershell
docker build -f docker/sandbox.Dockerfile -t data-analyst-agent-sandbox:latest .
```

启用：

```powershell
$env:DATA_ANALYST_AGENT_EXECUTOR_MODE="docker"
```

沙箱运行参数包括：

- `--network none`
- `--read-only`
- `--cpus 1`
- `--memory 512m`
- `--pids-limit 128`

安全说明：默认生产 compose 只在 `worker` 服务挂载 Docker socket。若要在容器内调度 Docker 沙箱，应把该权限限制在受控 worker 节点上，避免 API 容器持有 Docker 控制权限。

## 多表和数据库连接

- Excel 多 sheet 会被读取为表集合，并选择行数最多的 sheet 作为主分析表。
- 系统会为多 sheet 生成表摘要，并根据字段名、取值重叠和唯一性推断潜在关联关系。
- `data_analyst_agent.database_connector` 提供 PostgreSQL 只读查询入口。
- 数据库查询只允许 `SELECT`，会包裹 `LIMIT`，并校验主机必须在 `DATA_ANALYST_AGENT_ALLOWED_DB_HOSTS`。

## 当前边界

- 标准库 HTTP server 仍可本地运行；生产建议使用 FastAPI。
- 后台任务本地是进程内线程；生产建议使用 Redis/RQ worker。
- Python 执行器默认是 AST 防护；生产可启用 Docker 沙箱。
- API token、actor 隔离和轻量 RBAC 已具备，但还不是完整的企业 SSO/OIDC。
- SQLite 足够本地和演示环境；高并发生产环境建议切换 PostgreSQL。

## 下一步生产强化

- 更完整的 typed request/response models 和 API versioning。
- Worker 重试策略、死信队列、横向扩容和任务优先级。
- 独立沙箱 worker 节点，避免 API 容器持有 Docker 权限。
- SSO/OIDC、组织、项目、成员、RBAC 和配额。
- 结构化 trace/span，记录每个 plan step、tool call、耗时、错误和成本。
- 数据保留策略、任务过期清理、报告生命周期和备份恢复。
- 线上告警：失败率、排队时间、P95 延迟、成本、沙箱拒绝和异常增长。
