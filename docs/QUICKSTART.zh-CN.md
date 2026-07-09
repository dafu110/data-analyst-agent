# Data Analyst Agent 快速使用指南

这是一个中文数据分析 Agent，用于 CSV / Excel 数据集的自动画像、业务字段识别、图表建议、管理摘要、质量门禁、报告导出和追问。

## 本地运行

先安装生产依赖：

```powershell
python -m pip install -e .[prod]
```

国内网络较慢时可以使用镜像：

```powershell
python -m pip install -e .[prod] -i https://pypi.tuna.tsinghua.edu.cn/simple
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

如果 8002 被占用，可以换成 8003 或其他端口。

## 推荐使用方式

1. 上传 CSV 或 Excel 文件。
2. 选择业务场景，例如销售、电商、财务、客户运营。
3. 选择分析深度：
   - 快速诊断：适合快速查看主要问题。
   - 标准分析：适合日常经营分析。
   - 深度复盘：会输出更多 trace、指标口径和原始结果。
4. 选择交付格式：
   - 业务报告：适合分析师和业务负责人。
   - 管理摘要：适合老板或管理层。
   - 诊断清单：适合检查数据质量和字段口径。
5. 点击开始分析，完成后查看图表、报告、追问和导出。

## 当前能力

- CSV / Excel 多 sheet 数据分析。
- 数据质量评分、缺失值、重复行、常量字段检查。
- 业务语义识别：收入、销量、区域、产品、日期、成本、利润等。
- 自动生成分析计划、关键洞察、行动建议和指标口径。
- 图表规格：柱状图、趋势图、数值范围图、分组贡献图。
- 导出 Markdown、HTML、CSV 摘要、PDF、PPTX。
- 任务历史、状态时间线、取消任务、审计日志、运行指标。
- FastAPI / OpenAPI、PostgreSQL、Redis/RQ worker、Docker 沙箱入口。

## 生产运行建议

生产环境建议显式配置：

```text
DATA_ANALYST_AGENT_ENV=prod
DATA_ANALYST_AGENT_API_TOKEN=<strong-token>
DATA_ANALYST_AGENT_DATABASE_URL=postgresql://user:password@localhost:5432/data_analyst_agent
DATA_ANALYST_AGENT_REDIS_URL=redis://localhost:6379/0
DATA_ANALYST_AGENT_EXECUTOR_MODE=docker
DATA_ANALYST_AGENT_MAX_UPLOAD_MB=10
DATA_ANALYST_AGENT_MAX_CONCURRENT_JOBS=2
DATA_ANALYST_AGENT_RATE_LIMIT_PER_MINUTE=60
```

生产启动：

```powershell
python -m backend.fastapi_app --host 0.0.0.0 --port 8000
python -m backend.worker
```

本地 `in_process` Python 执行器只用于开发和演示；生产环境必须使用 Docker executor。

## 验证命令

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
python scripts\production_e2e_check.py --base-url http://127.0.0.1:8000 --token $env:DATA_ANALYST_AGENT_API_TOKEN
```

## 常见问题

### 端口被占用

换一个端口：

```powershell
python -m backend.fastapi_app --host 127.0.0.1 --port 8003
```

### Excel 读取失败

请确认已经安装生产依赖：

```powershell
python -m pip install -e .[prod]
```

### PDF 中文乱码

PDF 导出需要系统中存在微软雅黑、黑体、宋体、文泉驿或 Noto Sans CJK 等中文字体。安装字体后重启服务，并重新导出 PDF。

### 报告只有少量图表

可以选择：

```text
分析深度：深度复盘
交付格式：业务报告
```
