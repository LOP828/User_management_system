# 企业微信通知第一阶段最小落地准备

更新日期：2026-03-20

## 1. 本轮结论

- 本轮只收敛企业微信通知第一阶段最小范围，不做小程序消息。
- 第一阶段先覆盖 `transfer / success / reminder` 三条现有闭环。
- 第一阶段先做“事件触发点 + 发送适配层 + 配置项 + 异步任务入口”。
- 第一阶段不引入站内消息中心、不做复杂通知策略、不改已收口业务主链。

## 2. 第一阶段最小通知范围

### 2.1 先通知哪些角色

- `admin`
  - 接收：转移申请待审批、成功申请待审批
- `matchmaker`
  - 接收：转移审批结果（原负责人 / 新负责人）
  - 接收：成功申请审批结果（申请人 / 配对卡主操作红娘）
  - 接收：已存在 reminder 的到达通知（reminder 接收人）

### 2.2 先接哪些业务事件

- `transfer_applied`
  - 触发点：`apps.transfer.services.create_transfer_request`
  - 接收人：管理员
- `transfer_approved`
  - 触发点：`apps.transfer.services.approve_transfer_request`
  - 接收人：原负责人、新负责人
- `transfer_rejected`
  - 触发点：`apps.transfer.services.reject_transfer_request`
  - 接收人：申请人（即原负责人）
- `success_applied`
  - 触发点：`apps.success.services.create_success_application`
  - 接收人：管理员
- `success_approved`
  - 触发点：`apps.success.services.approve_success_application`
  - 接收人：申请人、配对卡主操作红娘
- `success_rejected`
  - 触发点：`apps.success.services.reject_success_application`
  - 接收人：申请人、配对卡主操作红娘
- `reminder_due`
  - 触发点：第一阶段仅针对已写入数据库的 reminder 做发送
  - 接收人：`reminder.staff_id`
  - 覆盖类型：`manual / followup_timeout / pause_revisit / first_meet_* / success_revisit`

## 3. 为什么这样最小且可执行

- 这三条链路已真实联调通过，业务口径稳定，适合在现有服务层挂通知事件，不会反向冲击已收口模块。
- `transfer` 与 `success` 已有明确审批动作和角色边界，通知对象确定，不需要额外业务判断。
- `reminder` 已有持久化模型、接收人字段、Celery 定时扫描和列表处理闭环，具备“以 reminder 记录为发送源”的最小条件。
- `match_card matched_revisit` 当前一部分是派生展示、一部分是持久化提醒；第一阶段若强行覆盖会把范围扩到“派生提醒转真实发送策略”，不够小，因此先只发已持久化 reminder。

## 4. 依赖的现有模块与状态流转

### 4.1 现有模块

- `apps.transfer`
  - 已有申请、审批通过、驳回服务入口
  - 已有 `UserTransferRequest` 持久化模型
- `apps.success`
  - 已有申请、审批通过、驳回、失效服务入口
  - 已有 `SuccessApplication` / `SuccessCase` 持久化模型
- `apps.reminder`
  - 已有 `Reminder` 持久化模型
  - 已有 Celery 扫描任务：`scan_followup_timeout` / `scan_first_meet` / `scan_pause_revisit`
  - 已有 `staff_id` 接收人字段
- `apps.staff`
  - 已有 `wechat_id` 字段，可作为后续 receiver 标识的预留数据
- `apps.oplog`
  - 已有 canonical action：`transfer_*`、`success_*`、`reminder_set`、`follow_up_created`
  - 可复用作发送失败排查时的业务上下文辅助

### 4.2 现有状态与动作入口

- 转移申请：
  - `pending -> approved / rejected`
- 成功申请：
  - `pending -> approved / rejected`
  - 审批通过后配对卡 `success_pending_review -> success`
- reminder：
  - reminder 已持久化，状态含 `pending / sent / processed / expired`
  - 第一阶段建议把企业微信发送成功后更新为 `sent`

## 5. 第一阶段需要新增的最小能力

### 5.1 发送适配层

- 新增 `apps.notify` 模块
- 提供单一出口，例如：
  - `send_wecom_text(webhook_key, content)`
  - `enqueue_wecom_event(event_type, payload, receivers)`

### 5.2 异步任务入口

- 新增 Celery task，负责企业微信实际发送
- 业务服务层只负责入队，不直接调用外部 webhook

### 5.3 配置项

- 企业微信 webhook 基础配置
  - 例如全局 webhook key / URL
- 开关配置
  - 是否启用企业微信通知
  - 是否启用 reminder 到达通知

### 5.4 事件钩子

- 在以下服务函数成功提交事务后触发通知入队：
  - `create_transfer_request`
  - `approve_transfer_request`
  - `reject_transfer_request`
  - `create_success_application`
  - `approve_success_application`
  - `reject_success_application`
- reminder 链路第一阶段建议新增独立扫描或发送入口：
  - 从 `Reminder.status = pending` 且 `remind_at <= now` 的记录中取数发送
  - 成功后置为 `sent`

### 5.5 最小观测能力

- 发送请求/响应日志
- 失败重试或至少失败留痕
- 与业务日志分离，不改 `operation_log` 语义

## 6. 本轮明确不做

- 不做小程序消息通知
- 不做站内消息中心
- 不做复杂通知策略、汇总推送、订阅偏好
- 不做全量历史 reminder 补发策略
- 不把 `matched_revisit` 派生提醒强行接入第一阶段真实发送
- 不处理 success approve / invalidate 读后延迟
- 不重审已收口模块

## 7. 下一步唯一建议

- 进入实现时，只做一件事：补齐 `apps.notify` 最小骨架，并先接通 `transfer_applied + success_applied + persisted reminder_due` 三类企业微信发送链路。
