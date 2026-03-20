# AI红娘配对跟进管理系统 数据库设计文档 v1.1.1

## 1. 文档信息

- 文档名称：数据库设计文档
- 版本：v1.1.1
- 依赖文档：MVP PRD v1.3、业务流程与状态流转文档 v1.1.1
- 技术选型：PostgreSQL（推荐）/ MySQL 8.0+
- 字符集：UTF-8（utf8mb4）
- 时区：所有时间字段统一存储 UTC，展示层转换为本地时间

---

## 2. 设计原则

1. **主键**：所有表使用自增 BIGINT 主键（id），不使用 UUID（MVP阶段优先简单）
2. **软删除**：核心业务表使用 deleted_at 字段做软删除，不物理删除
3. **审计字段**：所有表包含 created_at、updated_at
4. **枚举值**：状态类字段使用 VARCHAR 存储可读字符串，不用数字编码（提高可读性，MVP阶段不追求极致性能）
5. **外键**：逻辑外键，不建物理外键约束（应用层保证一致性，降低迁移复杂度）
6. **索引**：只建高频查询必需的索引，上线后根据慢查询再补

---

## 3. 实体关系总览

```
staff（红娘/管理员）
  │
  ├── 1:N ──▶ user（用户档案）       ← staff.id = user.owner_id
  │            │
  │            ├── 1:N ──▶ follow_up_record（跟进记录）
  │            ├── 1:N ──▶ recommendation_batch（推荐批次）
  │            ├── 1:N ──▶ user_status_history（状态历史）
  │            ├── 1:N ──▶ user_transfer_request（转移申请）
  │            └── 1:N ──▶ reminder（提醒记录）
  │
  ├── 1:N ──▶ match_card（配对卡）    ← 男方红娘/女方红娘/主操作红娘
  │            │
  │            ├── 1:N ──▶ follow_up_record（已配对跟进）
  │            ├── 1:N ──▶ success_application（成功申请）
  │            └── 1:N ──▶ reminder（提醒记录）
  │
  recommendation_batch（推荐批次）
  │
  └── 1:N ──▶ recommendation_candidate（推荐候选明细）

  success_application（成功申请）
  │
  └── 1:1 ──▶ success_case（成功案例）

  独立配置表：
  ├── reason_enum（原因枚举配置）
  ├── payment_level（付费等级规则）
  └── operation_log（操作日志）
```

---

## 4. 表结构定义

### 4.1 staff（红娘/管理员）

系统操作人员表，包括一线红娘和门店管理员。

| 字段名 | 类型 | 是否必填 | 默认值 | 说明 |
|--------|------|---------|--------|------|
| id | BIGINT | 是 | 自增 | 主键 |
| name | VARCHAR(50) | 是 | — | 姓名 |
| phone | VARCHAR(20) | 是 | — | 手机号（登录账号） |
| role | VARCHAR(20) | 是 | — | 角色：matchmaker / admin |
| status | VARCHAR(20) | 是 | active | 状态：active / disabled |
| wechat_id | VARCHAR(100) | 否 | NULL | 微信ID（用于提醒推送） |
| created_at | TIMESTAMP | 是 | CURRENT_TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 是 | CURRENT_TIMESTAMP | 更新时间 |
| deleted_at | TIMESTAMP | 否 | NULL | 软删除时间 |

**索引：**
- UNIQUE(phone) — 手机号唯一
- INDEX(role) — 按角色筛选

---

### 4.2 user（用户档案）

红娘服务的客户档案，即到店付费的单身用户。

| 字段名 | 类型 | 是否必填 | 默认值 | 说明 |
|--------|------|---------|--------|------|
| id | BIGINT | 是 | 自增 | 主键 |
| name | VARCHAR(50) | 是 | — | 姓名/昵称 |
| gender | VARCHAR(10) | 是 | — | 性别：male / female |
| age | INT | 是 | — | 年龄 |
| phone | VARCHAR(20) | 否 | NULL | 手机号 |
| wechat | VARCHAR(100) | 否 | NULL | 微信号 |
| other_contact | VARCHAR(200) | 否 | NULL | 其他联系方式 |
| city | VARCHAR(50) | 是 | — | 城市 |
| payment_level_id | BIGINT | 是 | — | 付费等级（关联 payment_level.id） |
| owner_id | BIGINT | 是 | — | 负责红娘（关联 staff.id） |
| basic_requirement | TEXT | 是 | — | 基本择偶要求 |
| pool_status | VARCHAR(30) | 是 | new_pending | 未配对池主状态（见枚举 4.2.1） |
| pre_pause_status | VARCHAR(30) | 否 | NULL | 暂停前的状态（暂停解除时恢复用） |
| is_profile_complete | BOOLEAN | 是 | FALSE | 资料是否完整 |
| is_in_match | BOOLEAN | 是 | FALSE | 是否存在进行中的配对卡；仅当存在 match_card.stage IN ('initial_contact', 'stable_contact', 'success_pending_review') 时为 TRUE，stage='success' 或 'ended' 时为 FALSE |
| paid_at | TIMESTAMP | 否 | NULL | 付费时间（T+N 的起算点）；创建用户时可为空，后续确认付费完成时写入，一旦写入即作为未首见提醒计算基准 |
| paused_at | TIMESTAMP | 否 | NULL | 最近一次进入 paused 状态的时间；暂停时写入，恢复时清空；用于 pause_revisit 提醒基准时间 |
| last_action_at | TIMESTAMP | 否 | NULL | 最近有效动作时间（管理员用）；以下动作发生时更新：新建未配对跟进、发起推荐、用户状态变更、创建配对卡、更新配对卡关键字段、处理提醒、转移负责人。处理提醒时：target_type='user' 更新该用户；target_type='match_card' 更新双方用户 |
| last_unmatched_active_at | TIMESTAMP | 否 | NULL | 未配对阶段最近有效动作时间，用于跟进超时计算；创建用户时自动设为 created_at，配对结束回流时重置为回流时间 |
| profile_detail | JSON | 否 | NULL | 完整资料卡（结构化扩展字段） |
| emotional_history | JSON | 否 | NULL | 情感经历摘要（配对卡结束时系统写入） |
| tags | JSON | 否 | NULL | 辅助标签数组，如 ["待重新推荐","未首见超时"] |
| created_at | TIMESTAMP | 是 | CURRENT_TIMESTAMP | 入库时间（系统自动生成） |
| updated_at | TIMESTAMP | 是 | CURRENT_TIMESTAMP | 更新时间 |
| deleted_at | TIMESTAMP | 否 | NULL | 软删除时间 |

**枚举 4.2.1 pool_status 取值：**

| 值 | 含义 |
|----|------|
| new_pending | 新入库待处理 |
| communicated_pending_recommend | 已沟通待推荐 |
| recommended_pending_select | 已推荐待选择 |
| selected_pending_meet | 已选人待见面 |
| met_not_continue | 已见面未继续 |
| paused | 暂停中 |

**索引：**
- INDEX(owner_id) — 红娘查自己的用户
- INDEX(pool_status) — 按状态筛选
- INDEX(payment_level_id) — 按付费等级筛选
- INDEX(is_in_match) — 区分未配对/已配对
- INDEX(city) — 按城市筛选
- INDEX(created_at) — 按入库时间排序
- INDEX(paid_at) — 未首见时效计算
- INDEX(last_unmatched_active_at) — 未配对跟进超时扫描
- FULLTEXT(name, phone, wechat) — 全局搜索（若数据库支持）

---

### 4.3 user_status_history（用户状态变更历史）

记录用户每次状态变更，用于追溯和审计。

| 字段名 | 类型 | 是否必填 | 默认值 | 说明 |
|--------|------|---------|--------|------|
| id | BIGINT | 是 | 自增 | 主键 |
| user_id | BIGINT | 是 | — | 关联 user.id |
| from_status | VARCHAR(30) | 否 | NULL | 变更前状态（首次创建时为 NULL） |
| to_status | VARCHAR(30) | 是 | — | 变更后状态 |
| changed_by | BIGINT | 是 | — | 操作人（关联 staff.id，系统自动变更时记为触发者） |
| reason | VARCHAR(500) | 否 | NULL | 变更原因 |
| reason_id | BIGINT | 否 | NULL | 结构化原因 ID（关联 reason_enum.id）；暂停、恢复、管理员 force 状态类操作优先写入此字段 |
| reason_note | VARCHAR(255) | 否 | NULL | 原因补充说明；暂停备注、force_reason 等写入此字段 |
| created_at | TIMESTAMP | 是 | CURRENT_TIMESTAMP | 变更时间 |

**索引：**
- INDEX(user_id, created_at) — 查某用户的状态历史

---

### 4.4 follow_up_record（跟进记录）

统一覆盖未配对跟进、已配对回访、成功后回访，通过 scene 字段区分。

| 字段名 | 类型 | 是否必填 | 默认值 | 说明 |
|--------|------|---------|--------|------|
| id | BIGINT | 是 | 自增 | 主键 |
| scene | VARCHAR(20) | 是 | — | 跟进场景：unmatched / matched / success_followup |
| user_id | BIGINT | 否 | NULL | 未配对跟进时关联 user.id；matched 场景下也必填，用于标识本次回访归属男方还是女方 |
| match_card_id | BIGINT | 否 | NULL | 已配对/成功后跟进时关联 match_card.id |
| staff_id | BIGINT | 是 | — | 跟进红娘（关联 staff.id） |
| content | TEXT | 是 | — | 跟进内容 |
| next_remind_mode | VARCHAR(10) | 否 | NULL | 提醒方式：manual / default / NULL（unmatched 场景可为空） |
| next_remind_at | TIMESTAMP | 否 | NULL | 下次提醒时间 |
| is_still_contact | VARCHAR(10) | 否 | NULL | matched 场景语义为“是否仍联系”；success_followup 场景语义为“是否仍在一起”：yes / no / unknown |
| risk_status | VARCHAR(20) | 否 | NULL | matched 场景风险情况：none / watching / high_risk |
| failure_reason_id | BIGINT | 否 | NULL | 失败原因（关联 reason_enum.id，category='meet_failure'）。仅当 scene='unmatched' 且用户从 met_not_continue 退出时必填 |
| overdue_reason_id | BIGINT | 否 | NULL | 超时原因（关联 reason_enum.id，category='overdue'）；仅处理 first_meet_overdue 提醒时使用 |
| overdue_reason_note | VARCHAR(255) | 否 | NULL | 超时原因补充说明；仅处理 first_meet_overdue 提醒时使用 |
| created_at | TIMESTAMP | 是 | CURRENT_TIMESTAMP | 跟进时间 |

**校验规则（应用层）：**
- 当 scene = 'unmatched' 时：
  - user_id 必填，match_card_id 为 NULL
  - next_remind_mode 可为空；若传值则仅允许 manual
  - 当用于 met_not_continue 退出时，failure_reason_id 必填
  - 当用于处理 first_meet_overdue 提醒时，overdue_reason_id 必填，overdue_reason_note 选填
- 当 scene = 'matched' 时：
  - match_card_id 必填
  - user_id 必填，用于区分男方侧/女方侧
  - is_still_contact、risk_status、next_remind_mode 必填
  - next_remind_mode = 'manual' 时 next_remind_at 必填
  - next_remind_mode = 'default' 时 next_remind_at 必须为空或不传
  - 满足以上条件即构成单方有效回访
- 当 scene = 'success_followup' 时：
  - match_card_id 必填，且关联配对卡 stage = 'success'
  - content、is_still_contact、next_remind_mode 必填
  - risk_status 不要求
  - next_remind_mode = 'manual' 时 next_remind_at 必填
  - next_remind_mode = 'default' 时 next_remind_at 必须为空或不传

**索引：**
- INDEX(user_id, created_at) — 查某用户的跟进历史
- INDEX(match_card_id, created_at) — 查某配对卡的回访历史
- INDEX(staff_id) — 查某红娘的跟进记录

---

### 4.5 recommendation_batch（推荐批次）

一轮推荐的批次记录。

| 字段名 | 类型 | 是否必填 | 默认值 | 说明 |
|--------|------|---------|--------|------|
| id | BIGINT | 是 | 自增 | 主键 |
| user_id | BIGINT | 是 | — | 被推荐的用户（关联 user.id） |
| staff_id | BIGINT | 是 | — | 发起红娘（关联 staff.id） |
| batch_no | VARCHAR(50) | 是 | — | 批次编号（系统自动生成） |
| candidate_count | INT | 是 | — | 当轮候选数量 |
| status | VARCHAR(20) | 是 | open | 批次状态：open / closed |
| created_at | TIMESTAMP | 是 | CURRENT_TIMESTAMP | 推荐时间 |
| closed_at | TIMESTAMP | 否 | NULL | 批次关闭时间 |

**索引：**
- INDEX(user_id, created_at) — 查某用户的推荐历史
- INDEX(staff_id) — 查某红娘发起的推荐

---

### 4.6 recommendation_candidate（推荐候选明细）

每轮推荐中的每一个候选人记录。

| 字段名 | 类型 | 是否必填 | 默认值 | 说明 |
|--------|------|---------|--------|------|
| id | BIGINT | 是 | 自增 | 主键 |
| batch_id | BIGINT | 是 | — | 所属批次（关联 recommendation_batch.id） |
| candidate_user_id | BIGINT | 是 | — | 候选用户（关联 user.id） |
| is_selected | BOOLEAN | 是 | FALSE | 是否被选中 |
| is_met | BOOLEAN | 是 | FALSE | 是否见面 |
| result | VARCHAR(20) | 否 | NULL | 最终结果：continue / not_continue / pending |
| created_at | TIMESTAMP | 是 | CURRENT_TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 是 | CURRENT_TIMESTAMP | 更新时间 |

**索引：**
- INDEX(batch_id) — 查某批次的所有候选人
- INDEX(candidate_user_id) — 查某用户被推荐的历史（用于重复推荐检测）

---

### 4.7 match_card（配对卡）

已配对关系的核心记录。

| 字段名 | 类型 | 是否必填 | 默认值 | 说明 |
|--------|------|---------|--------|------|
| id | BIGINT | 是 | 自增 | 主键 |
| male_user_id | BIGINT | 是 | — | 男方用户（关联 user.id） |
| female_user_id | BIGINT | 是 | — | 女方用户（关联 user.id） |
| male_staff_id | BIGINT | 是 | — | 男方红娘（关联 staff.id） |
| female_staff_id | BIGINT | 是 | — | 女方红娘（关联 staff.id） |
| primary_staff_id | BIGINT | 是 | — | 主操作红娘（关联 staff.id） |
| stage | VARCHAR(30) | 是 | initial_contact | 当前主阶段（见枚举 4.7.1） |
| risk_level | VARCHAR(20) | 是 | none | 风险等级：none / watching / high_risk |
| risk_reason_id | BIGINT | 否 | NULL | 风险原因（关联 reason_enum.id） |
| risk_reason_note | VARCHAR(500) | 否 | NULL | 风险原因补充说明 |
| male_feedback | TEXT | 否 | NULL | 男方反馈 |
| female_feedback | TEXT | 否 | NULL | 女方反馈 |
| male_heat | INT | 否 | NULL | 男方热度（1-10 或其他刻度，先预留） |
| female_heat | INT | 否 | NULL | 女方热度 |
| staff_judgment | TEXT | 否 | NULL | 红娘综合判断 |
| last_visit_at | TIMESTAMP | 否 | NULL | 最近回访时间；取双方最近一次任一单方有效回访 created_at 的最大值 |
| next_remind_at | TIMESTAMP | 否 | NULL | 下次提醒时间；取该配对卡当前所有未完成回访提醒中最早到期 remind_at 的最小值 |
| end_reason_male | VARCHAR(500) | 否 | NULL | 结束原因（男方） |
| end_reason_female | VARCHAR(500) | 否 | NULL | 结束原因（女方） |
| end_reason_staff | VARCHAR(500) | 否 | NULL | 结束原因（红娘总结） |
| ended_at | TIMESTAMP | 否 | NULL | 结束时间 |
| created_at | TIMESTAMP | 是 | CURRENT_TIMESTAMP | 建立时间 |
| updated_at | TIMESTAMP | 是 | CURRENT_TIMESTAMP | 更新时间 |

**枚举 4.7.1 stage 取值：**

| 值 | 含义 |
|----|------|
| initial_contact | 初期接触 |
| stable_contact | 稳定联系 |
| success_pending_review | 成功待审核 |
| success | 成功 |
| ended | 结束 |

**索引：**
- INDEX(male_user_id) — 查某用户（男方）的配对卡
- INDEX(female_user_id) — 查某用户（女方）的配对卡
- INDEX(male_staff_id) — 男方红娘筛选
- INDEX(female_staff_id) — 女方红娘筛选
- INDEX(primary_staff_id) — 主操作红娘筛选
- INDEX(stage) — 按阶段筛选
- INDEX(risk_level) — 按风险筛选
- INDEX(next_remind_at) — 提醒调度用

---

### 4.8 success_application（成功案例申请）

红娘发起的成功案例审批记录。

| 字段名 | 类型 | 是否必填 | 默认值 | 说明 |
|--------|------|---------|--------|------|
| id | BIGINT | 是 | 自增 | 主键 |
| match_card_id | BIGINT | 是 | — | 关联 match_card.id |
| applicant_id | BIGINT | 是 | — | 申请人/红娘（关联 staff.id） |
| apply_note | TEXT | 否 | NULL | 申请说明 |
| status | VARCHAR(20) | 是 | pending | 审批状态：pending / approved / rejected |
| reviewer_id | BIGINT | 否 | NULL | 审批人/管理员（关联 staff.id） |
| review_note | VARCHAR(500) | 否 | NULL | 审批意见（驳回时必填） |
| reviewed_at | TIMESTAMP | 否 | NULL | 审批时间 |
| created_at | TIMESTAMP | 是 | CURRENT_TIMESTAMP | 申请时间 |

**索引：**
- INDEX(match_card_id) — 查某配对卡的申请历史
- INDEX(status) — 筛选待审批

---

### 4.9 success_case（成功案例）

审批通过后生成的成功案例正式记录。

| 字段名 | 类型 | 是否必填 | 默认值 | 说明 |
|--------|------|---------|--------|------|
| id | BIGINT | 是 | 自增 | 主键 |
| match_card_id | BIGINT | 是 | — | 关联 match_card.id |
| application_id | BIGINT | 是 | — | 关联 success_application.id |
| status | VARCHAR(20) | 是 | active | 案例状态：active / invalidated |
| invalidated_reason_id | BIGINT | 否 | NULL | 失效原因（关联 reason_enum.id） |
| invalidated_reason_note | VARCHAR(500) | 否 | NULL | 失效原因补充 |
| invalidated_at | TIMESTAMP | 否 | NULL | 失效时间 |
| approved_at | TIMESTAMP | 是 | — | 审核通过时间（成功后回访的 T0） |
| created_at | TIMESTAMP | 是 | CURRENT_TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 是 | CURRENT_TIMESTAMP | 更新时间 |

**索引：**
- UNIQUE(match_card_id, status) — 一张配对卡同一状态下只有一条（逻辑约束，应用层保证）
- INDEX(status) — 按状态筛选
- INDEX(approved_at) — 按审核通过时间查

---

### 4.10 user_transfer_request（用户转移申请）

| 字段名 | 类型 | 是否必填 | 默认值 | 说明 |
|--------|------|---------|--------|------|
| id | BIGINT | 是 | 自增 | 主键 |
| user_id | BIGINT | 是 | — | 被转移用户（关联 user.id） |
| from_staff_id | BIGINT | 是 | — | 原负责人（关联 staff.id） |
| to_staff_id | BIGINT | 是 | — | 新负责人（关联 staff.id） |
| reason | VARCHAR(500) | 是 | — | 转移原因 |
| status | VARCHAR(20) | 是 | pending | 审批状态：pending / approved / rejected |
| reviewer_id | BIGINT | 否 | NULL | 审批人（关联 staff.id） |
| review_note | VARCHAR(500) | 否 | NULL | 审批意见 |
| reviewed_at | TIMESTAMP | 否 | NULL | 审批时间 |
| created_at | TIMESTAMP | 是 | CURRENT_TIMESTAMP | 申请时间 |

**索引：**
- INDEX(user_id) — 查某用户的转移历史
- INDEX(status) — 筛选待审批
- INDEX(from_staff_id) — 查某红娘发起的转移

---

### 4.11 reminder（提醒记录）

| 字段名 | 类型 | 是否必填 | 默认值 | 说明 |
|--------|------|---------|--------|------|
| id | BIGINT | 是 | 自增 | 主键 |
| target_type | VARCHAR(20) | 是 | — | 提醒对象类型：user / match_card |
| target_id | BIGINT | 是 | — | 对象 ID（user.id 或 match_card.id） |
| staff_id | BIGINT | 是 | — | 提醒接收人（关联 staff.id） |
| remind_type | VARCHAR(30) | 是 | — | 提醒类型（见枚举 4.11.1） |
| remind_at | TIMESTAMP | 是 | — | 提醒时间 |
| status | VARCHAR(20) | 是 | pending | 提醒状态：pending / sent / processed / expired |
| processed_at | TIMESTAMP | 否 | NULL | 处理时间 |
| is_manual | BOOLEAN | 是 | FALSE | 是否手动设置（手动只覆盖本次） |
| created_at | TIMESTAMP | 是 | CURRENT_TIMESTAMP | 创建时间 |

**枚举 4.11.1 remind_type 取值：**

| 值 | 含义 | 适用阶段 |
|----|------|---------|
| normal | 普通提醒 | 未配对 T+1 |
| first_meet_pending | 未首见待推进 | 未配对 T+2 |
| first_meet_delayed | 未首见延迟 | 未配对 T+3 |
| first_meet_warning | 未首见警告 | 未配对 T+4 |
| first_meet_overdue | 未首见超时 | 未配对 T+5 |
| followup_timeout | 跟进超时 | 未配对 |
| pause_revisit | 暂停回访 | 未配对暂停 |
| matched_revisit | 已配对回访 | 已配对 |
| success_revisit | 成功后回访 | 成功案例 |
| urgent | 紧急提醒 | 通用 |
| manual | 手动提醒 | 通用 |

**索引：**
- INDEX(staff_id, status, remind_at) — 红娘查自己的待处理提醒
- INDEX(target_type, target_id) — 查某用户/配对卡的提醒
- INDEX(remind_at, status) — 提醒调度定时任务用

---

### 4.12 operation_log（操作日志）

不可变记录，只允许插入，不允许更新和删除。

| 字段名 | 类型 | 是否必填 | 默认值 | 说明 |
|--------|------|---------|--------|------|
| id | BIGINT | 是 | 自增 | 主键 |
| operator_id | BIGINT | 是 | — | 操作人（关联 staff.id） |
| target_type | VARCHAR(30) | 是 | — | 操作对象类型：user / match_card / success_case / transfer 等 |
| target_id | BIGINT | 是 | — | 对象 ID |
| action | VARCHAR(50) | 是 | — | 操作类型（见枚举 4.12.1） |
| before_json | JSON | 否 | NULL | 结构化变更前快照 |
| after_json | JSON | 否 | NULL | 结构化变更后快照 |
| reason | VARCHAR(500) | 否 | NULL | 变更原因 |
| created_at | TIMESTAMP | 是 | CURRENT_TIMESTAMP | 操作时间 |

**枚举 4.12.1 action 取值（非穷举，可扩展）：**

| 值 | 含义 |
|----|------|
| user_created | 用户创建 |
| user_status_changed | 用户状态变更 |
| user_profile_updated | 用户资料修改 |
| user_paused | 用户暂停 |
| user_resumed | 用户恢复 |
| user_owner_changed | 用户负责人变更 |
| recommendation_created | 推荐批次创建 |
| candidate_selected | 候选人标记选中 |
| match_card_created | 配对卡创建 |
| match_card_stage_changed | 配对卡阶段变更 |
| match_card_risk_changed | 配对卡风险变更 |
| match_card_ended | 配对卡结束 |
| follow_up_created | 跟进记录创建 |
| success_applied | 成功申请发起 |
| success_approved | 成功申请审核通过 |
| success_rejected | 成功申请审核驳回 |
| success_invalidated | 成功案例标记失效 |
| transfer_applied | 转移申请发起 |
| transfer_approved | 转移申请审核通过 |
| transfer_rejected | 转移申请审核驳回 |
| reminder_set | 提醒设置/变更 |
| admin_force_change | 管理员强制修改 |

**索引：**
- INDEX(target_type, target_id, created_at) — 查某对象的操作历史
- INDEX(operator_id, created_at) — 查某操作人的日志
- INDEX(created_at) — 按时间范围查日志

**展示层说明：**
- `field_changed / old_value / new_value` 不再作为底层 schema 字段
- 若后续需要单字段变更展示，可由 `before_json / after_json` 在应用层或展示层派生

**特殊约束：**
- 此表不允许 UPDATE 和 DELETE 操作
- 应用层应确保写入后不可修改
- 建议数据库层面设置只读触发器或权限控制

---

### 4.13 reason_enum（原因枚举配置）

管理员可维护的结构化原因库。

| 字段名 | 类型 | 是否必填 | 默认值 | 说明 |
|--------|------|---------|--------|------|
| id | BIGINT | 是 | 自增 | 主键 |
| category | VARCHAR(30) | 是 | — | 原因分类（见枚举 4.13.1） |
| label | VARCHAR(100) | 是 | — | 原因显示文本 |
| sort_order | INT | 是 | 0 | 排序权重 |
| is_active | BOOLEAN | 是 | TRUE | 是否启用 |
| created_at | TIMESTAMP | 是 | CURRENT_TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 是 | CURRENT_TIMESTAMP | 更新时间 |

**枚举 4.13.1 category 取值：**

| 值 | 含义 |
|----|------|
| pause | 暂停原因 |
| meet_failure | 失败原因（见面不继续） |
| overdue | 超时原因 |
| risk | 风险原因 |
| transfer | 转移原因 |
| success_invalidate | 成功失效原因 |
| match_end | 配对结束原因 |

**索引：**
- INDEX(category, is_active, sort_order) — 按分类获取启用的原因列表

---

### 4.14 payment_level（付费等级规则）

| 字段名 | 类型 | 是否必填 | 默认值 | 说明 |
|--------|------|---------|--------|------|
| id | BIGINT | 是 | 自增 | 主键 |
| name | VARCHAR(50) | 是 | — | 等级名称 |
| sort_order | INT | 是 | 0 | 显示顺序 |
| is_active | BOOLEAN | 是 | TRUE | 是否启用 |
| homepage_weight | INT | 是 | 0 | 首页排序权重（数值越大越靠前） |
| recommend_limit | INT | 是 | — | 推荐候选上限（每轮最多推荐几人） |
| pause_revisit_days | INT | 是 | 30 | 暂停状态下回访间隔（天） |
| followup_timeout_days | INT | 是 | 7 | 未配对跟进超时天数（超过此天数未跟进则生成提醒） |
| note | VARCHAR(500) | 否 | NULL | 备注 |
| created_at | TIMESTAMP | 是 | CURRENT_TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 是 | CURRENT_TIMESTAMP | 更新时间 |

**索引：**
- INDEX(is_active, sort_order) — 获取启用的等级列表

---

## 5. 数据库初始化数据

### 5.1 默认原因枚举

系统初始化时，按 PRD 定义预插入以下原因：

**暂停原因（pause）：** 忙工作、忙考试、情绪问题、家庭因素、对平台不满、暂时不想见、其他

**失败原因（meet_failure）：** 第一版由门店自行维护，初始可为空

**超时原因（overdue）：** 用户拖延、对方拖延、库存不足、排期冲突、资料未补全、红娘未推进、其他

**风险原因（risk）：** 一方降温、异地、家庭阻力、节奏不一致、失联、现实条件冲突、沟通冲突、其他

**转移原因（transfer）：** 第一版由门店自行维护，初始可为空

**成功失效原因（success_invalidate）：** 第一版由门店自行维护，初始可为空

**配对结束原因（match_end）：** 第一版由门店自行维护，初始可为空

### 5.2 默认管理员账号

系统初始化时创建一个默认管理员账号，门店首次登录后修改密码。

---

## 6. 关键查询场景与索引说明

| 查询场景 | 涉及表 | 使用索引 |
|---------|-------|---------|
| 红娘查自己负责的未配对用户 | user | owner_id + is_in_match + pool_status |
| 红娘首页：未配对超时列表 | user + reminder | user.paid_at + reminder.status |
| 红娘首页：已配对待回访 | match_card + reminder | match_card.next_remind_at + stage |
| 已配对池按风险筛选 | match_card | risk_level + stage |
| 全局搜索 | user | name / phone / wechat 全文索引 |
| 管理员查超时总览 | user | pool_status + paid_at + last_action_at |
| 管理员查操作日志 | operation_log | target_type + target_id + created_at |
| 提醒调度（定时任务） | reminder | remind_at + status |
| 重复推荐检测 | recommendation_candidate | candidate_user_id + batch_id → 关联 batch.user_id |

---

## 7. 数据完整性约束汇总

| 约束 | 实现层 | 说明 |
|------|-------|------|
| 用户同一时间只能有一张进行中配对卡 | 应用层 | 创建配对卡时校验 is_in_match = FALSE；is_in_match 仅对应 stage IN ('initial_contact', 'stable_contact', 'success_pending_review') |
| 暂停用户不可被推荐为候选人 | 应用层 | 推荐候选搜索时过滤 pool_status ≠ paused |
| 已见面未继续必须填写失败原因才能退出 | 应用层 | 状态从 met_not_continue 流转时校验 |
| first_meet_overdue 处理时必须写超时原因 | 应用层 | 处理 first_meet_overdue 提醒时，必须落一条包含 overdue_reason_id 的 follow_up_record |
| 已配对跟进必须填写四个附加字段才算有效 | 应用层 | 保存跟进记录时校验 |
| 操作日志不可修改 | 数据库层 + 应用层 | 建议数据库权限限制 UPDATE/DELETE |
| 风险标记为关注中/高风险时必填原因 | 应用层 | 配对卡风险变更时校验 |
| 配对卡结束时红娘总结原因必填 | 应用层 | 结束操作提交时校验 |
| 转移审批通过后自动更新配对卡红娘字段 | 应用层 | 审批通过后级联更新 |
| 成功申请只能从"稳定联系"阶段发起 | 应用层 | 发起时校验 stage = stable_contact |

---

## 8. 版本记录

| 版本 | 日期 | 修改内容 |
|-----|------|---------|
| v1.1.1 | 2026-03-14 | 新增 follow_up_record.overdue_reason_id / overdue_reason_note、user_status_history.reason_id / reason_note，并统一 paid_at、last_action_at、is_in_match、match_card 回访字段语义 |
| v1.0 | — | 初始版本，14张表，覆盖全部 MVP 数据实体 |
