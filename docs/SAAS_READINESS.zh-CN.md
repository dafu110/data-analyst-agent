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

- SSO/OIDC：接入 OIDC discovery、JWKS 校验、组织域名映射、成员邀请和 SCIM/手工成员同步；当前 `X-Actor` / `X-Role` 只适合本地演示或网关后可信注入。
- 组织计费：接入订阅计划、支付回调、账单周期、超额用量、暂停/恢复服务和发票导出；当前成本与 quota 是估算和预警，不是可收费账单。
- 成员与权限：把 actor、organization、workspace、role 落到服务端成员表，支持项目级角色、数据集级共享、审计导出和数据保留策略。
- 服务端看板：保存看板、图表编辑版本和报告模板，而不只是浏览器本地保存。
- 结构化成本：按模型、工具、任务、租户统计 trace/span 成本，形成真实账单和成本回放。

## 商业化接入建议顺序

1. OIDC 登录与成员表：先替换演示用请求头身份，确保租户边界可信。
2. 服务端配额与计费状态：把 plan、quota、用量写入持久化存储，并由后端强制限额。
3. 支付与订阅回调：接入支付平台后，把订阅状态同步到账户用量接口。
4. 审计与合规导出：按组织导出任务、报告、权限和高风险操作记录。
