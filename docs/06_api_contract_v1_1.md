# AI红娘配对跟进管理系统 API契约文档 v1.1

## 1. 文档信息

- 文档名称：API契约文档
- 版本：v1.1
- 依赖文档：MVP PRD v1.3、业务流程 v1.1、数据库设计 v1.1、业务规则 v1.1、技术选型 v1.1
- API风格：RESTful
- Base URL：`/api/v1`
- 认证方式：JWT Bearer Token
- 内容类型：application/json
- 时间格式：ISO 8601（如 `2026-03-14T08:00:00Z`）

---

## 2. 全局约定

### 2.1 认证

除登录接口外，所有接口需在请求头携带：

```
Authorization: Bearer {access_token}
```

Token 过期返回 401，客户端用 refresh_token 刷新。

### 2.2 通用响应格式

#### 成功（单对象）
```json
{
  "id": 1,
  "name": "张三",
  ...
}
```

#### 成功（列表）
```json
{
  "count": 120,
  "page": 1,
  "page_size": 20,
  "results": [...]
}
```

#### 失败
```json
{
  "code": "ERROR_CODE",
  "message": "人类可读的错误描述",
  "details": {}
}
```

### 2.3 通用查询参数

| 参数 | 类型 | 说明 |
|------|------|------|
| page | int | 页码，默认1 |
| page_size | int | 每页条数，默认20，最大100 |
| ordering | string | 排序字段，前缀 `-` 表示降序，如 `-created_at` |

### 2.4 错误码体系

| 错误码 | HTTP状态 | 说明 |
|--------|---------|------|
| AUTH_TOKEN_EXPIRED | 401 | Token 已过期 |
| AUTH_TOKEN_INVALID | 401 | Token 无效 |
| PERMISSION_DENIED | 403 | 无权限 |
| NOT_FOUND | 404 | 资源不存在 |
| VALIDATION_ERROR | 400 | 参数校验失败 |
| USER_PROFILE_INCOMPLETE | 400 | 资料未完整，不可推荐 |
| USER_ALREADY_IN_MATCH | 400 | 用户已在配对中 |
| USER_STATUS_TRANSITION_INVALID | 400 | 状态流转不合法 |
| MATCH_STAGE_TRANSITION_INVALID | 400 | 配对卡阶段流转不合法 |
| MATCH_NOT_ENOUGH_VISITS | 400 | 有效回访次数不足 |
| MATCH_DURATION_TOO_SHORT | 400 | 配对卡存续时间不足30天 |
| RECOMMEND_LIMIT_EXCEEDED | 400 | 超出推荐候选上限 |
| TRANSFER_PENDING_EXISTS | 400 | 已有待审批的转移申请 |
| SUCCESS_PENDING_EXISTS | 400 | 已有待审批的成功申请 |
| FAILURE_REASON_REQUIRED | 400 | 必须填写失败原因 |
| PAUSE_REASON_REQUIRED | 400 | 必须填写暂停原因 |
| END_REASON_REQUIRED | 400 | 必须填写结束原因 |
| RISK_REASON_REQUIRED | 400 | 风险标记必须填写原因 |

---

## 3. 认证模块（Auth）

### 3.1 登录

```
POST /api/v1/auth/login/
```

**请求体：**
```json
{
  "phone": "13800138000",
  "password": "xxx"
}
```

**成功响应（200）：**
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "staff": {
    "id": 1,
    "name": "王红娘",
    "role": "matchmaker",
    "phone": "13800138000"
  }
}
```

---

### 3.2 刷新Token

```
POST /api/v1/auth/refresh/
```

**请求体：**
```json
{
  "refresh_token": "eyJ..."
}
```

**成功响应（200）：**
```json
{
  "access_token": "eyJ..."
}
```

---

### 3.3 小程序登录

```
POST /api/v1/auth/wechat-login/
```

**请求体：**
```json
{
  "code": "微信登录code"
}
```

**成功响应（200）：** 同3.1。

---

## 4. 红娘/管理员模块（Staff）

### 4.1 获取当前登录人信息

```
GET /api/v1/staff/me/
```

**权限：** 已登录

**成功响应（200）：**
```json
{
  "id": 1,
  "name": "王红娘",
  "role": "matchmaker",
  "phone": "13800138000",
  "wechat_id": "wx_abc",
  "status": "active"
}
```

---

### 4.2 获取红娘列表

```
GET /api/v1/staff/
```

**权限：** 已登录（用于转移申请选择新负责人等场景）

**查询参数：**
| 参数 | 类型 | 说明 |
|------|------|------|
| role | string | 筛选角色：matchmaker / admin |
| status | string | 筛选状态：active / disabled |

**成功响应（200）：** 列表格式，每项同4.1字段。

---

## 5. 用户档案模块（User）

### 5.1 创建用户

```
POST /api/v1/users/
```

**权限：** matchmaker, admin
**关联规则：** BR-USER-001, BR-USER-002

**请求体：**
```json
{
  "name": "张三",
  "gender": "male",
  "age": 28,
  "phone": "13900139000",
  "wechat": "zhangsan_wx",
  "other_contact": "",
  "city": "成都",
  "payment_level_id": 1,
  "owner_id": 1,
  "basic_requirement": "希望找25-30岁，成都本地"
}
```

**成功响应（201）：**
```json
{
  "id": 1,
  "name": "张三",
  "gender": "male",
  "age": 28,
  "phone": "13900139000",
  "wechat": "zhangsan_wx",
  "other_contact": "",
  "city": "成都",
  "payment_level_id": 1,
  "payment_level_name": "标准会员",
  "owner_id": 1,
  "owner_name": "王红娘",
  "basic_requirement": "希望找25-30岁，成都本地",
  "pool_status": "new_pending",
  "pool_status_display": "新入库待处理",
  "is_profile_complete": false,
  "is_in_match": false,
  "tags": [],
  "paid_at": null,
  "created_at": "2026-03-14T08:00:00Z"
}
```

**失败响应（400）：** VALIDATION_ERROR + 缺失字段列表。

---

### 5.2 获取用户列表（未配对池）

```
GET /api/v1/users/
```

**权限：** matchmaker（仅自己负责的），admin（全部）
**关联规则：** BR-PERM-002

**查询参数：**
| 参数 | 类型 | 说明 |
|------|------|------|
| pool_status | string | 主状态筛选 |
| payment_level_id | int | 付费等级 |
| owner_id | int | 负责人（管理员可用） |
| is_profile_complete | bool | 资料是否完整 |
| tag | string | 标签筛选，如 `待重新推荐` |
| is_in_match | bool | 默认 false（未配对池），true（已在配对中） |
| created_at_after | datetime | 入库时间起 |
| created_at_before | datetime | 入库时间止 |
| search | string | 姓名/手机号/微信号模糊搜索 |
| ordering | string | 排序：`-created_at`, `priority_score` |

**成功响应（200）：** 列表格式，每项同5.1响应字段 + `priority_score`（综合分）。

---

### 5.3 获取用户详情

```
GET /api/v1/users/{id}/
```

**权限：** 用户的 owner 或 admin，或涉及该用户的配对卡红娘

**成功响应（200）：**
```json
{
  "id": 1,
  "name": "张三",
  "gender": "male",
  "age": 28,
  "phone": "13900139000",
  "wechat": "zhangsan_wx",
  "other_contact": "",
  "city": "成都",
  "payment_level_id": 1,
  "payment_level_name": "标准会员",
  "owner_id": 1,
  "owner_name": "王红娘",
  "basic_requirement": "希望找25-30岁，成都本地",
  "pool_status": "communicated_pending_recommend",
  "pool_status_display": "已沟通待推荐",
  "is_profile_complete": true,
  "is_in_match": false,
  "tags": ["待重新推荐"],
  "paid_at": "2026-03-01T10:00:00Z",
  "last_action_at": "2026-03-13T14:00:00Z",
  "last_unmatched_active_at": "2026-03-13T14:00:00Z",
  "profile_detail": { ... },
  "emotional_history": [
    {
      "match_card_id": 5,
      "partner_name": "李**",
      "start_date": "2026-01-15",
      "end_date": "2026-03-10",
      "end_reason": "节奏不一致"
    }
  ],
  "created_at": "2026-03-01T10:00:00Z",
  "recent_follow_ups": [...],
  "active_match_card": null,
  "stats": {
    "total_recommendations": 3,
    "total_meetings": 2,
    "total_match_cards": 1
  }
}
```

---

### 5.4 编辑用户资料

```
PATCH /api/v1/users/{id}/
```

**权限：** owner 或 admin
**关联规则：** BR-USER-003（保存后重新计算资料完整度）

**请求体：** 只传需要修改的字段。

**成功响应（200）：** 返回更新后的完整用户对象。

---

### 5.5 用户状态变更

```
POST /api/v1/users/{id}/change-status/
```

**权限：** owner 或 admin
**关联规则：** BR-POOL-001

**请求体：**
```json
{
  "to_status": "communicated_pending_recommend",
  "reason": "首次沟通完成"
}
```

**成功响应（200）：**
```json
{
  "id": 1,
  "pool_status": "communicated_pending_recommend",
  "pool_status_display": "已沟通待推荐",
  "message": "状态变更成功"
}
```

**失败响应（400）：** USER_STATUS_TRANSITION_INVALID。

---

### 5.6 暂停用户

```
POST /api/v1/users/{id}/pause/
```

**权限：** owner 或 admin
**关联规则：** BR-POOL-003

**请求体：**
```json
{
  "reason_id": 3,
  "reason_note": "用户说最近太忙"
}
```

**成功响应（200）：**
```json
{
  "id": 1,
  "pool_status": "paused",
  "pre_pause_status": "communicated_pending_recommend",
  "message": "用户已暂停"
}
```

---

### 5.7 恢复用户

```
POST /api/v1/users/{id}/resume/
```

**权限：** owner 或 admin
**关联规则：** BR-POOL-004

**成功响应（200）：**
```json
{
  "id": 1,
  "pool_status": "communicated_pending_recommend",
  "message": "用户已恢复"
}
```

---

## 6. 推荐模块（Recommendation）

### 6.1 创建推荐批次

```
POST /api/v1/recommendations/
```

**权限：** matchmaker, admin
**关联规则：** BR-REC-001, BR-REC-002

**请求体：**
```json
{
  "user_id": 1,
  "candidate_user_ids": [5, 8, 12]
}
```

**成功响应（201）：**
```json
{
  "id": 1,
  "user_id": 1,
  "user_name": "张三",
  "batch_no": "REC-20260314-001",
  "staff_id": 1,
  "staff_name": "王红娘",
  "candidate_count": 3,
  "status": "open",
  "candidates": [
    {
      "id": 1,
      "candidate_user_id": 5,
      "candidate_name": "李四",
      "is_selected": false,
      "is_met": false,
      "result": null,
      "warnings": []
    },
    {
      "id": 2,
      "candidate_user_id": 8,
      "candidate_name": "王五",
      "is_selected": false,
      "is_met": false,
      "result": null,
      "warnings": ["该候选人曾被推荐但未见面"]
    },
    {
      "id": 3,
      "candidate_user_id": 12,
      "candidate_name": "赵六",
      "is_selected": false,
      "is_met": false,
      "result": null,
      "warnings": ["该候选人曾见面但未继续"]
    }
  ],
  "created_at": "2026-03-14T09:00:00Z"
}
```

**失败响应（400）：** USER_PROFILE_INCOMPLETE / RECOMMEND_LIMIT_EXCEEDED。

---

### 6.2 获取用户的推荐历史

```
GET /api/v1/recommendations/?user_id={id}
```

**权限：** owner 或 admin

**成功响应（200）：** 列表格式，每项同6.1响应。

---

### 6.3 标记候选人选中

```
POST /api/v1/recommendations/candidates/{candidate_id}/select/
```

**权限：** 推荐批次的发起红娘 或 admin

**成功响应（200）：**
```json
{
  "id": 1,
  "candidate_user_id": 5,
  "is_selected": true,
  "message": "候选人已选中，用户状态已更新为已选人待见面"
}
```

---

### 6.4 关闭推荐批次

```
POST /api/v1/recommendations/{batch_id}/close/
```

**权限：** 推荐批次的发起红娘 或 admin
**关联规则：** BR-REC-005

**成功响应（200）：**
```json
{
  "id": 1,
  "status": "closed",
  "message": "批次已关闭"
}
```

---

### 6.5 候选人搜索（推荐用）

```
GET /api/v1/recommendations/candidate-search/?user_id={id}&search={keyword}
```

**权限：** matchmaker, admin
**关联规则：** BR-REC-004

**说明：** 自动过滤暂停中、已在配对中、同性、已删除的用户。返回候选人列表 + 重复推荐警告。

**查询参数：**
| 参数 | 类型 | 说明 |
|------|------|------|
| user_id | int | 被推荐的用户（用于性别过滤和重复检测） |
| search | string | 搜索关键词（姓名/手机号/微信号） |
| city | string | 城市筛选 |
| age_min | int | 年龄下限 |
| age_max | int | 年龄上限 |

**成功响应（200）：**
```json
{
  "count": 5,
  "results": [
    {
      "id": 5,
      "name": "李四",
      "gender": "female",
      "age": 26,
      "city": "成都",
      "payment_level_name": "高级会员",
      "pool_status_display": "已沟通待推荐",
      "is_profile_complete": true,
      "duplicate_warning": null
    },
    {
      "id": 8,
      "name": "王五",
      "gender": "female",
      "age": 27,
      "city": "成都",
      "payment_level_name": "标准会员",
      "pool_status_display": "已沟通待推荐",
      "is_profile_complete": true,
      "duplicate_warning": {
        "level": "warning",
        "message": "该候选人曾被推荐但未见面",
        "last_batch_date": "2026-02-10"
      }
    }
  ]
}
```

---

## 7. 配对卡模块（MatchCard）

### 7.1 创建配对卡

```
POST /api/v1/match-cards/
```

**权限：** matchmaker, admin
**关联规则：** BR-MATCH-001, BR-USER-004

**请求体：**
```json
{
  "male_user_id": 1,
  "female_user_id": 5,
  "candidate_id": 1
}
```

`candidate_id` 为推荐候选明细 ID，用于关联更新候选明细。

**成功响应（201）：**
```json
{
  "id": 1,
  "male_user_id": 1,
  "male_user_name": "张三",
  "female_user_id": 5,
  "female_user_name": "李四",
  "male_staff_id": 1,
  "male_staff_name": "王红娘",
  "female_staff_id": 2,
  "female_staff_name": "赵红娘",
  "primary_staff_id": 1,
  "primary_staff_name": "王红娘",
  "stage": "initial_contact",
  "stage_display": "初期接触",
  "risk_level": "none",
  "risk_level_display": "无风险",
  "risk_reason": null,
  "male_feedback": null,
  "female_feedback": null,
  "male_heat": null,
  "female_heat": null,
  "staff_judgment": null,
  "last_visit_at": null,
  "next_remind_at": "2026-03-21T09:00:00Z",
  "end_reason_male": null,
  "end_reason_female": null,
  "end_reason_staff": null,
  "ended_at": null,
  "created_at": "2026-03-14T10:00:00Z"
}
```

**失败响应（400）：** USER_ALREADY_IN_MATCH。

---

### 7.2 获取配对卡列表（已配对池）

```
GET /api/v1/match-cards/
```

**权限：** matchmaker（涉及自己的），admin（全部）
**关联规则：** BR-PERM-002

**查询参数：**
| 参数 | 类型 | 说明 |
|------|------|------|
| stage | string | 主阶段筛选 |
| risk_level | string | 风险等级筛选 |
| staff_id | int | 红娘筛选（匹配 male_staff_id / female_staff_id / primary_staff_id 任一） |
| staff_role | string | 配合 staff_id 使用：male_staff / female_staff / primary_staff |
| last_visit_before | datetime | 最近回访时间早于 |
| next_remind_before | datetime | 下次提醒时间早于（找超时的） |
| ordering | string | 排序：`-created_at`, `next_remind_at`, `priority_score` |

**成功响应（200）：** 列表格式，每项同7.1响应字段。

---

### 7.3 获取配对卡详情

```
GET /api/v1/match-cards/{id}/
```

**权限：** 涉及的三个红娘任一 或 admin

**成功响应（200）：** 同7.1响应字段，额外包含：

```json
{
  ...,
  "follow_ups": [
    {
      "id": 1,
      "staff_name": "王红娘",
      "content": "男方反馈：聊得不错，准备约第二次",
      "is_still_contact": "yes",
      "risk_status": "none",
      "next_remind_mode": "default",
      "created_at": "2026-03-21T14:00:00Z"
    }
  ],
  "valid_visit_count": 1
}
```

---

### 7.4 推进配对卡阶段

```
POST /api/v1/match-cards/{id}/advance-stage/
```

**权限：** primary_staff 或 admin
**关联规则：** BR-MATCH-002, BR-MATCH-003

**请求体：**
```json
{
  "to_stage": "stable_contact",
  "reason": "双方持续保持联系"
}
```

**成功响应（200）：**
```json
{
  "id": 1,
  "stage": "stable_contact",
  "stage_display": "稳定联系",
  "message": "阶段推进成功"
}
```

**失败响应（400）：** MATCH_STAGE_TRANSITION_INVALID / MATCH_NOT_ENOUGH_VISITS。

---

### 7.5 设置风险标记

```
POST /api/v1/match-cards/{id}/set-risk/
```

**权限：** 涉及的三个红娘任一 或 admin
**关联规则：** BR-MATCH-004

**请求体：**
```json
{
  "risk_level": "watching",
  "risk_reason_id": 1,
  "risk_reason_note": "女方最近回复变慢"
}
```

**成功响应（200）：**
```json
{
  "id": 1,
  "risk_level": "watching",
  "risk_level_display": "关注中",
  "message": "风险标记已更新"
}
```

**失败响应（400）：** RISK_REASON_REQUIRED。

---

### 7.6 结束配对

```
POST /api/v1/match-cards/{id}/end/
```

**权限：** primary_staff 或 admin
**关联规则：** BR-MATCH-005, BR-MATCH-006, BR-POOL-006

**请求体：**
```json
{
  "end_reason_male": "觉得性格不合",
  "end_reason_female": "节奏跟不上",
  "end_reason_staff": "双方节奏不一致，女方明确提出结束"
}
```

**成功响应（200）：**
```json
{
  "id": 1,
  "stage": "ended",
  "ended_at": "2026-03-14T15:00:00Z",
  "message": "配对已结束，双方用户已回流未配对池",
  "reflowed_users": [
    { "id": 1, "name": "张三", "new_status": "communicated_pending_recommend" },
    { "id": 5, "name": "李四", "new_status": "communicated_pending_recommend" }
  ]
}
```

**失败响应（400）：** END_REASON_REQUIRED。

---

### 7.7 更新配对卡反馈/热度

```
PATCH /api/v1/match-cards/{id}/
```

**权限：** BR-MATCH-007 权限矩阵
**说明：** 男方红娘只能更新 male_feedback / male_heat，女方红娘只能更新 female_feedback / female_heat，主操作红娘可更新 staff_judgment。staff_judgment 不再通过跟进记录接口提交。

**请求体（示例：男方红娘更新）：**
```json
{
  "male_feedback": "男方说相处很愉快",
  "male_heat": 8
}
```

**成功响应（200）：** 返回更新后的完整配对卡对象。

**失败响应（403）：** PERMISSION_DENIED（如女方红娘尝试更新男方字段）。

---

## 8. 跟进记录模块（FollowUp）

### 8.1 创建跟进记录

```
POST /api/v1/follow-ups/
```

**权限：** BR-FU-003
**关联规则：** BR-FU-001, BR-FU-002, BR-FU-004

**请求体（未配对跟进）：**
```json
{
  "scene": "unmatched",
  "user_id": 1,
  "content": "电话沟通，用户明确了择偶要求",
  "next_remind_at": "2026-03-16T09:00:00Z"
}
```

**请求体（未配对 + 失败原因）：**
```json
{
  "scene": "unmatched",
  "user_id": 1,
  "content": "首次见面后，女方觉得性格不合",
  "failure_reason_id": 5
}
```

**请求体（已配对跟进 / 单方有效回访，手动提醒）：**
```json
{
  "scene": "matched",
  "match_card_id": 1,
  "user_id": 1,
  "content": "男方反馈：第二次约会聊得很好",
  "is_still_contact": "yes",
  "risk_status": "none",
  "next_remind_mode": "manual",
  "next_remind_at": "2026-03-28T09:00:00Z"
}
```

**请求体（已配对跟进 / 单方有效回访，默认节奏）：**
```json
{
  "scene": "matched",
  "match_card_id": 1,
  "user_id": 5,
  "content": "女方反馈：感觉还不错",
  "is_still_contact": "yes",
  "risk_status": "none",
  "next_remind_mode": "default"
}
```

**请求体（成功后回访）：**
```json
{
  "scene": "success_followup",
  "match_card_id": 1,
  "content": "双方仍在交往中，感情稳定",
  "is_still_contact": "yes",
  "next_remind_mode": "default"
}
```

**字段说明：**

| 字段 | 类型 | 必填 | 取值 | 说明 |
|------|------|------|------|------|
| next_remind_mode | string | 是（matched / success_followup 场景） | manual / default | 提醒方式选择 |
| next_remind_at | datetime | 条件必填 | ISO 8601 | 当 mode=manual 时必填；当 mode=default 时必须为空或不传 |

**校验规则：**
- next_remind_mode = "manual" 且 next_remind_at 为空 → 400 VALIDATION_ERROR
- next_remind_mode = "default" 且 next_remind_at 非空 → 400 VALIDATION_ERROR
- scene = "unmatched" 时 next_remind_mode 为选填

**成功响应（201）：**
```json
{
  "id": 1,
  "scene": "matched",
  "match_card_id": 1,
  "user_id": 1,
  "staff_id": 1,
  "staff_name": "王红娘",
  "content": "男方反馈：第二次约会聊得很好",
  "is_still_contact": "yes",
  "risk_status": "none",
  "next_remind_mode": "manual",
  "is_valid_visit": true,
  "next_remind_at": "2026-03-28T09:00:00Z",
  "failure_reason_id": null,
  "created_at": "2026-03-14T14:30:00Z"
}
```

### 8.2 获取跟进记录列表

```
GET /api/v1/follow-ups/
```

**查询参数：**
| 参数 | 类型 | 说明 |
|------|------|------|
| user_id | int | 按用户筛选 |
| match_card_id | int | 按配对卡筛选 |
| scene | string | unmatched / matched / success_followup |
| staff_id | int | 按红娘筛选 |
| is_valid_visit | bool | 仅有效回访 |

**成功响应（200）：** 列表格式，每项同8.1响应字段。

---

## 9. 成功案例模块（Success）

### 9.1 发起成功申请

```
POST /api/v1/success-applications/
```

**权限：** primary_staff 或 admin
**关联规则：** BR-SUCCESS-001

**请求体：**
```json
{
  "match_card_id": 1,
  "apply_note": "双方已确认恋爱关系，交往满30天"
}
```

**成功响应（201）：**
```json
{
  "id": 1,
  "match_card_id": 1,
  "applicant_id": 1,
  "applicant_name": "王红娘",
  "apply_note": "双方已确认恋爱关系，交往满30天",
  "status": "pending",
  "created_at": "2026-03-14T16:00:00Z"
}
```

**失败响应（400）：** MATCH_DURATION_TOO_SHORT / SUCCESS_PENDING_EXISTS。

---

### 9.2 获取成功申请列表

```
GET /api/v1/success-applications/
```

**权限：** admin（审批列表），matchmaker（自己发起的）

**查询参数：**
| 参数 | 类型 | 说明 |
|------|------|------|
| status | string | pending / approved / rejected |

---

### 9.3 审核成功申请（通过）

```
POST /api/v1/success-applications/{id}/approve/
```

**权限：** admin
**关联规则：** BR-SUCCESS-002

**成功响应（200）：**
```json
{
  "id": 1,
  "status": "approved",
  "reviewed_at": "2026-03-14T17:00:00Z",
  "success_case_id": 1,
  "message": "成功案例已入库"
}
```

---

### 9.4 审核成功申请（驳回）

```
POST /api/v1/success-applications/{id}/reject/
```

**权限：** admin
**关联规则：** BR-SUCCESS-003

**请求体：**
```json
{
  "review_note": "双方交往时间不足，建议再观察"
}
```

**成功响应（200）：**
```json
{
  "id": 1,
  "status": "rejected",
  "review_note": "双方交往时间不足，建议再观察",
  "reviewed_at": "2026-03-14T17:00:00Z",
  "message": "已驳回，配对卡已回退到稳定联系"
}
```

---

### 9.5 标记成功失效

```
POST /api/v1/success-cases/{id}/invalidate/
```

**权限：** primary_staff 或 admin
**关联规则：** BR-SUCCESS-004

**请求体：**
```json
{
  "reason_id": 1,
  "reason_note": "双方已分手"
}
```

**成功响应（200）：**
```json
{
  "id": 1,
  "status": "invalidated",
  "invalidated_at": "2026-03-14T18:00:00Z",
  "message": "成功案例已标记失效，配对卡已结束"
}
```

---

## 10. 用户转移模块（Transfer）

### 10.1 发起转移申请

```
POST /api/v1/transfer-requests/
```

**权限：** matchmaker（自己的用户），admin
**关联规则：** BR-TRANSFER-001

**请求体：**
```json
{
  "user_id": 1,
  "to_staff_id": 2,
  "reason": "本人即将休假一个月"
}
```

**成功响应（201）：**
```json
{
  "id": 1,
  "user_id": 1,
  "user_name": "张三",
  "from_staff_id": 1,
  "from_staff_name": "王红娘",
  "to_staff_id": 2,
  "to_staff_name": "赵红娘",
  "reason": "本人即将休假一个月",
  "status": "pending",
  "created_at": "2026-03-14T19:00:00Z"
}
```

**失败响应（400）：** TRANSFER_PENDING_EXISTS。

---

### 10.2 获取转移申请列表

```
GET /api/v1/transfer-requests/
```

**权限：** admin（审批列表），matchmaker（自己发起的）

**查询参数：**
| 参数 | 类型 | 说明 |
|------|------|------|
| status | string | pending / approved / rejected |

---

### 10.3 审核转移申请（通过）

```
POST /api/v1/transfer-requests/{id}/approve/
```

**权限：** admin
**关联规则：** BR-TRANSFER-002, BR-MATCH-008

**成功响应（200）：**
```json
{
  "id": 1,
  "status": "approved",
  "reviewed_at": "2026-03-14T19:30:00Z",
  "message": "转移已生效",
  "affected_match_cards": [
    { "id": 3, "updated_field": "male_staff_id", "new_staff_name": "赵红娘" }
  ]
}
```

---

### 10.4 审核转移申请（驳回）

```
POST /api/v1/transfer-requests/{id}/reject/
```

**权限：** admin

**请求体：**
```json
{
  "review_note": "当前负责用户较少，建议不转移"
}
```

**成功响应（200）：**
```json
{
  "id": 1,
  "status": "rejected",
  "review_note": "当前负责用户较少，建议不转移",
  "reviewed_at": "2026-03-14T19:30:00Z"
}
```

---

## 11. 提醒模块（Reminder）

### 11.1 获取我的提醒列表

```
GET /api/v1/reminders/
```

**权限：** 已登录（自动按当前 staff_id 筛选）

**查询参数：**
| 参数 | 类型 | 说明 |
|------|------|------|
| status | string | pending / sent / processed / expired |
| remind_type | string | 类型筛选 |
| target_type | string | user / match_card |
| remind_at_before | datetime | 提醒时间早于 |
| remind_at_after | datetime | 提醒时间晚于 |

**成功响应（200）：**
```json
{
  "count": 8,
  "results": [
    {
      "id": 1,
      "target_type": "user",
      "target_id": 1,
      "target_name": "张三",
      "target_summary": "已沟通待推荐 | 标准会员 | 入库3天",
      "staff_id": 1,
      "remind_type": "first_meet_pending",
      "remind_type_display": "未首见待推进",
      "remind_at": "2026-03-16T09:00:00Z",
      "status": "pending",
      "is_manual": false,
      "created_at": "2026-03-14T02:00:00Z"
    }
  ]
}
```

**跟进超时提醒示例：**
```json
{
  "id": 15,
  "target_type": "user",
  "target_id": 3,
  "target_name": "王五",
  "target_summary": "已沟通待推荐 | 高级会员 | 最近跟进：12天前",
  "remind_type": "followup_timeout",
  "remind_type_display": "跟进超时",
  "remind_at": "2026-03-14T09:00:00Z",
  "status": "pending"
}
```

---

### 11.2 标记提醒已处理

```
POST /api/v1/reminders/{id}/process/
```

**权限：** 提醒的接收红娘 或 admin

**成功响应（200）：**
```json
{
  "id": 1,
  "status": "processed",
  "processed_at": "2026-03-14T10:30:00Z"
}
```

---

### 11.3 手动设置提醒

```
POST /api/v1/reminders/manual/
```

**权限：** matchmaker, admin
**关联规则：** BR-REMIND-004

**请求体：**
```json
{
  "target_type": "user",
  "target_id": 1,
  "remind_at": "2026-03-18T09:00:00Z"
}
```

**成功响应（201）：**
```json
{
  "id": 10,
  "target_type": "user",
  "target_id": 1,
  "remind_type": "manual",
  "remind_at": "2026-03-18T09:00:00Z",
  "status": "pending",
  "is_manual": true,
  "message": "手动提醒已设置，原有系统提醒已覆盖"
}
```

---

## 12. 首页聚合接口（Dashboard）

### 12.1 红娘首页

```
GET /api/v1/dashboard/matchmaker/
```

**权限：** matchmaker

**成功响应（200）：**
```json
{
  "unmatched_overdue": {
    "count": 3,
    "items": [
      {
        "user_id": 1,
        "user_name": "张三",
        "pool_status_display": "已沟通待推荐",
        "payment_level_name": "高级会员",
        "overdue_days": 5,
        "overdue_type": "未首见超时",
        "priority_score": 85
      }
    ]
  },
  "matched_pending_visit": {
    "count": 4,
    "items": [
      {
        "match_card_id": 1,
        "male_name": "张三",
        "female_name": "李四",
        "stage_display": "初期接触",
        "risk_level_display": "无风险",
        "last_visit_at": "2026-03-07T14:00:00Z",
        "next_remind_at": "2026-03-14T09:00:00Z",
        "overdue_days": 0,
        "priority_score": 40
      }
    ]
  },
  "today_processed": {
    "count": 2
  },
  "recent_new": {
    "count": 1,
    "items": [
      {
        "user_id": 10,
        "user_name": "新用户A",
        "created_at": "2026-03-14T08:00:00Z"
      }
    ]
  }
}
```

---

### 12.2 管理员首页

```
GET /api/v1/dashboard/admin/
```

**权限：** admin

**成功响应（200）：**
```json
{
  "overdue_summary": {
    "total_overdue_users": 12,
    "by_staff": [
      { "staff_id": 1, "staff_name": "王红娘", "overdue_count": 5 },
      { "staff_id": 2, "staff_name": "赵红娘", "overdue_count": 7 }
    ]
  },
  "pending_approvals": {
    "transfer_count": 2,
    "success_count": 1
  },
  "high_risk_matches": {
    "count": 3
  }
}
```

---

## 13. 操作日志模块（OpLog）

### 13.1 获取操作日志

```
GET /api/v1/operation-logs/
```

**权限：** admin

**查询参数：**
| 参数 | 类型 | 说明 |
|------|------|------|
| target_type | string | 对象类型筛选 |
| target_id | int | 对象ID |
| operator_id | int | 操作人 |
| action | string | 操作类型 |
| created_at_after | datetime | 时间起 |
| created_at_before | datetime | 时间止 |

**成功响应（200）：**
```json
{
  "count": 50,
  "results": [
    {
      "id": 1,
      "operator_id": 1,
      "operator_name": "王红娘",
      "target_type": "user",
      "target_id": 1,
      "action": "user_status_changed",
      "action_display": "用户状态变更",
      "field_changed": "pool_status",
      "old_value": "new_pending",
      "new_value": "communicated_pending_recommend",
      "reason": "首次沟通完成",
      "created_at": "2026-03-14T08:30:00Z"
    }
  ]
}
```

---

## 14. 配置管理模块（ConfigMgmt）

### 14.1 获取原因枚举列表

```
GET /api/v1/reason-enums/
```

**权限：** 已登录

**查询参数：**
| 参数 | 类型 | 说明 |
|------|------|------|
| category | string | 原因分类：pause / meet_failure / overdue / risk / transfer / success_invalidate / match_end |
| is_active | bool | 是否启用 |

**成功响应（200）：**
```json
{
  "count": 7,
  "results": [
    { "id": 1, "category": "pause", "label": "忙工作", "sort_order": 1, "is_active": true },
    { "id": 2, "category": "pause", "label": "忙考试", "sort_order": 2, "is_active": true }
  ]
}
```

---

### 14.2 创建原因枚举

```
POST /api/v1/reason-enums/
```

**权限：** admin

**请求体：**
```json
{
  "category": "match_end",
  "label": "双方家庭不同意",
  "sort_order": 5
}
```

---

### 14.3 编辑原因枚举

```
PATCH /api/v1/reason-enums/{id}/
```

**权限：** admin

---

### 14.4 获取付费等级列表

```
GET /api/v1/payment-levels/
```

**权限：** 已登录

**成功响应（200）：**
```json
{
  "count": 3,
  "results": [
    {
      "id": 1,
      "name": "标准会员",
      "sort_order": 1,
      "is_active": true,
      "homepage_weight": 10,
      "recommend_limit": 3,
      "pause_revisit_days": 30,
      "note": ""
    },
    {
      "id": 2,
      "name": "高级会员",
      "sort_order": 2,
      "is_active": true,
      "homepage_weight": 30,
      "recommend_limit": 5,
      "pause_revisit_days": 14,
      "note": ""
    }
  ]
}
```

---

### 14.5 创建付费等级

```
POST /api/v1/payment-levels/
```

**权限：** admin

---

### 14.6 编辑付费等级

```
PATCH /api/v1/payment-levels/{id}/
```

**权限：** admin

---

## 15. 全局搜索

```
GET /api/v1/search/?q={keyword}
```

**权限：** 已登录

**说明：** 同时搜索姓名、手机号、微信号，返回匹配的用户列表。红娘只能搜到自己负责的 + 涉及自己配对卡的用户。

**成功响应（200）：**
```json
{
  "count": 3,
  "results": [
    {
      "id": 1,
      "name": "张三",
      "gender": "male",
      "age": 28,
      "pool_status_display": "已沟通待推荐",
      "is_in_match": false,
      "owner_name": "王红娘",
      "match_field": "name"
    }
  ]
}
```

---

## 16. 接口总览

| 编号 | 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|------|
| 3.1 | POST | /auth/login/ | 登录 | 公开 |
| 3.2 | POST | /auth/refresh/ | 刷新Token | 公开 |
| 3.3 | POST | /auth/wechat-login/ | 小程序登录 | 公开 |
| 4.1 | GET | /staff/me/ | 当前登录人 | 已登录 |
| 4.2 | GET | /staff/ | 红娘列表 | 已登录 |
| 5.1 | POST | /users/ | 创建用户 | 红娘/管理员 |
| 5.2 | GET | /users/ | 用户列表 | 红娘(自己)/管理员 |
| 5.3 | GET | /users/{id}/ | 用户详情 | 相关红娘/管理员 |
| 5.4 | PATCH | /users/{id}/ | 编辑用户 | owner/管理员 |
| 5.5 | POST | /users/{id}/change-status/ | 状态变更 | owner/管理员 |
| 5.6 | POST | /users/{id}/pause/ | 暂停 | owner/管理员 |
| 5.7 | POST | /users/{id}/resume/ | 恢复 | owner/管理员 |
| 6.1 | POST | /recommendations/ | 创建推荐 | 红娘/管理员 |
| 6.2 | GET | /recommendations/ | 推荐历史 | owner/管理员 |
| 6.3 | POST | /recommendations/candidates/{id}/select/ | 标记选中 | 发起红娘/管理员 |
| 6.4 | POST | /recommendations/{id}/close/ | 关闭批次 | 发起红娘/管理员 |
| 6.5 | GET | /recommendations/candidate-search/ | 候选搜索 | 红娘/管理员 |
| 7.1 | POST | /match-cards/ | 创建配对卡 | 红娘/管理员 |
| 7.2 | GET | /match-cards/ | 配对卡列表 | 相关红娘/管理员 |
| 7.3 | GET | /match-cards/{id}/ | 配对卡详情 | 相关红娘/管理员 |
| 7.4 | POST | /match-cards/{id}/advance-stage/ | 推进阶段 | 主操作红娘/管理员 |
| 7.5 | POST | /match-cards/{id}/set-risk/ | 设置风险 | 相关红娘/管理员 |
| 7.6 | POST | /match-cards/{id}/end/ | 结束配对 | 主操作红娘/管理员 |
| 7.7 | PATCH | /match-cards/{id}/ | 更新反馈热度 | 权限矩阵 |
| 8.1 | POST | /follow-ups/ | 创建跟进 | BR-FU-003 |
| 8.2 | GET | /follow-ups/ | 跟进列表 | 相关红娘/管理员 |
| 9.1 | POST | /success-applications/ | 发起成功申请 | 主操作红娘/管理员 |
| 9.2 | GET | /success-applications/ | 申请列表 | 管理员/发起人 |
| 9.3 | POST | /success-applications/{id}/approve/ | 审核通过 | 管理员 |
| 9.4 | POST | /success-applications/{id}/reject/ | 审核驳回 | 管理员 |
| 9.5 | POST | /success-cases/{id}/invalidate/ | 标记失效 | 主操作红娘/管理员 |
| 10.1 | POST | /transfer-requests/ | 发起转移 | 红娘/管理员 |
| 10.2 | GET | /transfer-requests/ | 转移列表 | 管理员/发起人 |
| 10.3 | POST | /transfer-requests/{id}/approve/ | 审核通过 | 管理员 |
| 10.4 | POST | /transfer-requests/{id}/reject/ | 审核驳回 | 管理员 |
| 11.1 | GET | /reminders/ | 我的提醒 | 已登录 |
| 11.2 | POST | /reminders/{id}/process/ | 标记已处理 | 接收红娘/管理员 |
| 11.3 | POST | /reminders/manual/ | 手动提醒 | 红娘/管理员 |
| 12.1 | GET | /dashboard/matchmaker/ | 红娘首页 | 红娘 |
| 12.2 | GET | /dashboard/admin/ | 管理员首页 | 管理员 |
| 13.1 | GET | /operation-logs/ | 操作日志 | 管理员 |
| 14.1 | GET | /reason-enums/ | 原因枚举列表 | 已登录 |
| 14.2 | POST | /reason-enums/ | 创建原因枚举 | 管理员 |
| 14.3 | PATCH | /reason-enums/{id}/ | 编辑原因枚举 | 管理员 |
| 14.4 | GET | /payment-levels/ | 付费等级列表 | 已登录 |
| 14.5 | POST | /payment-levels/ | 创建付费等级 | 管理员 |
| 14.6 | PATCH | /payment-levels/{id}/ | 编辑付费等级 | 管理员 |
| 15 | GET | /search/ | 全局搜索 | 已登录 |

**共计 38 个接口。**

---

## 17. 版本记录

| 版本 | 日期 | 修改内容 |
|-----|------|---------|
| v1.0 | — | 初始版本，38个接口 |
