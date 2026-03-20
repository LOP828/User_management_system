# AI红娘配对跟进管理系统 权限矩阵文档 v1.1.1

## 1. 文档信息

- 文档名称：权限矩阵文档
- 版本：v1.1.1
- 依赖文档：MVP PRD v1.3、业务规则 v1.1.1、API契约 v1.1.1
- 文档用途：每个接口、页面、按钮对应的角色权限和条件约束。开发实现权限拦截和 Codex 安全审计的对照表。

---

## 2. 角色定义

| 角色代码 | 角色名称 | 说明 |
|---------|---------|------|
| matchmaker | 红娘 | 一线服务人员，管理自己负责的用户和涉及自己的配对卡 |
| admin | 管理员 | 门店管理员，全局可见，负责审批和配置 |

---

## 3. 数据可见性规则

### 3.1 红娘的数据边界

红娘只能看到和操作与自己相关的数据，具体定义如下：

| 数据对象 | "自己的"定义 |
|---------|-------------|
| 用户 | user.owner_id = 当前 staff.id |
| 配对卡 | match_card.male_staff_id 或 female_staff_id 或 primary_staff_id = 当前 staff.id |
| 推荐批次 | recommendation_batch.staff_id = 当前 staff.id，或 batch.user_id 为自己负责的用户 |
| 跟进记录 | 关联的用户或配对卡属于"自己的" |
| 提醒 | reminder.staff_id = 当前 staff.id |
| 转移申请 | 自己发起的（from_staff_id = 当前 staff.id） |
| 成功申请 | 自己发起的（applicant_id = 当前 staff.id） |

### 3.2 管理员的数据边界

管理员可以查看和操作全店所有数据，无数据边界限制。

---

## 4. API 接口权限矩阵

### 4.1 认证模块

| 接口 | 方法 | 路径 | 匿名 | 红娘 | 管理员 | 附加条件 |
|------|------|------|------|------|-------|---------|
| 登录 | POST | /auth/login/ | ✅ | — | — | — |
| 刷新Token | POST | /auth/refresh/ | ✅ | — | — | — |
| 小程序登录 | POST | /auth/wechat-login/ | ✅ | — | — | — |

### 4.2 红娘/管理员模块

| 接口 | 方法 | 路径 | 红娘 | 管理员 | 附加条件 |
|------|------|------|------|-------|---------|
| 当前登录人 | GET | /staff/me/ | ✅ | ✅ | — |
| 红娘列表 | GET | /staff/ | ✅ | ✅ | 红娘：仅用于选择负责人/转移目标，不含敏感信息 |

### 4.3 用户档案模块

| 接口 | 方法 | 路径 | 红娘 | 管理员 | 附加条件 |
|------|------|------|------|-------|---------|
| 创建用户 | POST | /users/ | ✅ | ✅ | — |
| 用户列表 | GET | /users/ | ✅ 自己的 | ✅ 全部 | 红娘：自动注入 owner_id = 自己 |
| 用户详情 | GET | /users/{id}/ | ✅ 有关联 | ✅ | 红娘：owner 或涉及自己的任意历史/当前配对卡中的用户（含 success / ended） |
| 编辑用户 | PATCH | /users/{id}/ | ✅ owner | ✅ | 红娘：仅 owner_id = 自己，且不可修改 owner_id；管理员 force 修改 owner_id 时必须传 force=true + force_reason |
| 状态变更 | POST | /users/{id}/change-status/ | ✅ owner | ✅ | 红娘：限合法流转路径且不可传 force=true；管理员可传 force=true 跳过白名单，force_reason 必填 |
| 暂停 | POST | /users/{id}/pause/ | ✅ owner | ✅ | 红娘：仅 owner_id = 自己 |
| 恢复 | POST | /users/{id}/resume/ | ✅ owner | ✅ | 红娘：仅 owner_id = 自己 |

### 4.4 推荐模块

| 接口 | 方法 | 路径 | 红娘 | 管理员 | 附加条件 |
|------|------|------|------|-------|---------|
| 创建推荐 | POST | /recommendations/ | ✅ | ✅ | 红娘：user_id 必须是自己负责的用户 |
| 推荐历史 | GET | /recommendations/ | ✅ 自己的 | ✅ | 红娘：自动过滤 |
| 标记选中 | POST | /.../candidates/{id}/select/ | ✅ 发起人 | ✅ | 红娘：批次的 staff_id = 自己 |
| 关闭批次 | POST | /recommendations/{id}/close/ | ✅ 发起人 | ✅ | 红娘：批次的 staff_id = 自己 |
| 候选搜索 | GET | /.../candidate-search/ | ✅ | ✅ | 自动过滤暂停/配对中/同性/已删除用户 |

### 4.5 配对卡模块

| 接口 | 方法 | 路径 | 红娘 | 管理员 | 附加条件 |
|------|------|------|------|-------|---------|
| 创建配对卡 | POST | /match-cards/ | ✅ | ✅ | — |
| 配对卡列表 | GET | /match-cards/ | ✅ 涉及自己的 | ✅ 全部 | 红娘：male/female/primary_staff_id 任一 = 自己 |
| 配对卡详情 | GET | /match-cards/{id}/ | ✅ 涉及自己的 | ✅ | 同上 |
| 推进阶段 | POST | /match-cards/{id}/advance-stage/ | ✅ 主操作 | ✅ | 红娘：primary_staff_id = 自己 |
| 设置风险 | POST | /match-cards/{id}/set-risk/ | ✅ 涉及自己的 | ✅ | 红娘：三个红娘字段任一 = 自己 |
| 结束配对 | POST | /match-cards/{id}/end/ | ✅ 主操作 | ✅ | 红娘：primary_staff_id = 自己 |
| 更新反馈热度 | PATCH | /match-cards/{id}/ | ✅ 见4.6 | ✅ | 字段级权限控制，见下方详细矩阵 |

### 4.6 配对卡字段级权限

| 字段 | 男方红娘 | 女方红娘 | 主操作红娘 | 管理员 | 判定条件 |
|------|---------|---------|-----------|-------|---------|
| male_feedback（读） | ✅ | ✅ | ✅ | ✅ | — |
| male_feedback（写） | ✅ | ❌ | ✅ | ✅ | male_staff_id = 自己 或 primary_staff_id = 自己 |
| female_feedback（读） | ✅ | ✅ | ✅ | ✅ | — |
| female_feedback（写） | ❌ | ✅ | ✅ | ✅ | female_staff_id = 自己 或 primary_staff_id = 自己 |
| male_heat（读） | ✅ | ✅ | ✅ | ✅ | — |
| male_heat（写） | ✅ | ❌ | ✅ | ✅ | male_staff_id = 自己 或 primary_staff_id = 自己 |
| female_heat（读） | ✅ | ✅ | ✅ | ✅ | — |
| female_heat（写） | ❌ | ✅ | ✅ | ✅ | female_staff_id = 自己 或 primary_staff_id = 自己 |
| staff_judgment（读） | ✅ | ✅ | ✅ | ✅ | — |
| staff_judgment（写） | ❌ | ❌ | ✅ | ✅ | primary_staff_id = 自己；通过 PATCH /match-cards/{id}/ 直接更新，不通过跟进记录接口提交 |
| stage（写） | ❌ | ❌ | ✅ | ✅ | 通过 advance-stage 接口 |
| risk_level（写） | ✅ | ✅ | ✅ | ✅ | 通过 set-risk 接口 |

**实现方式：** 在 `matchcard/permissions.py` 中创建 `MatchCardFieldPermission` 类，PATCH 请求时逐字段检查写权限，无权限的字段从请求体中剥离或返回 403。

### 4.7 跟进记录模块

| 接口 | 方法 | 路径 | 红娘 | 管理员 | 附加条件 |
|------|------|------|------|-------|---------|
| 创建跟进 | POST | /follow-ups/ | ✅ 见下方 | ✅ | 分场景权限控制 |
| 跟进列表 | GET | /follow-ups/ | ✅ 相关的 | ✅ | 红娘：关联的用户或配对卡属于自己 |

**跟进记录创建权限细则：**

| 场景 | 条件 | 说明 |
|------|------|------|
| 未配对跟进 | user.owner_id = 当前 staff.id | 只能给自己负责的用户写跟进 |
| 已配对跟进（男方侧） | match_card.male_staff_id = 当前 staff.id，且 user_id = male_user_id | 男方红娘只能写男方侧单方回访 |
| 已配对跟进（女方侧） | match_card.female_staff_id = 当前 staff.id，且 user_id = female_user_id | 女方红娘只能写女方侧单方回访 |
| 已配对跟进（主操作） | match_card.primary_staff_id = 当前 staff.id | 主操作红娘可写男方或女方任一侧回访 |
| 成功后回访 | match_card.primary_staff_id = 当前 staff.id | success_followup 仅主操作红娘或管理员可创建 |

### 4.8 成功案例模块

| 接口 | 方法 | 路径 | 红娘 | 管理员 | 附加条件 |
|------|------|------|------|-------|---------|
| 发起成功申请 | POST | /success-applications/ | ✅ 主操作 | ✅ | primary_staff_id = 自己 |
| 申请列表 | GET | /success-applications/ | ✅ 自己发起的 | ✅ 全部 | 红娘：applicant_id = 自己 |
| 审核通过 | POST | /.../approve/ | ❌ | ✅ | — |
| 审核驳回 | POST | /.../reject/ | ❌ | ✅ | — |
| 标记失效 | POST | /success-cases/{id}/invalidate/ | ✅ 主操作 | ✅ | primary_staff_id = 自己 |

### 4.9 转移模块

| 接口 | 方法 | 路径 | 红娘 | 管理员 | 附加条件 |
|------|------|------|------|-------|---------|
| 发起转移 | POST | /transfer-requests/ | ✅ | ✅ | 红娘：user.owner_id = 自己（只能转自己的） |
| 转移列表 | GET | /transfer-requests/ | ✅ 自己发起的 | ✅ 全部 | 红娘：from_staff_id = 自己 |
| 审核通过 | POST | /.../approve/ | ❌ | ✅ | — |
| 审核驳回 | POST | /.../reject/ | ❌ | ✅ | — |

### 4.10 提醒模块

| 接口 | 方法 | 路径 | 红娘 | 管理员 | 附加条件 |
|------|------|------|------|-------|---------|
| 我的提醒 | GET | /reminders/ | ✅ 自己的 | ✅ | 红娘：自动注入 staff_id = 自己 |
| 标记已处理 | POST | /reminders/{id}/process/ | ✅ 接收人 | ✅ | reminder.staff_id = 自己 |
| 手动提醒 | POST | /reminders/manual/ | ✅ | ✅ | 红娘：target 必须是自己负责的用户/涉及自己的配对卡 |

### 4.11 首页聚合

| 接口 | 方法 | 路径 | 红娘 | 管理员 | 附加条件 |
|------|------|------|------|-------|---------|
| 红娘首页 | GET | /dashboard/matchmaker/ | ✅ | ❌ | 数据自动按当前 staff_id 过滤 |
| 管理员首页 | GET | /dashboard/admin/ | ❌ | ✅ | — |

### 4.12 操作日志

| 接口 | 方法 | 路径 | 红娘 | 管理员 | 附加条件 |
|------|------|------|------|-------|---------|
| 查看日志 | GET | /operation-logs/ | ❌ | ✅ | — |

### 4.13 配置管理

| 接口 | 方法 | 路径 | 红娘 | 管理员 | 附加条件 |
|------|------|------|------|-------|---------|
| 原因枚举列表 | GET | /reason-enums/ | ✅ | ✅ | 红娘：只能读取，用于表单下拉 |
| 创建原因枚举 | POST | /reason-enums/ | ❌ | ✅ | — |
| 编辑原因枚举 | PATCH | /reason-enums/{id}/ | ❌ | ✅ | — |
| 付费等级列表 | GET | /payment-levels/ | ✅ | ✅ | 红娘：只能读取 |
| 创建付费等级 | POST | /payment-levels/ | ❌ | ✅ | — |
| 编辑付费等级 | PATCH | /payment-levels/{id}/ | ❌ | ✅ | — |

### 4.14 全局搜索

| 接口 | 方法 | 路径 | 红娘 | 管理员 | 附加条件 |
|------|------|------|------|-------|---------|
| 全局搜索 | GET | /search/ | ✅ 范围受限 | ✅ 全部 | 红娘：只能搜到自己负责的 + 涉及自己配对卡的用户 |

---

## 5. 页面访问权限矩阵

### 5.1 PC端页面

| 页面 | 路由 | 红娘 | 管理员 | 说明 |
|------|------|------|-------|------|
| 登录页 | /login | ✅ | ✅ | 未登录可访问 |
| 红娘首页 | /home | ✅ | ❌ | 管理员访问跳转到管理员首页 |
| 未配对池列表 | /unmatched-pool | ✅ | ✅ | 红娘：数据自动按 owner 过滤 |
| 已配对池列表 | /matched-pool | ✅ | ✅ | 红娘：数据自动按涉及自己过滤 |
| 用户详情 | /users/:id | ✅ 有关联 | ✅ | 红娘：无关联时显示无权限 |
| 配对卡详情 | /match-cards/:id | ✅ 涉及自己 | ✅ | 红娘：不涉及时显示无权限 |
| 推荐批次创建 | /recommend/create | ✅ | ✅ | — |
| 全局搜索结果 | /search | ✅ | ✅ | — |
| 管理员首页 | /admin/home | ❌ | ✅ | 红娘访问返回403 |
| 超时总览 | /admin/overdue | ❌ | ✅ | — |
| 转移审批 | /admin/transfers | ❌ | ✅ | — |
| 成功案例审批 | /admin/success | ❌ | ✅ | — |
| 操作日志 | /admin/logs | ❌ | ✅ | — |
| 原因枚举管理 | /admin/reasons | ❌ | ✅ | — |
| 付费等级管理 | /admin/payment-levels | ❌ | ✅ | — |

### 5.2 小程序页面

| 页面 | 红娘 | 管理员 | 说明 |
|------|------|-------|------|
| 登录 | ✅ | ✅ | — |
| 首页（待处理列表） | ✅ | ✅ | 管理员也可在小程序查看，但数据为全店 |
| 用户快速处理 | ✅ 有关联 | ✅ | — |
| 配对卡快速处理 | ✅ 涉及自己 | ✅ | — |
| 写跟进表单 | ✅ | ✅ | 权限同 API 层 BR-FU-003 |

---

## 6. 按钮/操作级权限矩阵

### 6.1 用户详情页

| 按钮/操作 | 红娘 | 管理员 | 显示条件 | 附加约束 |
|-----------|------|-------|---------|---------|
| 编辑资料 | ✅ owner | ✅ | 始终显示 | — |
| 标记已沟通 | ✅ owner | ✅ | pool_status = new_pending | — |
| 发起推荐 | ✅ owner | ✅ | pool_status = communicated_pending_recommend | is_profile_complete = TRUE |
| 标记选中候选人 | ✅ 批次发起人 | ✅ | pool_status = recommended_pending_select | — |
| 创建配对卡 | ✅ | ✅ | pool_status = selected_pending_meet | 对方 is_in_match = FALSE |
| 见面不继续 | ✅ owner | ✅ | pool_status = selected_pending_meet | — |
| 暂停服务 | ✅ owner | ✅ | pool_status IN (S1-S4) | 不在 met_not_continue |
| 恢复服务 | ✅ owner | ✅ | pool_status = paused | — |
| 转移用户 | ✅ owner | ✅ | 始终显示 | — |
| 写跟进 | ✅ owner | ✅ | 始终显示 | — |
| 设置提醒 | ✅ owner | ✅ | 始终显示 | — |
| 强制修改状态 | ❌ | ✅ | 始终显示（仅管理员可见） | 复用 POST /users/{id}/change-status/，必须传 force=true + force_reason |
| 强制修改负责人 | ❌ | ✅ | 始终显示（仅管理员可见） | 复用 PATCH /users/{id}/，修改 owner_id 时必须传 force=true + force_reason |

### 6.2 配对卡详情页

| 按钮/操作 | 男方红娘 | 女方红娘 | 主操作红娘 | 管理员 | 显示条件 |
|-----------|---------|---------|-----------|-------|---------|
| 写跟进（男方） | ✅ | ❌ | ✅ | ✅ | stage IN (M1, M2) |
| 写跟进（女方） | ❌ | ✅ | ✅ | ✅ | stage IN (M1, M2) |
| 写成功后回访 | ❌ | ❌ | ✅ | ✅ | stage = success |
| 填写男方反馈/热度 | ✅ | ❌ | ✅ | ✅ | stage IN (M1, M2) |
| 填写女方反馈/热度 | ❌ | ✅ | ✅ | ✅ | stage IN (M1, M2) |
| 填写综合判断 | ❌ | ❌ | ✅ | ✅ | stage IN (M1, M2) |
| 推进到稳定联系 | ❌ | ❌ | ✅ | ✅ | stage = initial_contact 且男方侧/女方侧各 ≥ 1 条单方有效回访 |
| 设置风险标记 | ✅ | ✅ | ✅ | ✅ | stage IN (M1, M2) |
| 发起成功申请 | ❌ | ❌ | ✅ | ✅ | stage = stable_contact 且存续 ≥ 30天 且无 pending 申请 |
| 结束配对 | ❌ | ❌ | ✅ | ✅ | stage IN (M1, M2) |
| 标记失效 | ❌ | ❌ | ✅ | ✅ | stage = success |
| 设置提醒 | ✅ | ✅ | ✅ | ✅ | stage IN (M1, M2) |

### 6.3 管理员审批页

| 按钮/操作 | 红娘 | 管理员 | 说明 |
|-----------|------|-------|------|
| 通过转移申请 | ❌ | ✅ | status = pending |
| 驳回转移申请 | ❌ | ✅ | status = pending，驳回原因必填 |
| 通过成功申请 | ❌ | ✅ | status = pending |
| 驳回成功申请 | ❌ | ✅ | status = pending，驳回原因必填 |

### 6.4 管理员配置页

| 按钮/操作 | 红娘 | 管理员 | 说明 |
|-----------|------|-------|------|
| 新增原因枚举 | ❌ | ✅ | — |
| 编辑原因枚举 | ❌ | ✅ | — |
| 启用/停用原因枚举 | ❌ | ✅ | — |
| 新增付费等级 | ❌ | ✅ | — |
| 编辑付费等级 | ❌ | ✅ | — |
| 启用/停用付费等级 | ❌ | ✅ | — |

---

## 7. DRF Permission Classes 设计

### 7.1 通用权限类

```python
# utils/permissions.py

class IsAuthenticated(BasePermission):
    """已登录"""
    
class IsAdmin(BasePermission):
    """管理员角色"""
    def has_permission(self, request, view):
        return request.user.role == 'admin'

class IsMatchmaker(BasePermission):
    """红娘角色"""
    def has_permission(self, request, view):
        return request.user.role == 'matchmaker'
```

### 7.2 用户模块权限类

```python
# apps/user/permissions.py

class IsUserOwner(BasePermission):
    """当前红娘是该用户的负责人"""
    def has_object_permission(self, request, view, obj):
        if request.user.role == 'admin':
            return True
        return obj.owner_id == request.user.id

class CanViewUser(BasePermission):
    """能看到该用户：owner 或涉及该用户的配对卡红娘"""
    def has_object_permission(self, request, view, obj):
        if request.user.role == 'admin':
            return True
        if obj.owner_id == request.user.id:
            return True
        # 检查是否有涉及该用户的配对卡
        from apps.matchcard.models import MatchCard
        return MatchCard.objects.filter(
            Q(male_user_id=obj.id) | Q(female_user_id=obj.id),
            Q(male_staff_id=request.user.id) | 
            Q(female_staff_id=request.user.id) | 
            Q(primary_staff_id=request.user.id)
        ).exists()
```

### 7.3 配对卡模块权限类

```python
# apps/matchcard/permissions.py

class IsMatchCardRelated(BasePermission):
    """涉及该配对卡的任一红娘"""
    def has_object_permission(self, request, view, obj):
        if request.user.role == 'admin':
            return True
        return request.user.id in (
            obj.male_staff_id, 
            obj.female_staff_id, 
            obj.primary_staff_id
        )

class IsMatchCardPrimaryStaff(BasePermission):
    """配对卡的主操作红娘"""
    def has_object_permission(self, request, view, obj):
        if request.user.role == 'admin':
            return True
        return obj.primary_staff_id == request.user.id

class MatchCardFieldPermission(BasePermission):
    """配对卡字段级写权限"""
    
    MALE_STAFF_WRITABLE = {'male_feedback', 'male_heat'}
    FEMALE_STAFF_WRITABLE = {'female_feedback', 'female_heat'}
    PRIMARY_STAFF_WRITABLE = {
        'male_feedback', 'male_heat', 
        'female_feedback', 'female_heat', 
        'staff_judgment'
    }
    
    def has_object_permission(self, request, view, obj):
        if request.method not in ('PATCH', 'PUT'):
            return True
        if request.user.role == 'admin':
            return True
            
        staff_id = request.user.id
        requested_fields = set(request.data.keys())
        
        allowed_fields = set()
        if staff_id == obj.male_staff_id:
            allowed_fields |= self.MALE_STAFF_WRITABLE
        if staff_id == obj.female_staff_id:
            allowed_fields |= self.FEMALE_STAFF_WRITABLE
        if staff_id == obj.primary_staff_id:
            allowed_fields |= self.PRIMARY_STAFF_WRITABLE
        
        forbidden = requested_fields - allowed_fields
        if forbidden:
            self.message = f"无权修改以下字段：{', '.join(forbidden)}"
            return False
        return True
```

### 7.4 跟进记录权限类

```python
# apps/followup/permissions.py

class CanCreateFollowUp(BasePermission):
    """跟进记录创建权限"""
    
    def has_permission(self, request, view):
        if request.user.role == 'admin':
            return True
        if request.method != 'POST':
            return True
            
        scene = request.data.get('scene')
        staff_id = request.user.id
        
        if scene == 'unmatched':
            user_id = request.data.get('user_id')
            from apps.user.models import User
            try:
                user = User.objects.get(id=user_id)
                return user.owner_id == staff_id
            except User.DoesNotExist:
                return False
                
        elif scene == 'matched':
            match_card_id = request.data.get('match_card_id')
            user_id = request.data.get('user_id')
            from apps.matchcard.models import MatchCard
            try:
                mc = MatchCard.objects.get(id=match_card_id)
                if staff_id == mc.primary_staff_id:
                    return user_id in (mc.male_user_id, mc.female_user_id)
                if staff_id == mc.male_staff_id:
                    return user_id == mc.male_user_id
                if staff_id == mc.female_staff_id:
                    return user_id == mc.female_user_id
                return False
            except MatchCard.DoesNotExist:
                return False

        elif scene == 'success_followup':
            match_card_id = request.data.get('match_card_id')
            from apps.matchcard.models import MatchCard
            try:
                mc = MatchCard.objects.get(id=match_card_id)
                return mc.primary_staff_id == staff_id
            except MatchCard.DoesNotExist:
                return False

        return False
```

### 7.5 转移/成功申请权限类

```python
# apps/transfer/permissions.py

class CanCreateTransfer(BasePermission):
    """只能转移自己负责的用户"""
    def has_permission(self, request, view):
        if request.user.role == 'admin':
            return True
        if request.method != 'POST':
            return True
        user_id = request.data.get('user_id')
        from apps.user.models import User
        try:
            user = User.objects.get(id=user_id)
            return user.owner_id == request.user.id
        except User.DoesNotExist:
            return False

# apps/success/permissions.py

class CanCreateSuccessApplication(BasePermission):
    """只有主操作红娘可以发起成功申请"""
    def has_permission(self, request, view):
        if request.user.role == 'admin':
            return True
        if request.method != 'POST':
            return True
        match_card_id = request.data.get('match_card_id')
        from apps.matchcard.models import MatchCard
        try:
            mc = MatchCard.objects.get(id=match_card_id)
            return mc.primary_staff_id == request.user.id
        except MatchCard.DoesNotExist:
            return False
```

---

## 8. 各 View 的权限配置速查表

| View | permission_classes |
|------|-------------------|
| StaffMeView | [IsAuthenticated] |
| StaffListView | [IsAuthenticated] |
| UserCreateView | [IsAuthenticated] |
| UserListView | [IsAuthenticated] （queryset 层过滤） |
| UserDetailView | [IsAuthenticated, CanViewUser] |
| UserUpdateView | [IsAuthenticated, IsUserOwner] （service 层额外校验 owner_id / force） |
| UserChangeStatusView | [IsAuthenticated, IsUserOwner] |
| UserPauseView | [IsAuthenticated, IsUserOwner] |
| UserResumeView | [IsAuthenticated, IsUserOwner] |
| RecommendationCreateView | [IsAuthenticated] （service 层校验 owner） |
| RecommendationListView | [IsAuthenticated] （queryset 层过滤） |
| CandidateSelectView | [IsAuthenticated] （service 层校验 batch.staff_id） |
| BatchCloseView | [IsAuthenticated] （service 层校验 batch.staff_id） |
| CandidateSearchView | [IsAuthenticated] |
| MatchCardCreateView | [IsAuthenticated] |
| MatchCardListView | [IsAuthenticated] （queryset 层过滤） |
| MatchCardDetailView | [IsAuthenticated, IsMatchCardRelated] |
| MatchCardAdvanceStageView | [IsAuthenticated, IsMatchCardPrimaryStaff] |
| MatchCardSetRiskView | [IsAuthenticated, IsMatchCardRelated] |
| MatchCardEndView | [IsAuthenticated, IsMatchCardPrimaryStaff] |
| MatchCardUpdateView | [IsAuthenticated, IsMatchCardRelated, MatchCardFieldPermission] |
| FollowUpCreateView | [IsAuthenticated, CanCreateFollowUp] |
| FollowUpListView | [IsAuthenticated] （queryset 层过滤） |
| SuccessApplicationCreateView | [IsAuthenticated, CanCreateSuccessApplication] |
| SuccessApplicationListView | [IsAuthenticated] （queryset 层过滤） |
| SuccessApproveView | [IsAuthenticated, IsAdmin] |
| SuccessRejectView | [IsAuthenticated, IsAdmin] |
| SuccessInvalidateView | [IsAuthenticated, IsMatchCardPrimaryStaff] |
| TransferCreateView | [IsAuthenticated, CanCreateTransfer] |
| TransferListView | [IsAuthenticated] （queryset 层过滤） |
| TransferApproveView | [IsAuthenticated, IsAdmin] |
| TransferRejectView | [IsAuthenticated, IsAdmin] |
| ReminderListView | [IsAuthenticated] （自动按 staff_id 过滤） |
| ReminderProcessView | [IsAuthenticated] （service 层校验 staff_id） |
| ReminderManualView | [IsAuthenticated] |
| DashboardMatchmakerView | [IsAuthenticated, IsMatchmaker] |
| DashboardAdminView | [IsAuthenticated, IsAdmin] |
| OperationLogListView | [IsAuthenticated, IsAdmin] |
| ReasonEnumListView | [IsAuthenticated] |
| ReasonEnumCreateView | [IsAuthenticated, IsAdmin] |
| ReasonEnumUpdateView | [IsAuthenticated, IsAdmin] |
| PaymentLevelListView | [IsAuthenticated] |
| PaymentLevelCreateView | [IsAuthenticated, IsAdmin] |
| PaymentLevelUpdateView | [IsAuthenticated, IsAdmin] |
| GlobalSearchView | [IsAuthenticated] （queryset 层过滤） |

---

## 9. 安全审计检查清单

以下为 Codex 审计时需要重点检查的权限安全点：

| 编号 | 检查项 | 风险等级 | 说明 |
|------|-------|---------|------|
| SEC-001 | 红娘是否只能看到自己负责的用户 | 高 | 检查 UserListView 的 queryset 过滤 |
| SEC-002 | 红娘是否只能看到涉及自己的配对卡 | 高 | 检查 MatchCardListView 的 queryset 过滤 |
| SEC-003 | 非主操作红娘是否无法推进配对卡阶段 | 高 | 检查 IsMatchCardPrimaryStaff |
| SEC-004 | 非主操作红娘是否无法结束配对 | 高 | 检查 MatchCardEndView |
| SEC-005 | 配对卡字段级写权限是否正确 | 高 | 检查 MatchCardFieldPermission |
| SEC-006 | 红娘是否无法审批转移/成功 | 高 | 检查 IsAdmin 在审批 View 上 |
| SEC-007 | 红娘是否无法访问操作日志 | 中 | 检查 OperationLogListView |
| SEC-008 | 红娘是否无法修改原因枚举/付费等级 | 中 | 检查 IsAdmin 在配置 View 上 |
| SEC-009 | 操作日志是否不可修改 | 高 | 检查 OperationLog 模型无 update/delete |
| SEC-010 | 转移申请只能转自己的用户 | 中 | 检查 CanCreateTransfer |
| SEC-011 | 暂停用户不出现在候选搜索中 | 中 | 检查 CandidateSearchView 过滤 |
| SEC-012 | 全局搜索是否按数据边界过滤 | 中 | 检查 GlobalSearchView queryset |
| SEC-013 | JWT Token 是否正确验证过期 | 高 | 检查 simplejwt 配置 |
| SEC-014 | 小程序端 API 是否走同一套权限 | 高 | 确认无独立绕过路径 |
| SEC-015 | 管理员页面路由是否有前端守卫 | 中 | 检查 React Router + 后端双重校验 |

---

## 10. 版本记录

| 版本 | 日期 | 修改内容 |
|-----|------|---------|
| v1.1.1 | 2026-03-14 | 统一 force 权限口径，并将用户详情可见范围与示例代码统一为"涉及任意历史/当前配对卡的红娘可见" |
| v1.0 | — | 初始版本，覆盖全部 API、页面、按钮权限 + DRF Permission Classes 设计 + 审计检查清单 |
