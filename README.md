# Data Analyst Agent

[![CI](https://github.com/dafu110/data-analyst-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/dafu110/data-analyst-agent/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

一个中文数据分析 Agent / SaaS 原型，用于上传 CSV、Excel 或连接数据库后，自动完成数据画像、字段识别、质量检查、图表建议、业务洞察、报告导出和追问分析。

## 项目概览

面向业务分析场景的中文数据 Agent，提供受控的数据画像、分析规划、执行证据和报告导出。

## 界面预览

![Data Analyst Agent 中文工作台](docs/assets/data-analyst-agent-workbench.png)

## 快速开始

```powershell
python -m pip install -e .[prod]
python -m backend.fastapi_app --host 127.0.0.1 --port 8002
```

打开 `http://127.0.0.1:8002`；OpenAPI 文档位于 `http://127.0.0.1:8002/docs`。

## 演示与验证

1. 按[快速开始](#快速开始)启动服务，并打开 `http://127.0.0.1:8002`。
2. 上传 `examples/sales.csv`，确认数据画像和质量检查后生成分析计划。
3. 审核计划并查看分析详情，确认结论、执行证据和报告导出都可追溯。

截图展示上传前的受控工作台。完整的结果态验证路径见 [销售复盘演示](docs/SALES_REVIEW_DEMO.md)：上传 `examples/sales.csv` 后，先审核数据画像和分析计划，再查看带来源步骤的结论与导出报告。

### `sales.csv` 结果示例

以下结果由 `python -m data_analyst_agent.cli examples\sales.csv --goal "分析销售表现和数据质量"` 生成，可由同一命令复现：

- 数据画像：10 行、5 列，质量评分 100%，所有字段缺失值为 0。
- 区域结论：`East` 收入为 6120，占样例总收入的 42.6%（计算步骤：`profile`、`revenue-by-region`）。
- 产品结论：`Notebook` 收入最高，为 8820；`Pen` 销量最高，为 285（计算步骤：`revenue-by-product`、`units-by-product`）。
- 结果边界：样例没有日期字段且不足 30 行，因此生成报告会将趋势、同比和相关性结论标记为需要人工复核。

### 可复现验证

README 不把某次本地测试数量当作持续有效的质量结论。顶部 CI 徽章反映默认分支的当前状态；下面的[测试与验证](#测试与验证)命令可在本地复现单元测试、离线 eval、前端语法检查和导出 smoke。

生产外部依赖仍需在目标环境中通过 `python -m backend.production_check --require-external` 验证 Docker、PostgreSQL、Redis/RQ 和受限沙箱。

## 核心能力

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

## 架构与实现

`data_analyst_agent/` 负责数据画像、分析规划、受控执行与报告生成；`backend/` 提供 API、任务和导出服务；`frontend/` 提供中文工作台。

### 本地运行命令

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

### 国内安装

如果依赖下载慢，可以使用国内镜像：

```powershell
python -m pip install -e .[prod] -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 命令行分析

```powershell
python -m data_analyst_agent.cli examples\sales.csv --goal "分析销售表现和数据质量"
```

## 测试与验证

发布前建议运行：

```powershell
python -m compileall data_analyst_agent backend evals
node --check frontend\app.js
node --check frontend\labels.js
node --check frontend\charts.js
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

`--require-external` 会把 PostgreSQL、Redis/RQ、Docker server、`data-analyst-agent-sandbox:latest` 镜像和一次只读/无网络/降权的沙箱容器 smoke 都作为失败门禁。

## 部署与生产

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

### Docker Python 沙箱

构建沙箱镜像：

```powershell
docker build -f docker/sandbox.Dockerfile -t data-analyst-agent-sandbox:latest .
```

启用 Docker 执行器：

```powershell
$env:DATA_ANALYST_AGENT_EXECUTOR_MODE="docker"
```

本地 `in_process` 执行器只用于开发和演示，依赖 AST guard 阻断 import、open、eval、exec、dunder 属性访问和文件写出方法；生产环境必须使用 Docker executor。

### 生产环境安全基线

界面和报告默认使用中文。生产环境建议显式设置：

```powershell
$env:DATA_ANALYST_AGENT_ENV="prod"
$env:DATA_ANALYST_AGENT_API_TOKEN="<strong-token>"
$env:DATA_ANALYST_AGENT_EXECUTOR_MODE="docker"
$env:DATA_ANALYST_AGENT_DATABASE_URL="postgresql://user:password@localhost:5432/data_analyst_agent"
$env:DATA_ANALYST_AGENT_REDIS_URL="redis://localhost:6379/0"
```

当 `DATA_ANALYST_AGENT_ENV` 为 `prod` 或 `production` 时，服务会强制检查 API Token、Docker 沙箱、PostgreSQL 和 Redis/RQ 配置，避免以本地开发默认值裸跑。

### 实现细节

分析链路由 `data_analyst_agent/` 负责画像、规划、执行与报告生成，`backend/` 提供 API、任务与导出服务，`frontend/` 提供中文工作台。

## 生产边界

本地 `in_process` 执行器仅用于开发和演示；生产环境需要启用 Docker 沙箱、PostgreSQL、Redis/RQ 和 API Token。

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

## 相关文档与上线准备

- [中文快速开始](docs/QUICKSTART.zh-CN.md)
- [API 接口说明](docs/API.md)
- [生产级端到端验证清单](docs/PRODUCTION_VERIFICATION.zh-CN.md)
- [运维手册](docs/OPERATIONS.md)
- [Launch hardening checklist](docs/launch-hardening.md)
- [ADR: Sandboxed analysis execution](docs/adr/0001-sandboxed-analysis-execution.md)
- [更新日志](CHANGELOG.md)

### 建议运行顺序

1. 先运行 `python -m unittest discover -s tests`
2. 再运行 `python -m evals.run_evals`
3. 启动 `python -m backend.fastapi_app --host 127.0.0.1 --port 8002`
4. 打开 `http://127.0.0.1:8002`
5. 上传 `examples/sales.csv` 体验完整分析流程

## 许可证

MIT. See [LICENSE](LICENSE).
