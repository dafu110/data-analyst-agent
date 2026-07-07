# SaaS 化就绪说明

本项目已经具备个人和小团队使用所需的基础能力，并补齐了面向 SaaS 化演进的可验证骨架。

## 已落地能力

- 生产联调：FastAPI 入口支持 PostgreSQL 存储、Redis/RQ worker、Docker Python 沙箱和生产 compose 模板。
- 账户与用量：`GET /api/account` 返回 actor、organization、workspace、role、plan、quota、usage 和 features。
- 权限隔离：任务、报告、指标按 actor、organization、workspace 过滤；普通用户发送 `X-Role: admin` 不会自动获得管理员权限。
- BI 交互：图表页支持筛选、类型切换、看板视图保存、图表标题和 X/Y 字段编辑、PNG/SVG/CSV 导出。
- 报告模板：支持业务报告、老板版摘要、客户汇报、部门复盘、PPT 大纲和诊断清单。
- 运维指标：Prometheus 暴露任务量、状态分布、平均/P95 延迟、估算成本和额度使用率。
- 发布门禁：CI 和 Release Gate 检查 Python 编译、单元测试、eval、前端语法、生产配置和 Docker 沙箱镜像。

## 运行环境建议

| 环境 | 存储 | 队列 | 执行器 | 用途 |
| --- | --- | --- | --- | --- |
| local | SQLite | in-process | AST guard | 本地开发、演示 |
| staging | PostgreSQL | Redis/RQ | Docker sandbox | 上线前联调 |
| production | PostgreSQL | Redis/RQ | Docker sandbox | 多用户团队使用 |

## 关键请求头

```text
Authorization: Bearer <DATA_ANALYST_AGENT_API_TOKEN>
X-Actor: alice
X-Org: acme
X-Workspace: finance
X-Role: analyst
X-Plan: team
X-Trace-ID: trace-20260707-001
```

## 监控与告警建议

- 失败率：`failed_jobs / total_jobs` 连续 10 分钟高于 5% 告警。
- 延迟：`data_analyst_agent_job_duration_p95_ms` 高于业务 SLA 告警。
- 成本：`data_analyst_agent_estimated_cost_usd` 当日增速异常告警。
- 额度：`data_analyst_agent_quota_used_ratio` 高于 80% 提醒，高于 95% 告警。
- 队列：`active_jobs` 长时间接近并发上限时扩容 worker。

## 仍需真实商业化接入

- SSO/OIDC、成员邀请、组织计费和支付回调。
- 服务端保存看板和图表编辑版本，而不只是浏览器本地保存。
- 更细粒度 RBAC、项目级配额、审计导出和数据保留策略。
- 结构化 trace/span 成本分摊，按模型、工具、租户统计真实账单。
