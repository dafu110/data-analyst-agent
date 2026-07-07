# 生产端到端验证与 Docker 沙箱安全

本文用于验证真实 `Docker daemon + PostgreSQL + Redis/RQ` 环境是否可运行完整分析链路。

## 前置条件

- 已配置 `.env.prod`，且不要使用示例弱口令。
- 宿主机 Docker daemon 可用。
- 生产部署默认使用 `DATA_ANALYST_AGENT_EXECUTOR_MODE=docker`。
- `docker-compose.prod.yml` 会构建 `data-analyst-agent-sandbox:latest`；只有 worker 挂载 Docker socket 并通过 Docker CLI 启动只读、无网络、资源受限的沙箱容器，API 不持有 Docker socket。

## 启动

```powershell
docker compose -f docker-compose.prod.yml --env-file .env.prod up --build
```

## 端到端冒烟检查

在服务健康后运行：

```powershell
python scripts/production_e2e_check.py --base-url http://127.0.0.1:8000 --token "<DATA_ANALYST_AGENT_API_TOKEN>"
```

脚本会检查：

- `/api/health` 返回 `postgresql`、`redis-rq`、`docker`
- 上传 `examples/sales.csv`
- 轮询任务直到完成
- 验证报告正文、图表规格和 `md/html/csv` 导出

## Docker Socket 风险说明

当前生产 compose 只给 worker 挂载 `/var/run/docker.sock`，API 容器不直接持有 Docker 权限。这个方案比 API/worker 都持有 socket 更符合最小权限，但 Docker socket 仍等价于较高宿主机权限，必须只用于受控主机。

推荐约束：

- worker 所在主机不要混跑不可信业务；API 继续保持无 Docker socket 权限。
- 只允许受控运维账号访问 `.env.prod` 和 Docker socket。
- 定期执行 `python -m backend.production_check --require-external`。
- 生产网络侧使用反向代理、TLS、访问日志和请求体大小限制。
- 对更高安全要求的部署，优先改为独立沙箱 worker 节点、Kubernetes Job、Firecracker/gVisor 或远程受限执行池，避免 Web API 容器直接持有 Docker socket。

## 压测建议

- 并发创建 3-10 个任务，确认 Redis/RQ 排队、worker 处理和取消行为。
- 上传接近 `DATA_ANALYST_AGENT_MAX_UPLOAD_MB` 的 CSV，观察内存和任务耗时。
- 人为提交错误文件、取消运行中任务，确认失败状态、审计记录和上传文件清理。
