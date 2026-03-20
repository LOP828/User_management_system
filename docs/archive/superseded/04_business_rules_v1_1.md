# AI红娘配对跟进管理系统 业务规则文档 v1.1

## 1. 文档信息

- 文档名称：业务规则文档
- 版本：v1.1
- 依赖文档：MVP PRD v1.3、业务流程文档 v1.1、数据库设计文档 v1.1
- 文档用途：将散落在 PRD 和流程文档中的所有校验规则、计算逻辑、判定条件集中为一份文档。开发写 if/else 的唯一依据。

---

## 2. 规则编号体系

每条规则使用固定编号，格式为：`BR-{模块}-{序号}`

| 模块代码 | 模块名称 |
|---------|---------|
| USER | 用户档案 |
| POOL | 未配对池 |
| REC | 推荐 |
| MATCH | 配对卡 |
| FU | 跟进记录 |
| REMIND | 提醒 |
| SUCCESS | 成功案例 |
| TRANSFER | 用户转移 |
| SORT | 排序 |
| PERM | 权限 |

---

## 3. 用户档案规则（BR-USER）

### BR-USER-001：最小建档校验

**触发时机：** 用户创建表单提交时

**校验规则：** 以下字段全部非空才允许保存：
- 姓名/昵称（name）：非空，长度 ≤ 50
- 性别（gender）：必须为 male 或 female
- 年龄（age）：正整数，范围 18-100
- 联系方式：phone、wechat、other_contact 至少填写一项
- 城市（city）：非空
- 付费等级（payment_level_id）：必须为有效且启用的付费等级 ID
- 负责人（owner_id）：必须为有效且启用的红娘 ID
- 基本择偶要求（basic_requirement）：非空

**失败响应：** 返回具体缺失字段列表，不允许保存。

---

### BR-USER-002：系统自动生成字段

**触发时机：** 用户记录创建时

**规则：**
- created_at = 当前时间
- pool_status = "new_pending"
- is_profile_complete = FALSE
- is_in_match = FALSE

这四个字段不接受前端传值，由后端强制覆盖。

---

### BR-USER-003：资料完整度判定

**触发时机：** 用户资料编辑保存时，重新计算

**判定规则：** 以下条件全部满足时 is_profile_complete = TRUE：
- 最小必填字段全部有值（BR-USER-001 的字段）
- profile_detail（JSON）中包含门店要求的完整字段集

**第一版简化处理：** profile_detail 非空且 JSON 字段数 ≥ 门店配置的最小字段数（可硬编码为一个阈值，如 10 个字段）。

**影响范围：** is_profile_complete = FALSE 时，不允许发起推荐（BR-REC-001）。

---

### BR-USER-004：用户不可同时存在多张进行中配对卡

**触发时机：** 创建配对卡时

**校验规则：** 检查 user.is_in_match 字段：
- 若男方或女方任一方 is_in_match = TRUE → 拦截，返回"该用户已在配对中，无法创建新配对卡"

**进行中的配对卡定义：** match_card.stage IN ('initial_contact', 'stable_contact', 'success_pending_review')

---

### BR-USER-005：情感经历自动写入

**触发时机：** 配对卡标记为"结束"时

**规则：** 系统在双方用户的 emotional_history（JSON数组）中追加一条记录：

```json
{
  "match_card_id": 123,
  "partner_name": "张**",       // 脱敏：保留姓，后续用 ** 替代
  "start_date": "2026-01-15",   // 配对卡 created_at
  "end_date": "2026-03-10",     // 配对卡 ended_at
  "end_reason": "节奏不一致"     // end_reason_staff 的值
}
```

---

## 4. 未配对池规则（BR-POOL）

### BR-POOL-001：状态流转合法性校验

**触发时机：** 任何用户状态变更操作

**合法流转路径（白名单）：**

| 当前状态 | 允许变更为 |
|---------|-----------|
| new_pending | communicated_pending_recommend, paused |
| communicated_pending_recommend | recommended_pending_select, paused |
| recommended_pending_select | selected_pending_meet, communicated_pending_recommend, paused |
| selected_pending_meet | met_not_continue, paused |
| met_not_continue | communicated_pending_recommend |
| paused | 暂停前记录的状态（pre_pause_status） |

**特殊路径（系统触发）：**
- 创建配对卡时：selected_pending_meet → 移出未配对池（is_in_match = TRUE）
- 配对卡结束时：外部回流 → communicated_pending_recommend

**不在白名单内的状态变更一律拦截。** 管理员强制修改不受此限制，但需写入操作日志。

---

### BR-POOL-002：已见面未继续退出条件

**触发时机：** 用户处于 met_not_continue 状态，尝试变更状态时

**规则：** 必须存在至少一条满足以下条件的跟进记录：
- scene = 'unmatched'
- user_id = 该用户
- failure_reason_id IS NOT NULL（已选择结构化失败原因）
- created_at > 用户进入 met_not_continue 的时间

**不满足则：** 返回 400 FAILURE_REASON_REQUIRED。

### BR-POOL-003：暂停进入规则

**触发时机：** 红娘点击"暂停服务"

**规则：**
1. 当前状态必须在 S1-S4（new_pending, communicated_pending_recommend, recommended_pending_select, selected_pending_meet）
2. met_not_continue 状态不允许直接暂停（必须先处理完失败流程）
3. 必须填写暂停原因（reason_enum.category = 'pause' 中选择）
4. 系统记录 pre_pause_status = 当前状态

---

### BR-POOL-004：暂停解除规则

**触发时机：** 红娘点击"恢复服务"

**规则：**
1. 当前状态必须为 paused
2. 恢复后状态 = pre_pause_status
3. 恢复后清空 pre_pause_status = NULL
4. 恢复后重新按正常规则生成提醒

---

### BR-POOL-005：失败后回退规则

**触发时机：** 用户从 met_not_continue 状态退出

**规则：**
1. 状态设为 communicated_pending_recommend
2. 自动在 tags 数组中追加 "待重新推荐"（去重，不重复追加）
3. 写入操作日志

---

### BR-POOL-006：配对卡结束回流规则

**触发时机：** 配对卡 stage 从 initial_contact/stable_contact 变为 ended

**规则（对双方用户各执行一次）：**
1. 设 is_in_match = FALSE
2. 设 pool_status = "communicated_pending_recommend"
3. 在 tags 中追加 "待重新推荐"
4. 写入情感经历（BR-USER-005）
5. 设 user.last_unmatched_active_at = 当前时间
6. 写入操作日志（action = user_status_changed，reason = "配对卡结束自动回流"）

---

## 5. 推荐规则（BR-REC）

### BR-REC-001：发起推荐前置检查

**触发时机：** 红娘点击"发起推荐"

**校验规则：**
1. 用户 pool_status 必须为 communicated_pending_recommend
2. 用户 is_profile_complete 必须为 TRUE
3. 若不满足，返回对应提示（"请先将用户状态推进到已沟通待推荐" 或 "请先补全资料卡"）

---

### BR-REC-002：推荐候选上限

**触发时机：** 推荐批次创建时，添加候选人

**规则：** 当轮候选人数量 ≤ 用户付费等级对应的 recommend_limit

**计算方式：**
```
user → payment_level_id → payment_level.recommend_limit
当前批次候选数 ≤ recommend_limit
```

超出时提示"已达到该付费等级的推荐候选上限（N人）"。

---

### BR-REC-003：重复推荐检测

**触发时机：** 推荐批次创建页，添加候选人时实时检测

**检测逻辑：**
```sql
-- 查找该用户（被推荐者）历史上是否和候选人有过推荐关系
SELECT rc.*, rb.user_id
FROM recommendation_candidate rc
JOIN recommendation_batch rb ON rc.batch_id = rb.id
WHERE rb.user_id = {当前用户ID}
  AND rc.candidate_user_id = {候选人ID}
```

**提示级别：**
- 存在记录且 is_met = FALSE → 黄色提示："该候选人曾被推荐但未见面"
- 存在记录且 is_met = TRUE 且 result = 'not_continue' → 红色警告："该候选人曾见面但未继续"

**两种情况均不强制禁止，由红娘决定是否继续添加。**

---

### BR-REC-004：候选人过滤规则

**触发时机：** 推荐批次创建页的候选人搜索

**过滤条件（不出现在搜索结果中）：**
1. pool_status = 'paused' → 暂停中的用户不可被推荐
2. is_in_match = TRUE → 已在配对中的用户不可被推荐
3. gender 与被推荐用户相同 → 同性不推荐（默认规则，第一版不做同性匹配）
4. deleted_at IS NOT NULL → 已软删除用户不展示

---

### BR-REC-005：批次关闭规则

**触发时机：** 红娘手动关闭当前推荐批次，或批次中所有候选处理完毕

**规则：**
1. 批次 status 从 open → closed
2. 若无候选被选中（所有候选 is_selected = FALSE），用户状态回到 communicated_pending_recommend 并挂 "待重新推荐" 标签

---

## 6. 配对卡规则（BR-MATCH）

### BR-MATCH-001：配对卡创建规则

**触发时机：** 红娘点击"创建配对卡"

**前置校验：**
1. 男方 is_in_match = FALSE
2. 女方 is_in_match = FALSE
3. 当前用户（发起推荐的一方）状态为 selected_pending_meet

**创建时自动填入：**
- male_staff_id = 男方用户的 owner_id
- female_staff_id = 女方用户的 owner_id
- primary_staff_id = 当前操作红娘的 staff.id
- stage = 'initial_contact'
- risk_level = 'none'

**创建后联动：**
- 男方 is_in_match = TRUE
- 女方 is_in_match = TRUE
- 更新对应候选明细：is_met = TRUE, result = 'continue'
- 生成首次回访提醒（created_at + 7天）

---

### BR-MATCH-002：主阶段流转合法性

**合法流转路径（白名单）：**

| 当前阶段 | 允许变更为 |
|---------|-----------|
| initial_contact | stable_contact, ended |
| stable_contact | success_pending_review, ended |
| success_pending_review | success, stable_contact（驳回） |
| success | ended（失效处理） |
| ended | —（终态，不可变更） |

**不在白名单内的变更一律拦截。** 管理员强制修改不受此限制。

---

### BR-MATCH-003：阶段推进前置条件

#### initial_contact → stable_contact
- 男方侧：至少 1 条单方有效回访（由 male_staff_id 对应的红娘提交）
- 女方侧：至少 1 条单方有效回访（由 female_staff_id 对应的红娘提交）

#### stable_contact → success_pending_review
- 男方侧：至少 2 条单方有效回访
- 女方侧：至少 2 条单方有效回访
- 配对卡存续时间 ≥ 30 天（created_at 距今 ≥ 30天）

#### success_pending_review → success
- 操作人角色必须为 admin
- 关联的 success_application.status 必须为 pending

**说明：**
- 系统按 follow_up_record.user_id 区分男方侧/女方侧并分别计数，一条记录不能同时计入双方侧。
- 若双方红娘为同一人，仍需分别针对男方、女方各提交一条跟进记录。

### BR-MATCH-004：风险标记规则

**触发时机：** 红娘在配对卡详情页设置风险等级

**规则：**
1. 只有 stage IN ('initial_contact', 'stable_contact') 时才能设置风险
2. risk_level 从 'none' → 'watching' 或 'high_risk'：必须选择 risk_reason_id（关联 reason_enum.category = 'risk'）
3. risk_level 从 'watching' / 'high_risk' → 'none'：清空 risk_reason_id 和 risk_reason_note
4. 每次变更写入操作日志

---

### BR-MATCH-005：配对卡结束规则

**触发时机：** 主操作红娘点击"结束配对"

**前置条件：**
- stage IN ('initial_contact', 'stable_contact')
- end_reason_staff（红娘总结原因）必填

**系统动作：**
1. stage → 'ended'
2. ended_at = 当前时间
3. 执行 BR-POOL-006（双方回流）
4. 取消该配对卡所有未处理的提醒（reminder.status = 'pending' → 'expired'）

---

### BR-MATCH-006：配对卡结束原因结构

**字段要求：**
- end_reason_male：选填，可从 reason_enum.category = 'match_end' 选择或自由填写
- end_reason_female：选填，同上
- end_reason_staff：必填，同上

---

### BR-MATCH-007：双红娘权限规则

**操作权限矩阵：**

| 操作 | 男方红娘 | 女方红娘 | 主操作红娘 | 管理员 |
|------|---------|---------|-----------|-------|
| 查看配对卡 | ✅ | ✅ | ✅ | ✅ |
| 填写男方反馈/热度 | ✅ | ❌ | ✅ | ✅ |
| 填写女方反馈/热度 | ❌ | ✅ | ✅ | ✅ |
| 填写红娘综合判断 | ❌ | ❌ | ✅ | ✅ |
| 推进主阶段 | ❌ | ❌ | ✅ | ✅ |
| 设置风险标记 | ✅ | ✅ | ✅ | ✅ |
| 结束配对 | ❌ | ❌ | ✅ | ✅ |
| 发起成功申请 | ❌ | ❌ | ✅ | ✅ |

**说明：** 当男方红娘 = 女方红娘 = 主操作红娘（同一人）时，该红娘拥有所有权限。

---

### BR-MATCH-008：转移用户对配对卡的影响

**触发时机：** 用户转移审批通过

**规则：**
1. 查找该用户所有进行中的配对卡（stage IN ('initial_contact', 'stable_contact', 'success_pending_review')）
2. 若用户是男方 → 更新 male_staff_id 为新负责人
3. 若用户是女方 → 更新 female_staff_id 为新负责人
4. primary_staff_id 不自动变更（需管理员手动调整）
5. 写入操作日志

---

## 7. 跟进记录规则（BR-FU）

### BR-FU-001：未配对跟进保存规则

**触发时机：** 跟进场景为 unmatched 时保存

**必填字段：**
- user_id：有效用户 ID
- content：非空
- staff_id：当前操作红娘

**选填字段：**
- next_remind_at（仅在 next_remind_mode = manual 时可填）
- next_remind_mode（未配对跟进不强制，但若传值仅允许 manual）
- failure_reason_id（仅 met_not_continue 退出场景必填）

**保存后联动：**
- 更新 user.last_action_at = 当前时间
- 更新 user.last_unmatched_active_at = 当前时间
- 若填写了 next_remind_at，创建手动提醒记录

### BR-FU-002：已配对跟进保存规则（单方有效回访判定）

**触发时机：** 跟进场景为 matched 时保存

**必填字段（构成单方有效回访）：**
- match_card_id：有效配对卡 ID
- user_id：本次回访归属的一侧用户 ID（男方或女方）
- content：非空
- staff_id：当前操作红娘
- is_still_contact：yes / no / unknown
- risk_status：none / watching / high_risk
- next_remind_mode：manual / default
  - next_remind_mode = manual → next_remind_at 必填
  - next_remind_mode = default → next_remind_at 必须为空或不传

**说明：**
- “红娘综合判断”不是单方有效回访的必填字段。红娘综合判断由主操作红娘在配对卡详情页通过 PATCH /match-cards/{id}/ 独立更新 staff_judgment 字段。
- 一条 matched 跟进记录只能归属于一个 user_id，只能计入男方侧或女方侧之一。

**保存后联动：**
- 更新 match_card.last_visit_at = 当前时间
- 若 risk_status 与配对卡当前 risk_level 不一致 → 提示红娘是否同步更新配对卡风险等级
- next_remind_mode = manual → 创建手动提醒
- next_remind_mode = default → 按 BR-REMIND-003 计算下次提醒时间

### BR-FU-003：跟进记录权限校验

**规则：**
- 未配对跟进：只有 user.owner_id 匹配的红娘可以创建
- 已配对跟进（matched）：
  - 男方红娘只能创建 user_id = male_user_id 的跟进
  - 女方红娘只能创建 user_id = female_user_id 的跟进
  - 主操作红娘可以创建男方或女方任一侧的跟进
- 成功后回访（success_followup）：只有 primary_staff_id 或 admin 可以创建
- 管理员可以创建任意跟进

### BR-FU-004：成功后回访保存规则

**触发时机：** 跟进场景为 success_followup 时保存

**必填字段：**
- match_card_id：有效配对卡 ID，且 stage = 'success'
- content：非空
- is_still_contact：yes / no / unknown（语义为“是否仍在一起”）
- next_remind_mode：manual / default
  - next_remind_mode = manual → next_remind_at 必填
  - next_remind_mode = default → next_remind_at 必须为空或不传

**不要求填写：**
- risk_status
- staff_judgment

**保存后联动：**
- next_remind_mode = manual → 创建手动提醒
- 若 is_still_contact = 'no' → 提示红娘是否标记成功案例失效

## 8. 提醒规则（BR-REMIND）

### BR-REMIND-001：未首见进度提醒生成

**触发时机：** 每日定时任务扫描（建议凌晨执行）

**计算基准：** user.paid_at（付费时间）

**生成规则：**

```python
today = 当前日期
days_since_paid = (today - user.paid_at).days

# 只对未配对池中非暂停、非已见面未继续状态的用户执行
if user.pool_status NOT IN ('paused', 'met_not_continue') 
   AND user.is_in_match = FALSE:
   
    if days_since_paid >= 5 AND 无 first_meet_overdue 提醒:
        创建提醒(type='first_meet_overdue', level='超时')
    elif days_since_paid >= 4 AND 无 first_meet_warning 提醒:
        创建提醒(type='first_meet_warning', level='警告')
    elif days_since_paid >= 3 AND 无 first_meet_delayed 提醒:
        创建提醒(type='first_meet_delayed', level='延迟')
    elif days_since_paid >= 2 AND 无 first_meet_pending 提醒:
        创建提醒(type='first_meet_pending', level='待推进')
    elif days_since_paid >= 1 AND 无 normal 提醒:
        创建提醒(type='normal', level='普通')
```

**T+5 超时特殊规则：** 生成 first_meet_overdue 提醒后，红娘必须填写超时原因才能标记为已处理。

---

### BR-REMIND-002：暂停用户回访提醒

**触发时机：** 每日定时任务扫描

**规则：**
```python
if user.pool_status == 'paused':
    revisit_interval = user.payment_level.pause_revisit_days
    last_follow_up = 最近一条跟进记录的 created_at
    
    if last_follow_up 为空:
        基准时间 = 用户进入暂停的时间
    else:
        基准时间 = last_follow_up
    
    if (today - 基准时间).days >= revisit_interval:
        创建提醒(type='pause_revisit')
```

---

### BR-REMIND-003：已配对默认回访提醒

**触发时机：** 配对卡创建时 + 每次有效回访完成后

**规则：**
```python
# 配对卡创建时
创建提醒(remind_at = match_card.created_at + 7天, type='matched_revisit')

# 有效回访完成后，若红娘选择"走系统默认规则"
last_valid_visit_count = 该配对卡的有效回访次数

if last_valid_visit_count == 1:
    下次提醒 = match_card.created_at + 14天
elif last_valid_visit_count == 2:
    下次提醒 = match_card.created_at + 30天
else:
    # 超出默认节奏后，按每30天一次
    下次提醒 = 最近回访时间 + 30天

创建提醒(remind_at = 下次提醒, type='matched_revisit')
```

**提醒对象：** 男方红娘和女方红娘各生成一条提醒记录。

---

### BR-REMIND-004：手动提醒覆盖规则

**触发时机：** 红娘手动设置下次提醒时间

**规则：**
1. 将该对象（用户或配对卡）所有 status = 'pending' 且 is_manual = FALSE 的系统提醒标记为 'expired'
2. 创建新提醒：is_manual = TRUE, remind_at = 红娘设置的时间
3. 下一次回访完成后，提醒重新按系统默认规则生成（is_manual 的提醒只覆盖本次）

---

### BR-REMIND-005：紧急提醒判定

**触发时机：** 每日定时任务扫描 + 风险等级变更时即时检查

**判定公式：**
```python
urgency_score = 0

# 超时天数权重
overdue_days = (today - 应回访日期).days
if overdue_days > 0:
    urgency_score += overdue_days * 10

# 付费等级权重
urgency_score += payment_level.homepage_weight * 2

# 风险等级权重
if risk_level == 'high_risk':
    urgency_score += 50
elif risk_level == 'watching':
    urgency_score += 20

# 判定阈值
if urgency_score >= 60:
    触发紧急即时提醒（微信即时推送）
```

**注意：** 紧急提醒每个对象每天最多触发一次，避免重复推送。

---

### BR-REMIND-006：成功后回访提醒

**触发时机：** 成功案例审核通过时

**规则：**
```python
t0 = success_case.approved_at

创建提醒(remind_at = t0 + 30天, type='success_revisit', staff_id = match_card.primary_staff_id)
创建提醒(remind_at = t0 + 90天, type='success_revisit', staff_id = match_card.primary_staff_id)
创建提醒(remind_at = t0 + 180天, type='success_revisit', staff_id = match_card.primary_staff_id)
```

---

### BR-REMIND-007：提醒发送时间

**规则：**

| 类型 | 发送逻辑 |
|------|---------|
| 早上汇总 | 每日 09:00，汇总当天所有 pending 提醒，发送微信消息 |
| 晚上汇总 | 每日 20:00，汇总当天仍未处理的 pending 提醒，发送微信消息 |
| 紧急即时 | urgency_score ≥ 60 时，立即发送微信消息（每对象每天限一次） |

---

### BR-REMIND-008：提醒状态流转

| 当前状态 | 可变更为 | 触发条件 |
|---------|---------|---------|
| pending | sent | 系统发送了微信提醒 |
| sent | processed | 红娘在系统中标记已处理 或 完成了相关跟进 |
| pending/sent | expired | 被手动提醒覆盖 或 配对卡结束 或 超过有效期（如30天未处理） |

### BR-REMIND-009：未配对跟进超时提醒

**触发时机：** 每日定时任务扫描

```python
for user in 未配对池中非暂停、非met_not_continue的用户:
    timeout_days = user.payment_level.followup_timeout_days  # 默认7

    baseline = user.last_unmatched_active_at or user.created_at

    if (today - baseline).days >= timeout_days:
        if 不存在今日已生成的 followup_timeout 提醒:
            创建提醒(type='followup_timeout', staff_id=user.owner_id)
```

**以下动作发生后，更新 user.last_unmatched_active_at = 当前时间：**
1. 新建未配对跟进记录（scene = 'unmatched'）
2. 发起推荐（创建推荐批次）
3. 更新未配对阶段下的用户状态（pool_status 变更）

**说明：**
- 此字段仅在用户处于未配对池时更新。
- 用户进入已配对池后不再更新此字段。
- 用户从已配对池回流到未配对池时，last_unmatched_active_at 重置为回流时间。

---

## 9. 成功案例规则（BR-SUCCESS）

### BR-SUCCESS-001：成功申请前置条件

**触发时机：** 主操作红娘点击"发起成功申请"

**校验：**
1. 配对卡 stage = 'stable_contact'
2. 配对卡存续时间 ≥ 30 天
3. 操作人 = primary_staff_id 或 角色为 admin
4. 不存在 status = 'pending' 的未处理申请

---

### BR-SUCCESS-002：审核通过联动

**触发时机：** 管理员点击"通过"

**系统动作：**
1. success_application.status → 'approved'
2. success_application.reviewed_at = 当前时间
3. 创建 success_case 记录（approved_at = 当前时间）
4. match_card.stage → 'success'
5. 生成三条成功后回访提醒（BR-REMIND-006）
6. 写入操作日志

---

### BR-SUCCESS-003：审核驳回联动

**触发时机：** 管理员点击"驳回"

**前置条件：** review_note（驳回原因）必填

**系统动作：**
1. success_application.status → 'rejected'
2. success_application.reviewed_at = 当前时间
3. match_card.stage → 'stable_contact'（回退）
4. 写入操作日志（含驳回原因）

---

### BR-SUCCESS-004：成功失效处理

**触发时机：** 主操作红娘或管理员在成功案例详情页点击"标记失效"

**前置条件：**
- match_card.stage = 'success'
- 必须选择失效原因（reason_enum.category = 'success_invalidate'）

**系统动作：**
1. success_case.status → 'invalidated'
2. success_case.invalidated_at = 当前时间
3. match_card.stage → 'ended'
4. match_card.ended_at = 当前时间
5. 取消该配对卡所有未处理的成功后回访提醒
6. **不执行** BR-POOL-006（不自动回流）
7. 写入操作日志

---

## 10. 用户转移规则（BR-TRANSFER）

### BR-TRANSFER-001：转移申请校验

**触发时机：** 红娘提交转移申请

**校验：**
1. from_staff_id 必须等于 user.owner_id（只能转移自己负责的用户）
2. to_staff_id 必须为有效且启用的红娘 ID
3. from_staff_id ≠ to_staff_id（不能转给自己）
4. 不存在 status = 'pending' 的未处理转移申请（同一用户同时只能有一个在审）
5. 转移原因 reason 非空

---

### BR-TRANSFER-002：转移审批通过联动

**触发时机：** 管理员点击"通过"

**系统动作：**
1. user_transfer_request.status → 'approved'
2. user.owner_id → to_staff_id
3. 执行 BR-MATCH-008（更新进行中配对卡的红娘字段）
4. 将该用户所有 pending 状态的提醒的 staff_id 更新为新负责人
5. 通知原负责人（微信消息）
6. 通知新负责人（微信消息）
7. 写入操作日志

---

## 11. 排序规则（BR-SORT）

### BR-SORT-001：首页综合分计算

**适用范围：** 红娘首页"未配对超时"和"已配对待回访"模块

**计算公式：**
```python
def calculate_priority_score(entity):
    score = 0
    
    # 1. 付费等级权重（0-100）
    score += payment_level.homepage_weight
    
    # 2. 超时天数（每超时1天 +10分）
    if entity_type == 'user':
        overdue_days = (today - user.paid_at).days - 期望完成天数
    elif entity_type == 'match_card':
        overdue_days = (today - match_card.next_remind_at).days
    
    if overdue_days > 0:
        score += overdue_days * 10
    
    # 3. 风险权重
    if hasattr(entity, 'risk_level'):
        if entity.risk_level == 'high_risk':
            score += 50
        elif entity.risk_level == 'watching':
            score += 20
    
    # 4. 新用户权重（入库7天内 +15分）
    if entity_type == 'user' and (today - user.created_at).days <= 7:
        score += 15
    
    return score
```

### BR-SORT-002：严重超时保护

**规则：** 当 overdue_days ≥ 7 时，该条目的综合分最低保底为 80 分，确保不会被高付费等级的非超时用户完全淹没。

```python
if overdue_days >= 7:
    score = max(score, 80)
```

---

## 12. 权限规则（BR-PERM）

### BR-PERM-001：角色权限总表

| 功能 | 红娘 | 管理员 |
|------|------|-------|
| 创建用户 | ✅ | ✅ |
| 编辑用户资料 | ✅ 自己的 | ✅ 全部 |
| 查看未配对池 | ✅ 自己的 | ✅ 全部 |
| 查看已配对池 | ✅ 涉及自己的 | ✅ 全部 |
| 创建跟进记录 | ✅ | ✅ |
| 发起推荐 | ✅ | ✅ |
| 创建配对卡 | ✅ | ✅ |
| 修改用户状态 | ✅ 限白名单 | ✅ 无限制 |
| 设置风险标记 | ✅ | ✅ |
| 推进配对卡阶段 | ✅ 限主操作红娘 | ✅ |
| 结束配对 | ✅ 限主操作红娘 | ✅ |
| 发起成功申请 | ✅ 限主操作红娘 | ✅ |
| 审批成功申请 | ❌ | ✅ |
| 发起转移申请 | ✅ | ✅ |
| 审批转移申请 | ❌ | ✅ |
| 查看操作日志 | ❌ | ✅ |
| 管理原因枚举 | ❌ | ✅ |
| 管理付费等级 | ❌ | ✅ |
| 强制修改状态/负责人 | ❌ | ✅ |

### BR-PERM-002："自己的"定义

**红娘查看未配对池时：** 只能看到 user.owner_id = 自己的 staff.id 的用户

**红娘查看已配对池时：** 能看到 match_card.male_staff_id 或 match_card.female_staff_id 或 match_card.primary_staff_id = 自己的 staff.id 的配对卡

---

## 13. 微信消息模板（BR-MSG）

### BR-MSG-001：早晚汇总消息格式

```
【{时间段}工作提醒】
您今日有 {N} 项待处理：
- 未配对超时：{x} 人
- 已配对待回访：{y} 对
- 未首见超时：{z} 人
点击查看详情 → {链接}
```

### BR-MSG-002：紧急提醒消息格式

```
【紧急提醒】
{用户名/配对卡编号} 需要立即处理
原因：{提醒类型描述}
超时 {N} 天 | 风险等级：{risk_level}
点击处理 → {链接}
```

### BR-MSG-003：审批通知消息格式

```
【审批通知】
{类型}已{结果}
{详情描述}
操作人：{管理员名称}
时间：{时间}
```

### BR-MSG-004：转移通知消息格式

```
【用户转移通知】
用户 {用户名} 已从您名下转移至 {新红娘名称}
（或：用户 {用户名} 已从 {原红娘名称} 转移至您名下）
转移原因：{原因}
审批人：{管理员名称}
```

---

## 14. 版本记录

| 版本 | 日期 | 修改内容 |
|-----|------|---------|
| v1.0 | — | 初始版本，覆盖全部 MVP 业务规则 |
