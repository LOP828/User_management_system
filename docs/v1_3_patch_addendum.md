# v1.3 修订补丁 追加修正（Addendum）

## 文档信息

- 触发来源：GPT-5.4 对 v1.3 补丁的二次审查
- 状态：4项追加修正，应用后文档进入"可开工"状态
- 使用方式：本文档是 v1_3_downstream_patch.md 的追加件，两份配合使用

---

## ⚠️ 实现状态标注（2026-03-16）

本 Addendum 所有 4 项追加修正已全部吸收进 `matchmaker_server` 代码库：

| 追加修正 | 核心内容 | 实现状态 |
|--------|---------|---------|
| 追加1（同侧计数） | 同一红娘双侧各提交一条跟进，按 user_id 区分 | ✅ followup 服务已按此逻辑实现 |
| 追加2（next_remind_mode） | 跟进请求体新增 next_remind_mode 字段（manual/default） | ✅ FollowUpRecord 已有 next_remind_mode 字段；服务层校验已实现 |
| 追加3（last_unmatched_active_at） | user 表新增字段，有效动作后更新 | ✅ 字段已落地；创建/状态变更/followup/推荐/暂停恢复均已同步 |
| 追加4（汇总表编号） | 补丁汇总表编号从 Issue# 改为补丁序号 | ✅ 文档修正（不涉及代码） |

**注：** `last_unmatched_active_at` 历史存量 NULL 值的一次性 backfill migration 尚未执行（非阻塞，详见 TODO.md 清理项）。

---

## 追加实现对齐说明（2026-03-19）

本次仅做基准文档与现有实现的最小对齐，未引入新需求：

1. **Dashboard 契约状态修正**
   - `06_api_contract_v1_1_2.md` 中 Dashboard 已从“部分实现”修正为“已实现”
   - 红娘端 `unmatched_overdue / matched_pending_visit / today_processed / recent_new`
   - 管理端 `overdue_summary`
   - 均以当前代码与测试口径为准

2. **`overdue_type` 口径修正**
   - Dashboard `unmatched_overdue.items[].overdue_type` 统一以当前实现 `"跟进超时"` 为准
   - 不再使用旧示例中的 `"未首见超时"`

3. **`paused_at` 正式字段补录**
   - `paused_at` 已是 user 表正式字段
   - 进入暂停时写入，恢复时清空
   - `pause_revisit` 扫描的基准时间以 `paused_at` 为起点；若存在暂停后的 unmatched 跟进，则取最近一条跟进时间
   - 该字段与规则已补入 `03_database_schema_v1_1_1.md`、`04_business_rules_v1_1_1.md`

---

## 追加修正 1：同一红娘双侧计数规则矛盾

### 问题

原文写"同时计入双方侧"又写"按 user_id 区分"，逻辑自相矛盾。一条记录只能有一个 user_id，不可能同时属于两侧。

### 修正

**PRD v1.3 §13.7 原文：**

> 若双方红娘是同一人，则该红娘的回访同时计入双方侧。判定时按 follow_up_record.user_id 区分是男方还是女方的回访。

**改为：**

> 若双方红娘是同一人，仍需分别针对男方、女方各提交一条跟进记录。系统按 follow_up_record.user_id 区分所属一侧并分别计数，一条记录不能同时计入双方侧。

**影响文档：**
- 01 PRD v1.3 §13.7
- 04 业务规则 BR-MATCH-003（补丁1中已改的部分，同步更新措辞）

---

## 追加修正 2：默认提醒规则缺少明确字段

### 问题

业务规则写"next_remind_at 或走系统默认规则"，但 API 请求体中没有字段表达这个分支。后端无法区分"用户漏填"和"用户选择走默认"。

### 修正

**06 API契约 §8.1 创建跟进记录 请求体（已配对）改为：**

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

或：

```json
{
  "scene": "matched",
  "match_card_id": 1,
  "user_id": 1,
  "content": "女方反馈：感觉还不错",
  "is_still_contact": "yes",
  "risk_status": "none",
  "next_remind_mode": "default"
}
```

**新增字段说明：**

| 字段 | 类型 | 必填 | 取值 | 说明 |
|------|------|------|------|------|
| next_remind_mode | string | 是（matched/success_followup 场景必填） | manual / default | 提醒方式选择 |
| next_remind_at | datetime | 条件必填 | ISO 8601 | 当 mode=manual 时必填；当 mode=default 时必须为空或不传 |

**校验规则：**
- next_remind_mode = "manual" 且 next_remind_at 为空 → 400 VALIDATION_ERROR "手动提醒模式下必须填写提醒时间"
- next_remind_mode = "default" 且 next_remind_at 非空 → 400 VALIDATION_ERROR "默认规则模式下不应填写提醒时间"
- scene = "unmatched" 时 next_remind_mode 为选填（未配对跟进不强制设提醒）

**影响文档：**
- 04 业务规则 BR-FU-002：将"next_remind_at 或标记走系统默认规则"改为"next_remind_mode 必填，取值 manual/default"
- 06 API契约 §8.1：更新请求体和字段说明
- 03 数据库设计 §4.4 follow_up_record 表：新增 `next_remind_mode VARCHAR(10)` 字段，取值 manual/default/NULL（unmatched场景为NULL）

---

## 追加修正 3：未配对超时 baseline 与有效动作重置对不上

### 问题

baseline 只取"最近跟进记录时间"或"入库时间"，但规则又说"发起推荐"和"更新状态"也重置计时。算法实际上不会重置这两种动作。

### 修正

**03 数据库设计 §4.2 user 表新增字段：**

| 字段名 | 类型 | 是否必填 | 默认值 | 说明 |
|--------|------|---------|--------|------|
| last_unmatched_active_at | TIMESTAMP | 否 | NULL | 未配对阶段最近有效动作时间，用于跟进超时计算 |

创建用户时自动设为 created_at。

**新增索引：** INDEX(last_unmatched_active_at)——提醒扫描定时任务用。

**04 业务规则 BR-REMIND-009 伪代码改为：**

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

**说明：** 此字段仅在用户处于未配对池时更新。用户进入已配对池后不再更新此字段。用户从已配对池回流到未配对池时，last_unmatched_active_at 重置为回流时间。

**影响文档：**
- 01 PRD v1.3 §10.3：将"计算基准"段落改为使用 last_unmatched_active_at
- 03 数据库设计 §4.2：新增字段
- 04 业务规则 BR-REMIND-009：重写伪代码
- 04 业务规则 BR-POOL-006（配对卡结束回流）：在联动操作中追加"设 last_unmatched_active_at = 当前时间"

---

## 追加修正 4：补丁汇总表编号对应错误

### 问题

v1_3_downstream_patch.md 最后的"变更影响汇总"表中，"涉及补丁"列的编号是 Issue 编号（#3, #6, #7），但应该对应的是补丁文档内部的补丁编号（补丁1~7）。

### 修正

**原文汇总表：**

| 文档 | 涉及补丁 |
|------|---------|
| 03 数据库设计 | #3, #6, #7 |
| 04 业务规则 | #1, #3, #6, #7 |
| 06 API契约 | #1, #3, #6 |
| 07 权限矩阵 | #1 |
| 08 开发验收检查清单 | #1, #3, #6, #7 |

**改为：**

| 文档 | 涉及补丁 | 具体内容 |
|------|---------|---------|
| 03 数据库设计 | 补丁2, 补丁3, 补丁4, 追加2, 追加3 | scene枚举+failure_reason_id+followup_timeout_days+next_remind_mode+last_unmatched_active_at |
| 04 业务规则 | 补丁1, 补丁2, 补丁3, 补丁4, 追加1, 追加2, 追加3 | BR-FU-002重写+BR-MATCH-003重写+BR-POOL-002重写+BR-FU-004新增+BR-REMIND-009新增+双侧计数+提醒模式 |
| 06 API契约 | 补丁1, 补丁2, 补丁3, 追加2 | 跟进请求体改+success_followup示例+failure_reason_id示例+next_remind_mode |
| 07 权限矩阵 | 补丁1 | staff_judgment说明 |
| 08 开发验收检查清单 | 补丁1, 补丁2, 补丁3, 补丁4 | 闭环4/6/7/8/9检查项更新 |

---

## 全部修正完成后的文档状态

| 文档 | 版本 | 状态 |
|------|------|------|
| 01 PRD | v1.3 + 追加修正1,3 | ✅ 可开工 |
| 02 业务流程 | v1.0 | ✅ 可开工（无需改） |
| 03 数据库设计 | v1.0 + 补丁2,3,4 + 追加2,3 | ✅ 可开工 |
| 04 业务规则 | v1.0 + 补丁1,2,3,4 + 追加1,2,3 | ✅ 可开工 |
| 05 技术选型 | v1.0 | ✅ 可开工（无需改） |
| 06 API契约 | v1.0 + 补丁1,2,3 + 追加2 | ✅ 可开工 |
| 07 权限矩阵 | v1.0 + 补丁1 | ✅ 可开工 |
| 08 开发验收检查清单 | v1.0 + 补丁1,2,3,4 | ✅ 可开工 |
