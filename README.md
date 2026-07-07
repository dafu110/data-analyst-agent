# Data Analyst Agent

一个中文数据分析 Agent / SaaS 原型，用于上传 CSV、Excel 或连接数据库后，自动完成数据画像、字段识别、质量检查、图表建议、业务洞察、报告导出和追问分析。

## 界面截图

![Data Analyst Agent 中文工作台](docs/assets/data-analyst-agent-workbench.png)

## 当前能力

- 上传 CSV、Excel，多 sheet Excel 会自动选择主表并保留表结构信息
- 自动生成数据画像、字段类型、缺失值、质量评分和质量门禁
- 识别日期、地区、产品、渠道、收入、成本、利润等业务字段
- 自动规划并执行 SQL / Python 分析步骤
- 生成多种图表规格，包括缺失值、均值、范围、分类分布、相关性、时间趋势、分群贡献
- 生成中文业务报告、管理层摘要、行动建议和指标口径
- 支持 Markdown、HTML、CSV、PDF、PPTX 报告导出
- 支持 FastAPI / OpenAPI、任务状态、审计、限流、基础 RBAC
- 支持 PostgreSQL、Redis/RQ worker、Docker Python 沙箱的生产化配置
- 内置单元测试、eval 数据集和 FastAPI smoke 端到端测试

## 快速运行

安装依赖：

```powershell
python -m pip install -e .[prod]
```

启动 FastAPI 服务：

```powershell
python -m backend.fastapi_app --host 127.0.0.1 --port 8002
```

打开应用：

```text
http://127.0.0.1:8002
```

OpenAPI 文档：

```text
http://127.0.0.1:8002/docs
```

## 国内安装

如果依赖下载慢，可以使用国内镜像：

```powershell
python -m pip install -e .[prod] -i https://pypi.tuna.tsinghua.edu.cn/simple
```

## 命令行分析

```powershell
python -m data_analyst_agent.cli examples\sales.csv --goal "分析销售表现和数据质量"
```

## 测试与验证

发布前建议运行：

```powershell
python -m compileall data_analyst_agent backend evals
node --check frontend\app.js
python -m unittest discover -s tests
python -m evals.run_evals
```

生产 Compose 服务启动后，可以运行端到端验证：

```powershell
python scripts\production_e2e_check.py --base-url http://127.0.0.1:8000 --token <DATA_ANALYST_AGENT_API_TOKEN>
```

单独运行 FastAPI 主链路 smoke 测试：

```powershell
python -m unittest tests.test_fastapi_smoke
```

生产依赖和外部服务检查：

```powershell
python -m backend.production_check
```

如果要求 PostgreSQL、Redis、Docker 必须可用：

```powershell
python -m backend.production_check --require-external
```

## PostgreSQL / Redis / Worker

配置 PostgreSQL：

```powershell
$env:DATA_ANALYST_AGENT_DATABASE_URL="postgresql://user:password@localhost:5432/data_analyst_agent"
```

配置 Redis 队列：

```powershell
$env:DATA_ANALYST_AGENT_REDIS_URL="redis://localhost:6379/0"
```

启动 API：

```powershell
python -m backend.fastapi_app --host 127.0.0.1 --port 8002
```

启动 worker：

```powershell
python -m backend.worker
```

## Docker Python 沙箱

构建沙箱镜像：

```powershell
docker build -f docker/sandbox.Dockerfile -t data-analyst-agent-sandbox:latest .
```

启用 Docker 执行器：

```powershell
$env:DATA_ANALYST_AGENT_EXECUTOR_MODE="docker"
```

## 生产环境安全基线

界面和报告默认使用中文。生产环境建议显式设置：

```powershell
$env:DATA_ANALYST_AGENT_ENV="prod"
$env:DATA_ANALYST_AGENT_API_TOKEN="<strong-token>"
$env:DATA_ANALYST_AGENT_EXECUTOR_MODE="docker"
$env:DATA_ANALYST_AGENT_DATABASE_URL="postgresql://user:password@localhost:5432/data_analyst_agent"
$env:DATA_ANALYST_AGENT_REDIS_URL="redis://localhost:6379/0"
```

当 `DATA_ANALYST_AGENT_ENV` 为 `prod` 或 `production` 时，服务会强制检查 API Token、Docker 沙箱、PostgreSQL 和 Redis/RQ 配置，避免以本地开发默认值裸跑。

## 项目结构

```text
backend/                 FastAPI、HTTP 服务、任务存储、导出器、worker、生产检查
data_analyst_agent/      Agent 核心、画像、规划、执行、洞察、报告、图表
frontend/                中文 SaaS 前端工作台
evals/                   回归评测数据集
examples/                示例数据
tests/                   单元测试和端到端 smoke 测试
docs/                    中文快速开始、运维和生产验证文档
docker/                  Python 沙箱镜像和运行脚本
```

## 关键文档

- [中文快速开始](docs/QUICKSTART.zh-CN.md)
- [生产级端到端验证清单](docs/PRODUCTION_VERIFICATION.zh-CN.md)
- [运维手册](docs/OPERATIONS.md)

## 当前成熟度

当前项目已经适合个人和小团队真实使用，也具备 SaaS 化的基础架构。距离成熟商业 SaaS 还需要继续加强：

- 完整真实联调 PostgreSQL、Redis/RQ worker、Docker 沙箱
- 进一步拆分前端渲染层，持续减少高风险 `innerHTML`
- 增加登录、组织、套餐、用量计费和租户隔离
- 增强 BI 交互：字段拖拽、筛选器、看板保存、图表编辑
- 增强报告模板：老板版、客户版、部门版、PPT 模板
- 加入 CI、发布流程、监控告警、成本和延迟统计

## 建议运行顺序

1. 先运行 `python -m unittest discover -s tests`
2. 再运行 `python -m evals.run_evals`
3. 启动 `python -m backend.fastapi_app --host 127.0.0.1 --port 8002`
4. 打开 `http://127.0.0.1:8002`
5. 上传 `examples/sales.csv` 体验完整分析流程
