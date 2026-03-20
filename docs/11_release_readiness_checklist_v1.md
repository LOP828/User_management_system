# 上线前检查清单 v1

适用阶段：
- 联调完成后
- 发布前检查

使用说明：
- 每项标记：`通过 / 不通过 / 不适用`
- 若“不通过”，必须记录责任人与预计处理时间
- `是否 blocker` 为“是”的项目未通过时，不应进入正式发布

当前状态：
- 后端主链九组联调已完成，当前结论为“后端主链可联调通过”
- 前端联调阶段目标已达成，用户 / recommendation / match card detail / matched followup / reminder / success / transfer / dashboard 均已真实联调通过并收口
- 企业微信通知 phase 1 后端真实验收补证已完成，归档记录见 [13_wecom_smoke_validation.md](/mnt/d/project/User_management_system/docs/13_wecom_smoke_validation.md) §6
- 当前剩余问题均为非阻塞项或文档/执行单口径对齐项，不属于已确认主链缺陷

---

## 一、主链功能检查

| 分类 | 检查项 | 检查内容 | 验证方式 | 责任角色 | 是否 blocker | 结果 | 备注 |
|---|---|---|---|---|---|---|---|
| recommendation | 推荐搜索可用 | `candidate-search` 可正常返回合法候选，过滤非法候选 | 按联调执行单回归 | 前端 / 测试 / 后端 | 是 | 通过 | 主链联调通过 |
| recommendation | 推荐批次主链可用 | 创建批次、选中候选、关闭批次正常 | 按联调执行单回归 | 前端 / 测试 / 后端 | 是 | 通过 | 主链联调通过 |
| recommendation | 推荐历史权限正确 | admin 可见、当前 owner 可见、非 owner 不可见 | 按联调执行单回归 | 测试 / 后端 | 是 | 通过 | 当前接口为裸列表，非分页 |
| match-card | 建卡主链可用 | selected candidate 可成功建卡，已处理 candidate 不可重复建卡 | 按联调执行单回归 | 前端 / 测试 / 后端 | 是 | 通过 | 按当前实现，至少一方 `selected_pending_meet` 即可 |
| followup | 三类跟进可用 | unmatched / matched / success_followup 规则正确 | 按联调执行单回归 | 前端 / 测试 / 后端 | 是 | 通过 | 路径为 `/api/v1/follow-ups/` |
| reminder | 提醒主链可用 | 创建、处理、过期、自动补跟进正常 | 按联调执行单回归 | 前端 / 测试 / 后端 | 是 | 通过 | manual 创建路径为 `/api/v1/reminders/manual/` |
| success | 成功审批主链可用 | 发起、审批通过、success_followup 正常 | 按联调执行单回归 | 前端 / 测试 / 后端 | 是 | 通过 | invalidate 路径为 `/api/v1/success-cases/{id}/invalidate/` |
| transfer | 转移审批主链可用 | 发起、审批通过、owner 联动正常 | 按联调执行单回归 | 前端 / 测试 / 后端 | 是 | 通过 | 路径为 `/api/v1/transfer-requests/...` |
| dashboard | Dashboard 可用 | 红娘首页、管理员首页统计和明细正常 | 按联调执行单回归 | 前端 / 测试 / 后端 | 是 | 通过 | `today_processed`=今天创建的 followup 数 |
| user | 用户详情与排序可用 | User Detail 真实返回，priority_score 排序正常 | 按联调执行单回归 | 前端 / 测试 / 后端 | 否 | 通过 | 基础链路通过 |

---

## 二、关键规则与收口项检查

| 分类 | 检查项 | 检查内容 | 验证方式 | 责任角色 | 是否 blocker | 结果 | 备注 |
|---|---|---|---|---|---|---|---|
| followup | matched 阶段守卫 | `success_pending_review` 不允许写 `matched`；`success` 只允许 `success_followup` | 场景回归 | 测试 / 后端 | 是 | 通过 | P0 收口已验证 |
| reminder | ended 提醒守卫 | ended 配对卡 reminder 不可再 process | 场景回归 | 测试 / 后端 | 是 | 通过 | P0 收口已验证 |
| reminder | success approve 后旧 manual 已清理 | 旧 match 阶段 manual reminder 不再可处理 | 场景回归 | 测试 / 后端 | 是 | 通过 | P0 收口已验证 |
| reminder | first_meet_overdue 自动补跟进审计 | 自动创建 followup 时存在 `follow_up_created` | 场景回归 + operation_log 抽样 | 测试 / 后端 | 是 | 通过 | P0 收口已验证 |
| recommendation | batch 单选约束 | 同一 batch 不会出现多个 selected | 场景回归 | 测试 / 后端 | 是 | 通过 | 应用层与数据层约束均已验证 |

---

## 三、权限与数据边界检查

| 分类 | 检查项 | 检查内容 | 验证方式 | 责任角色 | 是否 blocker | 结果 | 备注 |
|---|---|---|---|---|---|---|---|
| recommendation | history 权限 | admin / 当前 owner / 非 owner 结果正确 | 联调回归 | 测试 / 后端 | 是 | 通过 | 联调已验证 |
| candidate-search | 搜索权限 | admin 可用；当前 owner 仅对自己负责用户可搜索 | 联调回归 | 测试 / 后端 | 是 | 通过 | 联调已验证 |
| transfer | owner 联动 | 转移后新 owner 可访问详情与推荐历史 | 联调回归 | 测试 / 后端 | 是 | 通过 | 联调已验证 |
| operation-log | 审计线一致性 | 核心动作可查到对应 canonical action | 抽样核对 | 测试 / 后端 | 否 | 通过 | 抽样核对通过 |

---

## 四、接口与返回结构检查

| 分类 | 检查项 | 检查内容 | 验证方式 | 责任角色 | 是否 blocker | 结果 | 备注 |
|---|---|---|---|---|---|---|---|
| API | 核心接口状态码正确 | 成功 / 失败场景响应码符合预期 | 联调回归 | 前端 / 测试 / 后端 | 是 | 通过 | 联调主链通过 |
| API | 错误码风格一致 | 已知失败场景返回现有业务错误码，不泄漏原始异常 | 联调回归 | 测试 / 后端 | 是 | 通过 | 联调主链通过 |
| API | 分页结构正常 | 列表接口 `count/page/page_size/results` 正常 | 联调回归 | 前端 / 测试 | 否 | 通过 | recommendation history 为裸列表，属当前实现口径 |
| Dashboard | overdue_type 口径正确 | `unmatched_overdue.items[].overdue_type = 跟进超时` | 联调回归 | 前端 / 测试 | 否 | 通过 | 已与实现对齐 |
| notify | 企业微信 webhook 发送链路可用 | worker 可消费任务，webhook 可成功发送并返回 `errcode=0` | 真实环境验收记录核对 | 后端 / 测试 | 否 | 通过 | phase 1 后端侧补证已完成，见 13 文档 §6 |

---

## 五、测试与回归检查

| 分类 | 检查项 | 检查内容 | 验证方式 | 责任角色 | 是否 blocker | 结果 | 备注 |
|---|---|---|---|---|---|---|---|
| 自动化测试 | 全量测试通过 | 当前仓库 pytest 全量通过 | 运行测试 | 后端 | 是 | 通过 | 联调阶段已持续回归通过 |
| 自动化测试 | 关键模块回归通过 | recommendation / followup / reminder / success / transfer / dashboard 回归通过 | 运行专项测试 | 后端 | 是 | 通过 | 各模块专项测试通过 |
| 联调回归 | 联调执行单 blocker 场景通过 | 执行单中 blocker 项全部通过 | 联调记录核对 | 前端 / 测试 / 后端 | 是 | 通过 | 九组联调已完成 |
| 缺陷管理 | blocker 已清零 | 当前 blocker 问题全部关闭或有明确不上线结论 | 问题单核对 | 项目负责人 / 测试 / 后端 | 是 | 通过 | 当前剩余均为非阻塞项 |
| 前端收口 | 前端联调已收口 | user / recommendation / match card detail / matched followup / reminder / success / transfer / dashboard 均已完成真实联调并收口 | 联调归档结论核对 | 前端 / 项目负责人 | 是 | 通过 | 可作为下一阶段默认基线 |

---

## 六、发布准备检查

| 分类 | 检查项 | 检查内容 | 验证方式 | 责任角色 | 是否 blocker | 结果 | 备注 |
|---|---|---|---|---|---|---|---|
| 发布 | 发布版本明确 | 本次发布分支、提交、版本号已确认 | 发布前确认 | 后端 / 项目负责人 | 是 | 通过 | 候选版本基线：`master` / `914d496` / `feat(celery): configure Celery Beat schedule for reminder scan tasks` |
| 发布 | 数据库变更确认 | 是否包含 migration，已确认执行顺序与回滚方案 | 发布前确认 | 后端 | 是 | 通过 | 发布口径：仅按仓库已提交 migration 基线执行标准 `manage.py migrate`；无新增人工 SQL / 强制数据回填动作。TODO 中 `paused_at` 历史数据 backfill 为非阻塞后续清理项，不属于本次发布 blocker |
| 发布 | 环境配置确认 | 关键环境变量、依赖服务、任务调度配置正确 | 发布前确认 | 后端 / 运维 | 是 | 通过 | 正式发布必配：可用 PostgreSQL（`DATABASE_NAME/USER/PASSWORD/HOST/PORT`）、可用 Redis（`REDIS_URL`）、Django `.env` 关键项（`SECRET_KEY`、`ALLOWED_HOSTS`、`TIME_ZONE`、JWT 时长）、Celery worker 与 beat 常驻；若发布范围包含企业微信 phase 1，则需配置 `WECOM_NOTIFY_ENABLED`、`WECOM_NOTIFY_REMINDER_DUE_ENABLED`、真实 `WECOM_WEBHOOK_URL`、`WECOM_NOTIFY_TIMEOUT_SECONDS`。`HTTP_PROXY/HTTPS_PROXY/NO_PROXY` 清理仅属本机联调注意事项，不纳入正式发布 blocker |
| 发布 | 备份与回滚方案 | 有明确回滚方案与责任人 | 发布前确认 | 后端 / 运维 / 项目负责人 | 是 | 通过 | 最小发布口径：发布前必须完成 PostgreSQL 全量备份，并备份当前生效 `.env`/关键配置；发布失败时，最小回滚动作为代码版本回退到发布前提交、恢复发布前 `.env`/服务配置并重启 Django/worker/beat。数据库不单独承诺反向 migration，继续采用“已有迁移基线 + 发布前数据库备份恢复”作为回滚兜底；Redis/Celery 队列状态不单独作为 blocker 级备份要求 |
| 发布 | 发布窗口确认 | 上线时间、观察窗口、通知对象已明确 | 发布前确认 | 项目负责人 | 否 | 通过 | 最小发布口径：正式上线前需由项目负责人明确发布执行人、具体发布时间段与通知对象；发布时间段按低峰窗口执行。发布后观察窗口按本文第七节执行：后端/前端/测试在上线后 0-2 小时观察 API、核心主链与数据状态，项目负责人/业务方在 0-1 天内跟进一线反馈。是否选择夜间或工作日低峰属建议项，不单独纳入 blocker |

---

## 七、上线观察项

| 分类 | 观察项 | 观察内容 | 观察时间 | 责任角色 | 是否 blocker | 结果 | 备注 |
|---|---|---|---|---|---|---|---|
| API | 核心接口错误率 | recommendation / followup / reminder / success / transfer 核心接口是否异常 | 上线后 0-2 小时 | 后端 | 是 |  |  |
| 业务 | 核心主链可用性 | 推荐、建卡、跟进、审批能否正常执行 | 上线后 0-2 小时 | 前端 / 测试 / 后端 | 是 |  |  |
| 数据 | 审计与状态一致性 | operation_log、状态流转、提醒状态是否出现明显异常 | 上线后 0-2 小时 | 后端 | 否 |  |  |
| 反馈 | 一线使用反馈 | 红娘 / 运营是否出现集中阻塞问题 | 上线后 0-1 天 | 项目负责人 / 业务方 | 否 |  |  |

---

## 八、上线结论

```md
### 上线结论

- 检查日期：
- 检查范围：
- blocker 未通过项：
- 非 blocker 未通过项：
- 是否允许上线：是 / 否
- 结论说明：
- 审核人：
```

当前建议结论：
- blocker 未通过项：无
- 非 blocker 未通过项：执行单与基准文档少量口径对齐项；success approve / invalidate 后约 1-2 秒读后延迟已保留在风险备注中
- 是否允许上线：具备进入联调后发布准备的前提条件
