# 企业微信 Phase 1 第一批链路真实环境冒烟验证

更新日期：2026-03-20

适用范围：

- `transfer_applied`
- `success_applied`
- `success_approved`
- `success_rejected`
- `persisted reminder_due`

不包含：

- `transfer_approved`
- `transfer_rejected`
- 小程序消息
- 消息中心

## 1. 环境前置条件

### 1.1 基础服务

- Django API 可正常启动
- PostgreSQL 可连接
- Redis 可连接
- Celery worker 已启动
- `persisted reminder_due` 若要验证定时发送，Celery beat 也需启动

建议命令：

```bash
cd /mnt/d/project/User_management_system/matchmaker_server
./.venv/bin/python manage.py runserver 127.0.0.1:8000
./.venv/bin/celery -A config worker -l info
./.venv/bin/celery -A config beat -l info
```

### 1.2 企业微信配置

`.env` 至少补齐：

```env
WECOM_NOTIFY_ENABLED=true
WECOM_NOTIFY_REMINDER_DUE_ENABLED=true
WECOM_WEBHOOK_URL=https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=你的真实key
WECOM_NOTIFY_TIMEOUT_SECONDS=5
```

### 1.3 接收人前置

- 至少存在 1 个 `admin`，且 `wechat_id` 或手机号可被 webhook @ 到
- 触发 `persisted reminder_due` 时，对应 `reminder.staff_id` 的 `wechat_id` 或手机号应有效

### 1.4 数据前置

- `transfer_applied` 需要：
  - 一个可登录红娘
  - 一个该红娘名下用户
  - 一个目标红娘
- `success_applied` 需要：
  - 一个满足成功申请前置条件的配对卡
  - 若本地已有联调数据，可复用 [_codex_prepare_success_pending.py](/mnt/d/project/User_management_system/matchmaker_server/_codex_prepare_success_pending.py)
- `persisted reminder_due` 需要：
  - 数据库里存在 `status=pending` 且 `remind_at <= now` 的 persisted reminder
  - 类型必须在 phase 1 第一批允许集合内：`manual / followup_timeout / pause_revisit / first_meet_* / success_revisit`

## 2. 真实环境冒烟验证步骤

### 2.1 准备 token

```bash
curl -X POST http://127.0.0.1:8000/api/v1/auth/login/ \
  -H 'Content-Type: application/json' \
  -d '{"phone":"13800000000","password":"Passw0rd123!"}'
```

记录：

- 管理员 token
- 红娘 token

### 2.2 验证 `transfer_applied`

使用红娘 token 发起转移申请：

```bash
curl -X POST http://127.0.0.1:8000/api/v1/transfer-requests/ \
  -H "Authorization: Bearer <matchmaker_token>" \
  -H 'Content-Type: application/json' \
  -d '{"user_id":1,"to_staff_id":2,"reason":"企业微信冒烟验证"}'
```

### 2.3 验证 `success_applied`

先确保存在满足条件的配对卡。

若要快速准备 `match_card_id=1` 的联调数据，可执行：

```bash
cd /mnt/d/project/User_management_system/matchmaker_server
./.venv/bin/python _codex_prepare_success_pending.py
```

然后使用主操作红娘 token 发起成功申请：

```bash
curl -X POST http://127.0.0.1:8000/api/v1/success-applications/ \
  -H "Authorization: Bearer <primary_staff_token>" \
  -H 'Content-Type: application/json' \
  -d '{"match_card_id":1,"apply_note":"企业微信冒烟验证"}'
```

### 2.4 验证 `persisted reminder_due`

两种方式二选一。

方式 A：等 beat 自动触发

- 保持 worker 和 beat 运行
- 等待 `notify.send_due_reminders` 调度执行

方式 B：手动执行一次发送命令

```bash
cd /mnt/d/project/User_management_system/matchmaker_server
./.venv/bin/python manage.py send_due_reminders_once --limit 20
```

## 3. 每条链路如何判断成功

### 3.1 `transfer_applied`

成功标志：

- API 返回 `201`
- worker 日志能看到 `notify.send_phase1_event`
- 企业微信群收到“转移申请待审批”消息
- 消息内容包含：
  - 用户名 / 用户 ID
  - 发起人
  - 目标红娘
  - 原因

### 3.2 `success_applied`

成功标志：

- API 返回 `201`
- 配对卡进入 `success_pending_review`
- worker 日志能看到 `notify.send_phase1_event`
- 企业微信群收到“成功申请待审批”消息
- 消息内容包含：
  - 配对卡 ID
  - 配对双方
  - 申请人
  - 申请说明

### 3.3 `persisted reminder_due`

成功标志：

- worker 日志或管理命令输出里可见发送结果
- 企业微信群收到 reminder 到期通知
- 对应 `reminder.status` 从 `pending` 变为 `sent`

可用 SQL 或 shell 核对：

```sql
select id, remind_type, status, remind_at
from reminder
where id = <你的 reminder_id>;
```

## 4. 如果失败，先排查什么

优先按下面顺序排查。

### 4.1 配置未生效

- `WECOM_NOTIFY_ENABLED` 是否为 `true`
- `WECOM_NOTIFY_REMINDER_DUE_ENABLED` 是否为 `true`
- `WECOM_WEBHOOK_URL` 是否为真实可用地址
- 修改 `.env` 后 Django / worker / beat 是否已重启

### 4.2 Celery 未运行或未消费

- worker 是否已启动
- `transfer_applied` / `success_applied` 触发后，worker 是否看到 `notify.send_phase1_event`
- beat 是否已启动
- `persisted reminder_due` 若依赖定时调度，是否看到 `notify.send_due_reminders`

### 4.3 webhook 可达性或企业微信侧错误

- 服务机是否可访问企业微信 webhook 域名
- webhook key 是否正确
- 机器人是否仍在群内
- 企业微信返回是否出现非零 `errcode`

### 4.4 接收人不可被命中

- `admin` 或 `reminder.staff` 是否存在
- `wechat_id` 或手机号是否为空
- webhook 群机器人是否允许对应 @ 方式

### 4.5 业务数据本身不满足触发条件

- `transfer_applied`：
  - user 是否属于当前红娘
  - `to_staff_id` 是否有效
- `success_applied`：
  - 配对卡是否处于 `stable_contact`
  - 男女双方是否各有 2 条有效回访
  - 是否满 30 天
  - `staff_judgment` 是否已填写
- `persisted reminder_due`：
  - reminder 是否为 persisted 记录
  - `status` 是否仍是 `pending`
  - `remind_at` 是否已到时
  - 类型是否属于第一批允许集合
  - 若是 `matched_revisit`，本轮本来就不会发送

## 5. 建议记录的最小验证结果

- 验证时间
- 验证环境
- webhook 群名
- 三条链路是否分别成功
- 对应 request id / application id / reminder id
- 失败截图或 worker 日志关键行

## 6. 2026-03-20 真实验收记录

### 6.1 验收范围

- 只做企业微信通知 phase 1 后端侧真实送达验收补证
- 本轮实际补证链路：`success_rejected`
- 同一轮脚本会先创建成功申请，再执行驳回，因此 worker 中会同时看到 `success_applied` 与 `success_rejected`

### 6.2 环境事实

- 业务库：Windows 本机 PostgreSQL，`127.0.0.1:5432`
- Redis：Docker 容器 `redis-dev`，`127.0.0.1:6379`
- worker：Windows 本机临时 Celery worker，`-P solo`
- `.env` 最终使用企业微信群机器人的真实 webhook 发送地址

### 6.3 过程记录

第一次真实验证使用了错误的企业微信 URL 形态：

- `openBotProfile/...` 管理页链接返回 `HTTP 404`

修正为 `qyapi.weixin.qq.com/cgi-bin/webhook/send?key=...` 后，又出现一次企业微信侧业务错误：

- `errcode=93000`
- `errmsg=invalid webhook url`

最终确认是 `.env` 修改后 worker 未重启导致旧配置仍在生效。重启 worker 并重新触发后，链路跑通。

### 6.4 最终成功证据

真实触发结果：

- `success_application.id=7`
- 状态：`rejected`

worker 就绪日志：

```text
[2026-03-20 20:02:59,768: INFO/MainProcess] Connected to redis://127.0.0.1:6379/0
[2026-03-20 20:03:00,887: INFO/MainProcess] celery@DESKTOP-5NBLU22 ready.
```

worker 消费与发送成功日志：

```text
[2026-03-20 20:03:15,707: INFO/MainProcess] Task notify.send_phase1_event[0f2e3be9-2a3f-4d66-8948-608211d293f2] received
[2026-03-20 20:03:15,709: INFO/MainProcess] notify.send_phase1_event received
[2026-03-20 20:03:15,811: INFO/MainProcess] Sending WeCom webhook
[2026-03-20 20:03:17,729: INFO/MainProcess] WeCom webhook delivered
[2026-03-20 20:03:17,761: INFO/MainProcess] Task notify.send_phase1_event[0f2e3be9-2a3f-4d66-8948-608211d293f2] succeeded in 2.0521516000007978s: {'ok': True, 'response': {'errcode': 0, 'errmsg': 'ok'}}
```

同一轮里 `success_applied` 也返回了成功响应：

```text
[2026-03-20 20:03:19,822: INFO/MainProcess] WeCom webhook delivered
[2026-03-20 20:03:19,838: INFO/MainProcess] Task notify.send_phase1_event[ffe8f675-4b9d-4ed9-899c-399ec121b40c] succeeded in 2.0674278999977105s: {'ok': True, 'response': {'errcode': 0, 'errmsg': 'ok'}}
```

### 6.5 本轮结论

- `success_rejected`：后端主链正常，worker 已消费，webhook 已发送且企业微信返回 `errcode=0`
- `success_applied`：同轮附带再次证明 webhook 发送成功
- “看不到企业微信群客户端”不构成后端失败判据；后端侧以 worker 消费日志和 webhook 成功响应为准

### 6.6 后续注意事项

- `.env` 中 `WECOM_WEBHOOK_URL` 必须使用真实 webhook 发送地址，不能使用 `openBotProfile/...` 管理页链接
- 修改 `.env` 后，Django / worker / beat 都必须重启，否则会继续使用旧配置
