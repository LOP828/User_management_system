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
    - 当前全量测试 `158` 条通过
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

---

### 部分完成

- **`[high priority]` B2 — Reminder 服务层改造**
  - 当前已实现：
    - `Reminder` 模型与迁移已落地
    - `apps/reminder/services.py` 已有派生式 reminder 计算逻辑
    - 已实现 `refresh_match_card_next_remind_at()`，会回写 `match_card.next_remind_at`
    - 已有针对已配对回访提醒的权限过滤和时间过滤逻辑
  - 当前缺口：
    - Reminder 表尚未接入现有服务层读写
    - 仍缺创建 / 完成 / 取消 Reminder 的 service 函数
    - 当前 reminder 仍是“按配对卡和跟进记录即时派生”，不是文档要求的持久化模型
  - 完成判定：
    - 补齐 Reminder 表写入、状态流转、覆盖/过期逻辑后完成

- **`[high priority]` B3 — Reminder API 端点**
  - 当前已实现：
    - Reminder 表已存在
    - `GET /reminders/` 已存在
    - 当前接口可按权限返回派生式 reminder 列表，并支持部分筛选
  - 当前缺口：
    - `POST /reminders/{id}/complete/` 未实现
    - 当前 API 仍未基于 `Reminder` 表提供持久化数据
    - 与 `06_api_contract_v1_1_2.md` 中完整 reminder 生命周期仍不一致
  - 完成判定：
    - 依赖 B2；补齐 complete 接口和模型化数据后完成

- **`[normal]` C4 — Reminder 模块测试**
  - 当前已实现：
    - 已有 Reminder migration / model schema 基础测试
    - 已有 reminder 列表相关测试
    - 已覆盖派生 reminder 的权限过滤、逾期展示、manual follow-up 影响、筛选行为
  - 当前缺口：
    - 仍无 Reminder 服务层持久化读写测试
    - 仍无 `complete` API 测试
    - `tasks.py` 仍是占位，缺 Celery task 单元测试
  - 完成判定：
    - 依赖 B2、B3；补齐 reminder 持久化和 API 后扩展测试

---

### 未完成

- **`[normal]` A6 — 统一 operation_log 字段模型**
  - 文件：`apps/oplog/models.py`、`docs/03_database_schema_v1_1_1.md`
  - 当前实际情况：
    - 代码实现为 `before_json / after_json`
    - 文档仍定义为 `field_changed / old_value / new_value`
    - 当前缺少 `operator_id + created_at` 联合索引
  - 完成判定：
    - 文档与代码字段命名统一，并补齐索引说明/迁移

- **`[high priority]` B4 — Recommendation 模型与迁移**
  - 文件：`apps/recommendation/models.py`
  - 当前实际情况：
    - 当前为空占位，迁移未落地
  - 完成判定：
    - 创建 `RecommendationBatch` + `RecommendationCandidate` 两张表并通过迁移

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
| 1 | A6 | 统一 operation_log 口径，减少后续文档/实现偏差 |
| 2 | B2, B3 | 在现有派生 reminder 基础上补成完整模型和 API |
| 3 | B4, B6 | Recommendation / Transfer 先补模型 |
| 4 | B5, B7 | Recommendation / Transfer 再补服务和 API |
| 5 | B8, B9, B10 | 收尾型接口，优先级低于核心业务链路 |
| 6 | C2, C3, C4, C5 | 模块完成后集中补测试与文档对齐 |

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
