# 联调执行单 v1

适用阶段：
- P0 已全部完成
- P1 已完成
- 当前用于前端 / 调用方 / 测试 / 协作者联调执行

使用说明：
- 每条场景执行后标记：`通过 / 失败 / 阻塞`
- 若失败或阻塞，按文末“联调阻塞项记录模板”登记
- 建议按本文顺序执行，减少前置依赖冲突

当前归档结论：
- 截至 2026-03-20，前端联调阶段目标已达成
- 用户、recommendation、match card 详情、matched followup、reminder、success、transfer、dashboard 已完成真实联调并收口
- 当前无 blocker
- 本文后续内容保留为联调基线执行记录，不再作为“未完成联调项”使用

---

## 一、基础数据与用户视图

| 模块 | 场景名称 | 角色 | 前置数据 | 操作步骤 | 关键接口 | 预期结果 | 失败时记录项 | 是否 blocker |
|---|---|---|---|---|---|---|---|---|
| 用户详情 | 查看用户详情 | admin / 当前 owner | 已存在 1 个用户，资料字段完整 | 进入用户详情页并刷新 | `GET /api/v1/users/{id}/` | 返回真实详情，不是占位数据；字段完整、可展示 | 用户ID、角色、返回字段缺失项、响应体 | 是 |
| 用户列表 | priority_score 排序 | admin / matchmaker | 至少 3 个用户，priority_score 有明显差异 | 按 `priority_score` 排序查看列表顺序 | `GET /api/v1/users/?ordering=priority_score` | 列表顺序与 priority_score 一致 | 查询参数、返回顺序、各用户 score | 否 |

## 二、推荐搜索与推荐历史

| 模块 | 场景名称 | 角色 | 前置数据 | 操作步骤 | 关键接口 | 预期结果 | 失败时记录项 | 是否 blocker |
|---|---|---|---|---|---|---|---|---|
| 候选搜索 | candidate-search 正常命中 | admin / 当前 owner | 目标用户 1 个；存在符合条件候选 2 个 | 以 `user_id + search/city/age` 搜索 | `GET /api/v1/recommendations/candidate-search/` | 返回候选命中；字段包含 `id/name/gender/age/city/payment_level_name/pool_status_display/is_profile_complete/duplicate_warning` | user_id、搜索参数、返回结果、缺失字段 | 是 |
| 候选搜索 | candidate-search 空结果 | admin / 当前 owner | 搜索关键词无匹配 | 用不存在关键词搜索 | `GET /api/v1/recommendations/candidate-search/` | 返回空列表，分页结构正常 | 查询参数、返回体 | 否 |
| 候选搜索 | candidate-search 过滤非法候选 | admin / 当前 owner | 存在暂停中、已在配对中、同性、本人等用户 | 搜索同一批数据 | `GET /api/v1/recommendations/candidate-search/` | 非法候选不会出现在结果中 | 非法候选用户ID、实际返回项 | 是 |
| 推荐历史 | admin 查看任意用户推荐历史 | admin | 某用户已有推荐批次历史 | 进入推荐历史页 | `GET /api/v1/recommendations/?user_id={id}` | admin 可见该用户推荐历史；当前接口返回裸列表，不是分页结构 | user_id、角色、返回体 | 否 |
| 推荐历史 | 当前 owner 查看推荐历史 | 当前 owner | 用户 owner 已指向当前红娘；历史批次可由其他人创建 | 进入推荐历史页 | `GET /api/v1/recommendations/?user_id={id}` | 当前 owner 可见历史记录；当前接口返回裸列表，不是分页结构 | user_id、owner_id、batch 创建者、返回体 | 是 |
| 推荐历史 | 非 owner 不可见 | 非 owner matchmaker | 用户 owner 非当前人 | 访问同一用户推荐历史 | `GET /api/v1/recommendations/?user_id={id}` | 返回无权限或空数据，不能看到历史；当前接口返回裸列表，不是分页结构 | user_id、当前 staff、响应码、响应体 | 是 |

## 三、推荐批次与选中主链

| 模块 | 场景名称 | 角色 | 前置数据 | 操作步骤 | 关键接口 | 预期结果 | 失败时记录项 | 是否 blocker |
|---|---|---|---|---|---|---|---|---|
| 推荐批次 | 创建 recommendation batch | admin / 当前 owner | 目标用户存在；搜索已找到候选 | 提交推荐候选列表创建批次 | `POST /api/v1/recommendations/` | 批次创建成功，候选列表生成 | 请求体、响应体、批次ID | 是 |
| 推荐选中 | 首次选中 candidate 成功 | admin / 当前 owner | 批次已创建，至少 2 个候选未选中 | 点击某候选“选中” | `POST /api/v1/recommendations/candidates/{id}/select/` | 选中成功；目标记录变为 selected | candidate_id、batch_id、响应体 | 是 |
| 推荐选中 | 同一 batch 二次选中失败 | admin / 当前 owner | 同一 batch 已有 1 个 candidate 被选中 | 再点另一候选“选中” | `POST /api/v1/recommendations/candidates/{id}/select/` | 稳定失败；不能出现第二个 selected | batch_id、首次 selected candidate_id、第二次 candidate_id、错误码 | 是 |
| 推荐关闭 | 关闭推荐批次 | admin / 当前 owner | 存在未关闭批次 | 执行关闭 | `POST /api/v1/recommendations/batches/{id}/close/` | 批次关闭成功；后续不可继续选中 | batch_id、响应体 | 否 |

## 四、配对卡建卡

| 模块 | 场景名称 | 角色 | 前置数据 | 操作步骤 | 关键接口 | 预期结果 | 失败时记录项 | 是否 blocker |
|---|---|---|---|---|---|---|---|---|
| 配对卡 | 从 selected candidate 建卡成功 | admin / 当前 owner | 已有 selected candidate，且未建卡 | 执行建卡 | `POST /api/v1/match-cards/` | 建卡成功，生成 match_card；按当前实现，至少一方处于 `selected_pending_meet` 即可建卡 | candidate_id、match_card_id、响应体 | 是 |
| 配对卡 | 已处理 candidate 不可重复建卡 | admin / 当前 owner | 同一 selected candidate 已经建过卡 | 再次建卡 | `POST /api/v1/match-cards/` | 稳定失败，不会重复建卡 | candidate_id、错误码、响应体 | 是 |

## 五、跟进三类场景

| 模块 | 场景名称 | 角色 | 前置数据 | 操作步骤 | 关键接口 | 预期结果 | 失败时记录项 | 是否 blocker |
|---|---|---|---|---|---|---|---|---|
| 跟进 | unmatched 跟进 | admin / 当前 owner | 用户处于未配对池可跟进状态 | 新增未配对跟进 | `POST /api/v1/follow-ups/` | `scene="unmatched"` 创建成功 | user_id、请求体、响应体 | 是 |
| 跟进 | matched 跟进在 initial_contact 允许 | admin / 当前 owner | match_card.stage=`initial_contact` | 新增 matched 跟进 | `POST /api/v1/follow-ups/` | 创建成功 | match_card_id、stage、请求体 | 是 |
| 跟进 | matched 跟进在 stable_contact 允许 | admin / 当前 owner | match_card.stage=`stable_contact` | 新增 matched 跟进 | `POST /api/v1/follow-ups/` | 创建成功 | match_card_id、stage、请求体 | 是 |
| 跟进 | success_pending_review 禁止 matched | admin / 当前 owner | match_card.stage=`success_pending_review` | 新增 matched 跟进 | `POST /api/v1/follow-ups/` | 稳定失败，不能落库 | match_card_id、stage、错误码、响应体 | 是 |
| 跟进 | success 后 success_followup 允许 | admin / 当前 owner | match_card.stage=`success` | 新增 success_followup | `POST /api/v1/follow-ups/` | 创建成功 | match_card_id、scene、响应体 | 是 |
| 跟进 | success 后 matched 禁止 | admin / 当前 owner | match_card.stage=`success` | 新增 matched 跟进 | `POST /api/v1/follow-ups/` | 稳定失败 | match_card_id、错误码、响应体 | 是 |

## 六、提醒创建 / 处理 / 过期

| 模块 | 场景名称 | 角色 | 前置数据 | 操作步骤 | 关键接口 | 预期结果 | 失败时记录项 | 是否 blocker |
|---|---|---|---|---|---|---|---|---|
| 提醒 | 创建 manual reminder | admin / 当前 owner | 用户或配对卡存在 | 新建手动提醒 | `POST /api/v1/reminders/manual/` | 创建成功，状态为 pending | target_type、target_id、请求体、响应体 | 是 |
| 提醒 | 处理 user reminder | admin / 当前 owner | 存在 pending 的 user reminder | 执行处理 | `POST /api/v1/reminders/{id}/process/` | 处理成功，状态更新为 processed | reminder_id、响应体 | 是 |
| 提醒 | 处理 match_card reminder | admin / 当前 owner | match_card 未 ended，存在 pending reminder | 执行处理 | `POST /api/v1/reminders/{id}/process/` | 处理成功；必要时回写 last_action_at / created_follow_up_id | reminder_id、match_card_id、响应体 | 是 |
| 提醒 | ended 配对卡 reminder 禁止处理 | admin / 当前 owner | match_card.stage=`ended`，存在历史残留 pending reminder | 执行处理 | `POST /api/v1/reminders/{id}/process/` | 稳定失败；不写 processed_at、不建 followup | reminder_id、match_card_id、错误码、处理前后数据 | 是 |
| 提醒 | first_meet_overdue 自动补跟进 | admin / 当前 owner | 存在 `first_meet_overdue` pending reminder | 执行处理 | `POST /api/v1/reminders/{id}/process/` | 处理成功；自动创建 followup；返回 `created_follow_up_id` | reminder_id、created_follow_up_id、响应体 | 是 |
| 提醒 | 过期提醒不再可处理 | admin / 当前 owner | 存在 expired reminder | 再次处理 | `POST /api/v1/reminders/{id}/process/` | 稳定失败 | reminder_id、状态、错误码 | 否 |

## 七、成功审批与成功后跟进

| 模块 | 场景名称 | 角色 | 前置数据 | 操作步骤 | 关键接口 | 预期结果 | 失败时记录项 | 是否 blocker |
|---|---|---|---|---|---|---|---|---|
| 成功审批 | 发起成功申请 | admin / 当前 owner | match_card 处于可申请成功阶段 | 提交成功申请 | `POST /api/v1/success-applications/` | 申请创建成功，match_card 进入 `success_pending_review` | match_card_id、请求体、响应体 | 是 |
| 成功审批 | 审批通过进入 success | admin | 已有待审批成功申请 | 执行 approve | `POST /api/v1/success-applications/{id}/approve/` | match_card 进入 `success`；生成 success_revisit | application_id、match_card_id、响应体 | 是 |
| 成功审批 | 成功案例失效 | admin / primary_staff | 已有 active success_case | 执行 invalidate | `POST /api/v1/success-cases/{id}/invalidate/` | success_case 失效，match_card 进入 `ended` | success_case_id、请求体、响应体 | 否 |
| 成功审批 | 旧 match manual reminder 被清理 | admin | approve 前该 match_card 下存在 pending manual reminder | 审批通过后检查旧 reminder | `POST /api/v1/success-applications/{id}/approve/` + `GET /api/v1/reminders/` | 旧 match 阶段 manual reminder 不再处于可处理状态 | application_id、旧 reminder_id、审批前后状态 | 是 |
| 成功跟进 | success_followup 正常可写 | admin / 当前 owner | match_card.stage=`success` | 新增 success_followup | `POST /api/v1/follow-ups/` | 创建成功 | match_card_id、请求体、响应体 | 是 |

## 八、转移审批主链

| 模块 | 场景名称 | 角色 | 前置数据 | 操作步骤 | 关键接口 | 预期结果 | 失败时记录项 | 是否 blocker |
|---|---|---|---|---|---|---|---|---|
| 转移审批 | 发起转移 | admin / 当前 owner | 用户已存在且可转移 | 提交转移申请 | `POST /api/v1/transfer-requests/` | 申请创建成功 | user_id、请求体、响应体 | 是 |
| 转移审批 | 审批通过后 owner 变更 | admin | 存在待审批转移申请 | 执行 approve | `POST /api/v1/transfer-requests/{id}/approve/` | 用户 owner 更新为新红娘 | transfer_id、审批前后 owner_id | 是 |
| 转移后联动 | 新 owner 可继续看推荐历史与详情 | 新 owner | 转移已完成 | 打开用户详情与推荐历史 | `GET /api/v1/users/{id}/` + `GET /api/v1/recommendations/?user_id={id}` | 新 owner 可见详情与推荐历史 | user_id、新 owner_id、响应体 | 是 |

## 九、Dashboard 联调

| 模块 | 场景名称 | 角色 | 前置数据 | 操作步骤 | 关键接口 | 预期结果 | 失败时记录项 | 是否 blocker |
|---|---|---|---|---|---|---|---|---|
| Dashboard | 红娘首页统计 | 当前 owner / matchmaker | 准备一组有 overdue / pending_visit / today_processed / recent_new 的数据 | 打开首页 | `GET /api/v1/dashboard/matchmaker/` | 返回 `unmatched_overdue / matched_pending_visit / today_processed / recent_new`，其中 `today_processed` 表示今天创建的 followup 数 | 请求参数、响应体、缺失字段 | 是 |
| Dashboard | overdue_type 口径确认 | 当前 owner / matchmaker | 存在未配对超时数据 | 查看 `unmatched_overdue.items` | `GET /api/v1/dashboard/matchmaker/` | `overdue_type` 口径为 `跟进超时` | item 数据、实际文案 | 否 |
| Dashboard | 管理员首页汇总 | admin | 系统内存在多类超时数据 | 打开管理员首页 | `GET /api/v1/dashboard/admin/` | 返回 `overdue_summary` | 响应体、缺失字段 | 是 |
| Dashboard | items 与统计一致 | admin / 当前 owner | 已准备可核对样本数据 | 比对卡片统计与 items 明细 | `GET /api/v1/dashboard/matchmaker/` / `GET /api/v1/dashboard/admin/` | 统计值与明细数量、口径一致 | 场景数据、统计值、明细列表 | 是 |

## 十、操作日志抽样核对

| 模块 | 场景名称 | 角色 | 前置数据 | 操作步骤 | 关键接口 | 预期结果 | 失败时记录项 | 是否 blocker |
|---|---|---|---|---|---|---|---|---|
| 操作日志 | 跟进创建日志 | admin / 当前 owner | 完成 1 次 followup 创建 | 查询操作日志 | `GET /api/v1/operation-logs/` | 存在 `follow_up_created`，且能关联 followup | follow_up_id、action、target_type、target_id、after_json | 否 |
| 操作日志 | first_meet_overdue 自动补跟进日志 | admin / 当前 owner | 完成 1 次 `first_meet_overdue` reminder 处理 | 查询操作日志 | `GET /api/v1/operation-logs/` | 自动创建的 followup 也有 `follow_up_created` | reminder_id、created_follow_up_id、日志明细 | 是 |
| 操作日志 | 成功审批日志 | admin | 完成 1 次 success approve | 查询操作日志 | `GET /api/v1/operation-logs/` | 存在 success 审批相关 canonical action | application_id、action、日志内容 | 否 |
| 操作日志 | 转移审批日志 | admin | 完成 1 次 transfer approve | 查询操作日志 | `GET /api/v1/operation-logs/` | 存在 transfer 审批相关 canonical action | transfer_id、action、日志内容 | 否 |

---

## 建议联调顺序

1. 用户详情、用户列表、priority_score
2. candidate-search、recommendation history
3. recommendation 创建、选中、建卡
4. followup 三类场景
5. reminder 创建、处理、过期
6. success 审批、success_followup
7. transfer 审批
8. Dashboard
9. operation_log 抽样核对

---

## 当前前端联调收口基线

- 已收口模块：
  - 用户模块
  - recommendation 模块
  - match card 详情
  - matched followup
  - reminder
  - success
  - transfer
  - dashboard
- 上述模块均已真实联调通过并完成收口
- 当前无 blocker
- 企业微信通知 phase 1 后端真实验收补证已完成，归档记录见 [13_wecom_smoke_validation.md](/mnt/d/project/User_management_system/docs/13_wecom_smoke_validation.md) §6
- `success_rejected` 已补齐 worker 消费证据与 webhook 成功响应证据，最终返回 `errcode=0, errmsg=ok`
- 已知非阻塞遗留项：
  - success approve / invalidate 后存在约 1-2 秒读后延迟
  - 前端已做本地状态同步兜底
  - 该项继续保留在 bug / 风险备注中跟踪

---

## 联调阻塞项记录模板

```md
### 阻塞记录

- 编号：
- 日期：
- 模块：
- 场景名称：
- 执行角色：
- 是否 blocker：是 / 否

### 前置信息

- 环境：
- 用户/数据ID：
- 请求接口：
- 请求参数/请求体：

### 实际结果

- 响应状态码：
- 响应体：
- 页面表现：
- 日志/报错信息：

### 预期结果

- 预期行为：
- 对应接口/规则口径：

### 影响范围判断

- 是否阻塞当前联调主链：
- 影响模块：
- 是否可绕过：
- 临时绕过方式：

### 跟进

- 责任人：
- 结论：
- 修复版本/提交：
- 回归结果：
```
