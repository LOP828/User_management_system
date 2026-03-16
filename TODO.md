## TODO — AI红娘配对跟进管理系统 开发执行清单

### 维护口径

- 本清单按当前仓库真实实现状态维护，不沿用旧结论。
- 状态分为：**已完成 / 部分完成 / 未完成**。
- 判断依据以 `matchmaker_server` 当前代码、迁移、接口和测试为准。
- 最后一次全面对齐：2026-03-16，全量测试 295 条通过。

---

### 已完成

- **`[blocker]` A1 — 修复 met_not_continue 状态流转逻辑**
  - 进入/退出 `met_not_continue` 已按 BR-POOL-002 实现，含旧轮次隔离
  - 测试覆盖：进入成功、退出无记录拦截、退出有记录放行、旧记录不计入

- **`[blocker]` A2 — 补齐 last_unmatched_active_at 更新逻辑**
  - 创建用户时初始化为 created_at
  - 状态变更、followup(scene=unmatched)、发起推荐、配对结束回流均已更新
  - pause 不更新，resume 更新
  - 测试覆盖：创建初始化、状态变更、pause/resume 行为对比

- **`[high priority]` A3 — 放开 admin 的 owner_id 变更**
  - admin + force=true + force_reason 可修改 owner_id（BR-TRANSFER-003）
  - 变更后同步进行中配对卡侧边 staff 字段 + pending 提醒接收人 + last_action_at
  - oplog 写入 action=admin_force_change
  - matchmaker 仍被 PermissionDenied 拦截
  - 测试覆盖：成功路径、缺 force、缺 reason、matchmaker 被拒、配对卡同步、提醒同步

- **`[high priority]` A4 — 扩展用户详情可见性权限**
  - owner 可读可写；admin 可读可写；配对卡关联方（male/female/primary_staff）只读
  - 关联方范围：任意历史/当前配对卡（含 success/ended）
  - 测试覆盖：owner 可读写、关联红娘只读、非关联红娘无权限、关联红娘不能写

- **`[high priority]` A5 — 确认 success_application 阶段前置条件**
  - 前置阶段改为 stage=stable_contact
  - 创建后自动推进配对卡到 success_pending_review
  - 审批通过/驳回链路完整
  - 测试覆盖：stable_contact 才能发起、自动推进、时长不足拦截、重复 pending 拦截

- **`[blocker]` C1 — Phase A 修复的测试覆盖**
  - A1-A5 均有明确测试覆盖，全量测试通过

- **`[normal]` A6 — 统一 operation_log 字段模型**
  - canonical schema：operator/action/target_type/target_id/before_json/after_json/reason/created_at
  - 已补齐三组索引：target_type+target_id+created_at、operator_id+created_at、created_at
  - create_operation_log() 共享 helper 已落地，各模块均已收口
  - 测试覆盖：model contract、migration contract、helper 写入

- **`[high priority]` B1 — Reminder 模型与迁移**
  - Reminder 表已落地，含 target_type/target_id/staff_id/remind_type/remind_at/status/processed_at/is_manual/created_at
  - 三组索引：staff_id+status+remind_at、target_type+target_id、remind_at+status
  - status/target_type/remind_type check constraint 已落地
  - 测试覆盖：migration contract、模型默认值与枚举约束

- **`[high priority]` B2 — Reminder 服务层改造**
  - build_persisted_reminder_queryset()、create_reminder()、process_reminder()
  - expire_reminder()、expire_target_reminders()
  - refresh_match_card_next_remind_at() 已兼容持久化 Reminder 表
  - first_meet_overdue 处理：自动生成 scene=unmatched 跟进记录，更新 last_action_at/last_unmatched_active_at
  - 测试覆盖：创建、query、process、expire、refresh、first_meet_overdue 闭环

- **`[high priority]` B3 — Reminder API 端点**
  - GET /api/v1/reminders/：已切换到 persisted 单轨（build_persisted_reminder_queryset）
  - POST /api/v1/reminders/{id}/process/：基于 persisted Reminder.id
  - POST /api/v1/reminders/manual/：基于 create_manual_reminder()，旧提醒自动失效
  - 三端点均已注册；派生式 build_reminder_list() 已删除
  - 测试覆盖：列表权限/筛选、manual 创建覆盖、process 权限/重复/first_meet_overdue

- **`[high priority]` B4 — Recommendation 模型与迁移**
  - RecommendationBatch + RecommendationCandidate 两张表
  - 批次号 REC-YYYYMMDD-NNN；status/result check constraint；INDEX 齐全
  - 测试覆盖：migration contract、模型默认值、唯一约束、枚举约束

- **`[high priority]` B5 — Recommendation 服务与 API**
  - create_recommendation_batch()：BR-REC-001/002/003/006 + Addendum §3
  - select_candidate()：S3→S4 状态推进
  - close_recommendation_batch()：BR-REC-005（关闭无选中回退+待重新推荐标签）
  - API：POST/GET /recommendations/、POST /candidates/{id}/select/、POST /{id}/close/
  - 权限：matchmaker 只管理自己负责用户的批次；admin 全局
  - 批次号格式：REC-YYYYMMDD-NNN（当日顺序递增）
  - 测试覆盖：19 条，覆盖权限、BR-REC-001/002/003/005/006、批次列表过滤
  - **未实现：** GET /recommendations/candidate-search/（§6.5，BR-REC-004），候选人搜索端点未落地

- **`[high priority]` C2 — Recommendation 模块测试**（已随 B5 完成）

- **`[high priority]` B6 — Transfer 模型与迁移**
  - UserTransferRequest 表：id/user_id/from_staff_id/to_staff_id/reason/status/reviewer_id/review_note/reviewed_at/created_at
  - status enum: pending/approved/rejected；check constraint 已落地
  - INDEX(user_id)、INDEX(status)、INDEX(from_staff_id)
  - 测试覆盖：migration contract（6条）、模型 contract（8条）

- **`[high priority]` B7 — Transfer 服务与 API**
  - create_transfer_request()：BR-TRANSFER-001 全部校验
  - approve_transfer_request()：BR-TRANSFER-002（owner 变更+matchcard sync+reminder sync+oplog）
  - reject_transfer_request()：status→rejected + oplog
  - API：POST/GET /transfer-requests/、POST /{id}/approve/、POST /{id}/reject/
  - 权限：matchmaker 只能为自己负责的用户发起，GET 只看自己的；admin 审批全局
  - 审批通过联动：user.owner_id、last_action_at 变更；active matchcard 同步；pending reminder 接收人同步；oplog 写入
  - 测试覆盖：18 条，覆盖权限、BR-TRANSFER-001/002、驳回、列表筛选
  - **未实现：** 微信消息通知（BR-TRANSFER-002 步骤5/6），依赖 WeChat 基础设施

- **`[high priority]` C3 — Transfer 模块测试**（已随 B7 完成）

- **`[normal]` B8 — OpLog 序列化与 API**
  - GET /api/v1/operation-logs/；admin only
  - 过滤：target_type、target_id、operator_id、action、created_at_after、created_at_before
  - 分页：DefaultPageNumberPagination（count/page/page_size/results）
  - action_display 映射表（16 个已知 action 已覆盖）
  - 测试覆盖：12 条，权限/字段/过滤/分页/排序

- **`[normal]` B9 — Dashboard API**（部分完成，详见"部分完成"节）

- **`[normal]` B10 — Search API**
  - GET /api/v1/search/?q=...
  - 关键词匹配：name/phone/wechat（icontains）
  - 过滤：pool_status、owner_id（admin 专用）
  - 权限：matchmaker 只看 owner 或配对卡相关用户（与 A4 口径一致）；admin 全局
  - 返回字段含 match_field、active_match_card_id（子查询注解）
  - 测试覆盖：17 条，权限/结构/关键词/过滤/权限范围/active_card

- **`[normal]` C4 — Reminder 模块测试**
  - migration contract、模型 contract、服务层、API 共 30+ 条，全部通过
  - 待补：Celery task 单元测试（依赖 Celery 基础设施接入）

---

### 部分完成

- **`[normal]` B9 — Dashboard API（已实现统计部分，未实现明细列表）**
  - **已实现：**
    - GET /api/v1/dashboard/matchmaker/：用户池各状态计数、active 配对卡计数、pending 提醒计数
    - GET /api/v1/dashboard/admin/：全局用户池计数、配对卡计数（含 high_risk）、pending 提醒、pending_approvals（transfer+success）
    - 权限：matchmaker → /matchmaker/（数据范围限定自己）；admin → /admin/（全局）
    - 测试覆盖：14 条，权限/结构/过滤/计数正确性
  - **未实现（文档 §12.1 明细项）：**
    - unmatched_overdue.items：带 priority_score / overdue_days 的超时用户明细列表（BR-SORT-001）
    - matched_pending_visit.items：带 priority_score / overdue_days 的配对卡明细列表
    - today_processed.count：当日已处理数
    - recent_new.items：近期新用户列表
    - overdue_summary.by_staff：按红娘拆分超时数（admin §12.2）

---

### 未完成

- **`[blocker]` Celery 定时任务 — Reminder 自动生成**（部分完成）
  - Celery 基础设施（config/celery.py、CELERY_BROKER_URL）已接好；`tasks.py` 已有真实 task
  - **已实现（service 层 + task 包装）：**
    - `followup_timeout`（BR-REMIND-009）：`scan_followup_timeout_reminders()` + `@shared_task`
    - `first_meet_pending/delayed/warning/overdue/normal`（BR-REMIND-001）：`scan_first_meet_reminders()` + `@shared_task`
    - 幂等逻辑：followup_timeout 按当日去重；first_meet 按 active 提醒去重
    - 测试覆盖：20 条，含边界/幂等/跳过条件，全部通过
  - **仍未实现：**
    - `pause_revisit`（BR-REMIND-002）：阻塞——user 表无 `paused_at` 字段，BR-REMIND-002 "用户进入暂停的时间"无法直接取得
    - Celery Beat 调度配置（CELERY_BEAT_SCHEDULE）：任务函数已就绪，需配置定时计划
    - 微信消息实际发送（BR-REMIND-007）：依赖企业微信基础设施
  - 已自动生成的完整列表：matched_revisit（配对卡推进时）、success_revisit（成功申请时）、manual（手动创建）、followup_timeout、first_meet_* 系列

- **`[normal]` GET /recommendations/candidate-search/（BR-REC-004）**
  - 文档 §6.5 已定义，但代码中 recommendation/urls.py 未注册此端点
  - 功能：在候选人池中搜索（排除暂停/配对中/同性），配合推荐流程使用
  - 当前可用 GET /api/v1/search/ 做基础搜索替代，但语义不完全一致

- **`[normal]` WeChat 微信消息通知**
  - BR-TRANSFER-002 §5/6、审批通知链路均未实现
  - 依赖企业微信/小程序消息基础设施

- **`[normal]` Dashboard 明细列表（priority_score / overdue_days）**
  - 已在 B9 部分实现节详述
  - 涉及 BR-SORT-001 优先级算法，属于前端体验优化项

- **`[normal]` C5 — 文档对齐收尾**（本任务正在执行）

---

### 后续清理项

- **清理 last_unmatched_active_at 的 NULL baseline 历史数据**
  - 历史旧数据和测试工厂绕过 service 直接 create() 的路径仍可能留下 NULL
  - 建议：一次性 migration backfill + 兜底策略（NULL 时 fallback 到 created_at）
  - 不阻塞当前功能

- **action_display 映射表后续维护**
  - apps/oplog/serializers.py 中维护了 ACTION_DISPLAY_MAP
  - 新增 action 时需手动同步更新

- **Dashboard 统计查询性能**
  - 当前逐状态独立 count()，随数据量增长可考虑合并为 annotate + values + Count

---

### 当前全量测试状态

- 全量测试：**315 条**，全部通过（2026-03-16）
- 分布：user/matchcard/followup/success/reminder/recommendation/transfer/oplog/dashboard/search/migration/model contract

---

### 执行顺序建议（后续）

| 优先级 | 任务 | 前置条件 |
|--------|------|---------|
| 1 | Celery 基础设施接入 | Redis/RabbitMQ 环境 |
| 2 | Reminder 自动生成定时任务 | Celery 接入 |
| 3 | candidate-search 端点（BR-REC-004） | 无硬前置 |
| 4 | Dashboard 明细列表（priority_score） | 无硬前置 |
| 5 | WeChat 通知 | 企微基础设施 |
| 6 | 闭环 13-16（前端/小程序/联调/安全审计） | 后端 API 全部完成 |
