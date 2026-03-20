# Matchmaker Server

## 当前状态

本目录包含 AI 红娘配对跟进管理系统的 Django 后端实现。

当前真实状态：
- 后端核心主链已完成，项目已从 P0 收口进入联调前准备阶段
- recommendation / followup / reminder / success / transfer / dashboard / search / oplog / user detail / priority_score 已有真实实现
- recommendation 已补齐 `candidate-search`、推荐历史 owner 可见、batch 单选硬约束
- reminder / success / followup 的 P0 收口项已完成：
  - `success_pending_review` 禁止创建 `matched` followup
  - `ended` 配对卡 reminder 不可再被 process
  - success approve 后清理旧 match 阶段 manual reminder
  - `first_meet_overdue` 自动补跟进时补写 `follow_up_created` 审计日志

当前全量测试状态：
- `536 passed`

## 已实现能力

- 认证、红娘、配置管理基础能力
- 用户档案、状态流转、暂停/恢复、`paused_at`
- recommendation 批次创建、选中、关闭、历史查询、候选搜索
- 配对卡创建、阶段推进、结束、风险管理
- followup 三种 scene：`unmatched` / `matched` / `success_followup`
- reminder 持久化、manual、process、expire、自动扫描任务
- success / transfer 审批闭环
- dashboard 统计与明细
- operation_log canonical action 收口

## 本地运行

1. 使用仓库内虚拟环境或自行创建虚拟环境并安装 `requirements.txt`
2. 复制 `.env.example` 为 `.env`
3. 准备 PostgreSQL，并确保 `.env` 中的连接参数可用
4. 执行迁移：

```bash
./.venv/bin/python manage.py migrate
```

5. 初始化管理员账号：

```bash
./.venv/bin/python manage.py init_admin
```

6. 启动 Django：

```bash
./.venv/bin/python manage.py runserver 127.0.0.1:8000
```

7. 登录拿 token：

```bash
curl -X POST http://127.0.0.1:8000/api/v1/auth/login/ \
  -H 'Content-Type: application/json' \
  -d '{"phone":"13800000000","password":"Passw0rd123!"}'
```

8. 运行测试：

```bash
./.venv/bin/pytest -q
```

### PostgreSQL 最小准备方案

项目 dev 配置默认使用 PostgreSQL：
- host: `127.0.0.1`
- port: `5432`
- db: `matchmaker`
- user: `postgres`
- password: `postgres`

至少需要保证：
- 本机存在可用 PostgreSQL 实例
- 能连通 `127.0.0.1:5432`
- 已创建数据库 `matchmaker`

若本机已安装 PostgreSQL，可执行：

```sql
CREATE DATABASE matchmaker;
ALTER USER postgres WITH PASSWORD 'postgres';
```

若你使用 Docker Desktop，可执行：

```bash
docker run --name matchmaker-postgres \
  -e POSTGRES_DB=matchmaker \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -p 5432:5432 \
  -d postgres:16
```

### 说明

- 基础 HTTP API 联调阶段，Redis 不是 blocker；只有 Celery / 定时任务需要 Redis。
- 当前仓库内 `local/postgresql-16.4` 是 PostgreSQL 源码目录，不是可直接启动的数据库实例。

## 企业微信冒烟验证

- phase 1 第一批真实环境冒烟步骤见 [../docs/13_wecom_smoke_validation.md](/mnt/d/project/User_management_system/docs/13_wecom_smoke_validation.md)
- 手动触发 persisted reminder_due 发送可执行：

```bash
./.venv/bin/python manage.py send_due_reminders_once --limit 20
```

## 说明

- `staff` 是 Django `AUTH_USER_MODEL`
- 默认管理员账号不会通过迁移自动创建
- 企业微信/小程序消息通知仍属后续集成项，不在当前后端闭环范围内
