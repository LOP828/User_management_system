## TODO — AI红娘配对跟进管理系统 开发执行清单

### 维护口径

- 本清单按当前仓库真实实现状态维护，不沿用旧结论。
- 状态分为：**已完成 / 部分完成 / 未完成**。
- 判断依据以 `matchmaker_server` 当前代码、迁移、接口和测试为准。

---

### 已完成

- **`[blocker]` A1 — 修复 met_not_continue 状态流转逻辑**
  - 当前已实现：
    - 进入 `met_not_continue` 已从白名单放开
    - 退出 `met_not_continue` 按 BR-POOL-002 校验：需存在 `scene=unmatched` + `failure_reason_id IS NOT NULL` + `created_at > 进入时间` 的跟进记录
    - 旧轮次失败跟进不会误算进本轮退出条件
  - 测试现状：
    - 已覆盖进入成功、退出无记录拦截、退出有记录放行、旧记录不计入
  - 完成判定：
    - 当前代码和测试均满足，视为完成

- **`[blocker]` A2 — 补齐 last_unmatched_active_at 更新逻辑**
  - 当前已实现：
    - `create_customer_profile()` 创建用户时，初始化 `last_unmatched_active_at = created_at`
    - `change_user_status()`: `to_status != paused` 时更新 `last_unmatched_active_at`
    - `resume_user()`: 恢复到活跃未配对状态时更新
    - `pause_user()`: 不更新
    - `followup` 的 `scene=unmatched` 写入时会更新
    - 配对卡结束回流到未配对池时会更新
  - 测试现状：
    - 已覆盖红娘 API 创建用户即初始化 baseline
    - 已覆盖 admin API 创建用户即初始化 baseline
    - 已覆盖创建后再做状态变更时，`last_unmatched_active_at` 被后续更新时间正确覆盖
    - 已覆盖状态变更更新、pause 不更新、resume 更新、admin force→paused 不更新
  - 完成判定：
    - 当前代码和测试均满足，视为完成

- **`[high priority]` A3 — 放开 admin 的 owner_id 变更**
  - 当前已实现：
    - 按 BR-TRANSFER-003，`admin + force=true + force_reason` 可修改 `owner_id`
    - matchmaker 仍被 PermissionDenied 拦截
    - 变更后会写入 `operation_log`（`action=admin_force_change`）
    - 会同步更新该用户涉及的进行中配对卡侧边红娘字段：
      - 用户作为男方时更新 `male_staff_id`
      - 用户作为女方时更新 `female_staff_id`
      - `primary_staff_id` 不自动变更
    - 会同步更新 `user.last_action_at`
    - 当前仓库中的 reminder 为派生式列表，接收人取自进行中配对卡的侧边 staff 字段；因此配对卡侧边字段同步后，当前 reminder 接收人语义已自动对齐
  - 测试现状：
    - 已覆盖 admin 成功、缺 force 被拒、缺 reason 被拒、matchmaker 被拒
    - 已覆盖男方侧进行中配对卡同步、女方侧进行中配对卡同步、非进行中配对卡不误改、无关用户/无关 active 配对卡不误伤、derived reminder 接收人切换、`last_action_at` 更新
  - 完成判定：
    - 按当前文档口径与当前仓库实现方式，视为完成

- **`[high priority]` A4 — 扩展用户详情可见性权限**
  - 当前已实现：
    - owner 可读可写
    - admin 可读可写
    - 配对卡关联方（`male_staff` / `female_staff` / `primary_staff`）可查看用户详情
    - 关联方仅限只读，不获得 PATCH / PUT 权限
    - 非关联红娘仍无权访问
  - 当前口径：
    - 用户详情查看范围按“任意历史/当前配对卡”处理，包含 `success / ended`
    - 写权限仍仅限 owner 或 admin
  - 测试现状：
    - 已覆盖 owner 可读可写
    - 已覆盖关联红娘可只读
    - 已覆盖非关联红娘无权访问
    - 已覆盖关联红娘不能写
  - 完成判定：
    - 当前代码和测试均满足，视为完成

- **`[high priority]` A5 — 确认 success_application 阶段前置条件**
  - 当前已实现：
    - `apps/success/services.py` 已将前置阶段校验改为 `stage=stable_contact`
    - 创建成功申请后会自动推进配对卡到 `success_pending_review`
    - 审批通过/驳回链路与当前 success 模块测试一致
  - 测试现状：
    - 已覆盖 `stable_contact` 才能发起、创建后自动推进阶段、时长不足拦截、重复 pending 拦截等路径
  - 完成判定：
    - 当前代码和测试均满足，视为完成

- **`[blocker]` C1 — Phase A 修复的测试覆盖**
  - 当前已实现：
    - A1-A5 已按最新口径具备明确测试覆盖
    - A2 相关测试工厂默认 baseline 已与当前创建语义对齐；如需显式构造 `NULL` baseline，仍可在单测中显式传值
    - 当前全量测试 `177` 条通过
  - 完成判定：
    - 当前代码和测试均满足，视为完成

- **`[blocker]` B1 — Reminder 模型与迁移**
  - 当前已实现：
    - `apps/reminder/models.py` 已落地 `Reminder` 模型
    - `apps/reminder/migrations/0001_initial.py` 已创建 `reminder` 表
    - 已按文档补齐 `target_type / target_id / staff_id / remind_type / remind_at / status / processed_at / is_manual / created_at`
    - 已补齐 `target_type`、`remind_type`、`status` 的枚举约束
    - 已补齐 `staff_id + status + remind_at`、`target_type + target_id`、`remind_at + status` 三组索引
  - 当前口径：
    - B1 仅完成 Reminder 表结构与迁移，不改现有派生式 reminder 服务
    - 当前 `/reminders/` 仍沿用派生逻辑，Reminder 表将在 B2/B3 再接入
  - 测试现状：
    - 已覆盖 migration 建表、字段、外键、索引、基础 check constraint
    - 已覆盖 Reminder 模型默认值与非法枚举值约束
  - 完成判定：
    - 当前模型、迁移和基础测试均满足，视为完成

- **`[high priority]` B2 — Reminder 服务层改造**
  - 当前已实现：
    - `apps/reminder/services.py` 已补齐 Reminder 表基础 service：
      - `build_persisted_reminder_queryset()`
      - `create_reminder()`
      - `process_reminder()`
      - `expire_reminder()`
      - `expire_target_reminders()`
    - `refresh_match_card_next_remind_at()` 已兼容 Reminder 表：
      - 若该配对卡已存在持久化回访类 Reminder，则按 Reminder 表中“未完成记录最早 remind_at”回写
      - 若该配对卡尚无持久化 Reminder，则继续沿用原派生式逻辑
    - `first_meet_overdue` 处理时，已支持自动生成 `scene=unmatched` 的跟进记录，并更新目标用户 `last_action_at / last_unmatched_active_at`
  - 当前口径：
    - 当前 `/reminders/` 列表仍走派生逻辑，不切换到 Reminder 表
    - B2 先提供 Reminder 表的写入 / 查询 / 处理 / 失效基础能力，为 B3 API 接入打底，避免现有提醒列表 `id` 语义突变
  - 测试现状：
    - 已覆盖 Reminder 创建
    - 已覆盖 Reminder 持久化 query 的权限与筛选
    - 已覆盖普通 Reminder 处理
    - 已覆盖 `first_meet_overdue` 处理闭环
    - 已覆盖 Reminder 失效 / 取消
    - 已覆盖 `refresh_match_card_next_remind_at()` 与现有派生逻辑的兼容行为
    - 现有 reminder 派生列表测试继续通过
  - 完成判定：
    - 当前服务层实现和测试均满足，视为完成

- **`[high priority]` B3 — Reminder API 端点**
  - 当前已实现：
    - `GET /reminders/` 已完全切换到 persisted 单轨，基于 `build_persisted_reminder_queryset()`
    - `POST /reminders/{id}/process/` 基于 persisted `Reminder.id` 调用服务层，完整支持权限检查与 `first_meet_overdue` 闭环
    - `POST /reminders/manual/` 已实现，基于 `create_manual_reminder()`，旧提醒自动失效，配对卡 `next_remind_at` 自动刷新
    - 三个端点均已注册到 `urls.py`
    - 派生式 `build_reminder_list()` 已确认无调用方，已于阶段1整理时删除
  - 测试现状：
    - 已覆盖 persisted 列表权限过滤、matchmaker/admin 筛选、类型/状态/时间范围筛选
    - 已覆盖 matched_revisit / success_revisit 出现在 persisted 列表
    - 已覆盖 manual 创建、覆盖旧系统提醒、权限拒绝
    - 已覆盖 process 权限检查、重复处理拒绝、first_meet_overdue 闭环
    - 全量测试 186 条通过
  - 完成判定：
    - API 三端点均完整实现并有测试覆盖，与 `06_api_contract_v1_1_2.md §11` 对齐，视为完成

- **`[normal]` C4 — Reminder 模块测试**
  - 当前已实现：
    - `tests/migrations/test_0004_reminder_core.py`：建表/字段/外键/索引/check constraint
    - `tests/apps/reminder/test_reminder_model_contract.py`：模型默认值与枚举约束
    - `tests/apps/reminder/test_reminder_service.py`：服务层持久化 query / create / process / expire / refresh
    - `tests/apps/reminder/test_reminder_api.py`：GET 列表（12条）、POST manual（2条）、POST process（4条）
    - 合计 reminder 相关测试 30+ 条，全部通过
  - 当前缺口：
    - `tasks.py` 仍是占位，缺 Celery task 单元测试（依赖后续 Celery 基础设施接入）
  - 完成判定：
    - 核心路径已覆盖，仅 Celery task 层待补，视为**接近完成**，不阻塞 B4 推进

- **`[normal]` A6 — 统一 operation_log 字段模型**
  - 当前已实现：
    - `operation_log` 底层 canonical schema 明确保持为 `operator / action / target_type / target_id / before_json / after_json / reason / created_at`
    - 已补齐索引：
      - `target_type + target_id + created_at`
      - `operator_id + created_at`
      - `created_at`
    - 已新增 `apps/oplog/services.py::create_operation_log()` 共享 helper
    - `user / matchcard / success` 现有写日志入口已最小收口到 helper，不再分散直接写 `OperationLog.objects.create()` 
    - `docs/03_database_schema_v1_1_1.md` 与 `docs/06_api_contract_v1_1_2.md` 已按 `before_json / after_json` 口径对齐
  - 当前口径：
    - `field_changed / old_value / new_value` 不再作为底层 schema 字段；如未来需要，只作为展示层派生口径
    - 本次不实现 operation_log API；查询接口仍归 B8
  - 测试现状：
    - 已覆盖 model 字段与索引 contract
    - 已覆盖 migration 后表结构与索引
    - 已覆盖 `create_operation_log()` helper 基本写入
  - 完成判定：
    - 当前模型、迁移、helper、文档和最小测试已形成闭环，视为完成

---

### 未完成

- **`[high priority]` B4 — Recommendation 模型与迁移** ✅
  - 当前已实现：
    - `apps/recommendation/models.py`：`RecommendationBatch` + `RecommendationCandidate` 两张表
    - `apps/recommendation/migrations/0001_initial.py`：建表 + 索引 + check constraint
    - `RecommendationBatch`：`user_id / staff_id / batch_no(unique) / candidate_count / status / created_at / closed_at`；INDEX(user_id, created_at)、INDEX(staff_id)；status check constraint
    - `RecommendationCandidate`：`batch_id / candidate_user_id / is_selected / is_met / result / created_at / updated_at`；INDEX(batch_id)、INDEX(candidate_user_id)；result check constraint
    - `tests/migrations/test_0006_recommendation_core.py`：建表/字段/索引/约束合约测试
    - `tests/apps/recommendation/test_recommendation_model_contract.py`：模型默认值、唯一约束、枚举约束
    - 全量测试 201 条通过
  - 注意：`last_unmatched_active_at` 更新（发起推荐时）属于服务层，在 B5 中实现
  - 完成判定：
    - 模型、迁移、测试均满足，视为完成

- **`[high priority]` B5 — Recommendation 服务与 API**
  - 文件：`apps/recommendation/services.py`、`views.py`、`serializers.py`、`urls.py`
  - 当前实际情况：
    - 相关文件仍为空占位或空路由
  - 完成判定：
    - 推荐批次生命周期（创建→添加候选人→确认）完整可走通，API 契约一致

- **`[high priority]` B6 — Transfer 模型与迁移**
  - 文件：`apps/transfer/models.py`
  - 当前实际情况：
    - 当前为空占位，迁移未落地
  - 完成判定：
    - 创建 `UserTransferRequest` 表并通过迁移

- **`[high priority]` B7 — Transfer 服务与 API**
  - 文件：`apps/transfer/services.py`、`views.py`、`serializers.py`、`urls.py`
  - 当前实际情况：
    - 当前为空占位或空路由
  - 依赖：
    - B6、A3 补齐 owner 变更联动
  - 完成判定：
    - 转移审批通过后 `user.owner_id` 正确变更，操作日志完整

- **`[normal]` B8 — OpLog 序列化与 API**
  - 文件：`apps/oplog/serializers.py`、`apps/oplog/views.py`
  - 当前实际情况：
    - 只有 `OperationLog` 模型，API 仍未实现
  - 完成判定：
    - 可按 `target_type + target_id` 查询操作日志，仅 admin 可访问

- **`[normal]` B9 — Dashboard API**
  - 文件：`apps/dashboard/views.py`、`services.py`
  - 当前实际情况：
    - 当前为空占位或空路由
  - 完成判定：
    - 返回结构与 API 契约一致，matchmaker 仅看到自己数据

- **`[normal]` B10 — Search API**
  - 文件：`apps/search/views.py`、`services.py`
  - 当前实际情况：
    - 当前为空占位或空路由
  - 完成判定：
    - 搜索结果包含用户基础信息 + 所属红娘，权限过滤正确

- **`[high priority]` C2 — Recommendation 模块测试**
  - 文件：`tests/test_recommendation.py`
  - 当前实际情况：
    - 模块本体尚未落地，对应测试未开始
  - 完成判定：
    - 推荐模块核心路径 ≥10 条测试，覆盖权限边界

- **`[high priority]` C3 — Transfer 模块测试**
  - 文件：`tests/test_transfer.py`
  - 当前实际情况：
    - 模块本体尚未落地，对应测试未开始
  - 完成判定：
    - 转移模块核心路径 ≥8 条测试

- **`[normal]` C5 — 文档对齐收尾**
  - 文件：`docs/03_database_schema_v1_1_1.md`、`docs/06_api_contract_v1_1_2.md`
  - 当前实际情况：
    - A3/A6/Reminder 等文档与代码仍存在偏差
  - 完成判定：
    - 文档中所有表/字段/API 定义与最新代码一致，无遗留 TODO 标记

---

### 当前最建议的执行顺序

| 顺序 | 任务 | 原因 / 前置 |
|------|------|-------------|
| 1 | ~~B3~~ ✅ | 已完成，三端点均落地并有测试 |
| 2 | B4 ✅ | Recommendation 模型与迁移已落地（本轮完成） |
| 3 | B5 | Recommendation 服务与 API，含 last_unmatched_active_at 联动 |
| 4 | B6 | Transfer 模型与迁移 |
| 5 | B7 | Transfer 服务与 API |
| 6 | B8, B9, B10 | 收尾型接口，优先级低于核心业务链路 |
| 7 | C2, C3, ~~C4~~, C5 | 模块完成后集中补测试与文档对齐；C4 核心已完成 |

---

### 后续清理项

- **`[normal]` 清理 last_unmatched_active_at 的 NULL baseline 历史/绕过链路问题**
  - 当前情况：
    - 通过正常用户创建链路，`last_unmatched_active_at` 已初始化为 `created_at`
    - 但历史旧数据，以及测试工厂或未来绕过 service 直接 `CustomerProfile.objects.create()` 的路径，仍可能留下 `last_unmatched_active_at = NULL`
  - 为什么现在不阻塞提交：
    - A2 当前验收范围仅要求补齐正常创建链路初始化，现有状态流转、pause/resume、未配对跟进、配对结束回流逻辑均未被破坏
    - 当前仓库尚未落地基于该字段的完整 reminder 持久化与超时计算闭环，因此该问题属于后续数据治理与兜底完善项
  - 后续建议动作：
    - 增加一次性数据修复脚本或 migration backfill，将历史 `NULL` baseline 回填为合适基准
    - 为后续依赖该字段的提醒、超时判断、未配对池停留时长计算增加 `NULL` 兜底策略
    - 统一测试工厂与创建辅助方法，避免继续直接造出 `NULL` baseline
