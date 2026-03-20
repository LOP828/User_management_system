# 联调问题记录表 v1

适用阶段：
- 联调执行中
- 前端 / 测试 / 调用方 / 后端协作排障

使用说明：
- 每发现一个问题，新增一条记录
- 若同一问题跨多次回归，保留同一编号并追加回归记录
- 严重程度建议统一使用：`P0 / P1 / P2 / P3`
- 状态建议统一使用：`新建 / 已确认 / 修复中 / 待回归 / 已关闭 / 非问题`

---

## 一、问题登记表

| 编号 | 日期 | 模块 | 场景名称 | 分类 | 严重程度 | 是否 blocker | 提出方 | 执行角色 | 环境 | 关联接口 | 关联对象ID | 问题描述 | 实际结果 | 预期结果 | 当前状态 | 负责人 | 备注 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| INT-001 | 2026-03-19 | followup / reminder / success / transfer | 执行单旧路径偏差 | 联调执行单理解偏差 | P3 | 否 | 后端联调 | admin / matchmaker | 本地联调环境 | follow-ups / reminders/manual / success-applications / success-cases / transfer-requests | - | 执行单中多处接口路径曾使用旧写法，易误导调用方 | 实际接口可用，但旧执行单路径不可直接调用 | 执行单应统一使用真实可调用路径 | 已关闭 | 后端 | 已同步修正到执行单，不属于后端 bug |
| INT-002 | 2026-03-19 | recommendation | recommendation history 返回结构 | 联调执行单理解偏差 | P3 | 否 | 后端联调 | admin / matchmaker | 本地联调环境 | `GET /api/v1/recommendations/?user_id={id}` | user_id | recommendation history 实际返回裸列表，不是分页结构 | 返回为 batch 列表，不含 `count/page/page_size/results` | 联调应按当前实现接裸列表 | 非问题 | 后端 | 已在执行单补充备注 |
| INT-003 | 2026-03-19 | dashboard | today_processed 统计口径 | 联调执行单理解偏差 | P3 | 否 | 后端联调 | matchmaker | 本地联调环境 | `GET /api/v1/dashboard/matchmaker/` | - | `today_processed` 容易被误解成“今日处理 reminder 数” | 当前实现统计“今天创建的 followup 数” | 联调和前端展示应以当前实现口径为准 | 非问题 | 后端 | 已在执行单补充备注 |
| INT-004 | 2026-03-19 | match-card | 建卡前置口径 | 联调执行单理解偏差 | P3 | 否 | 后端联调 | admin / matchmaker | 本地联调环境 | `POST /api/v1/match-cards/` | candidate_id | 建卡规则易被误解成“男女双方都必须 selected_pending_meet” | 当前实现为“至少一方处于 selected_pending_meet 即可” | 联调应按当前实现验证 | 非问题 | 后端 | 已在执行单补充备注 |
| INT-005 | 2026-03-19 | candidate-search | API 文档实现状态 | 文档口径问题 | P3 | 否 | 后端联调 | admin / matchmaker | 本地联调环境 | `GET /api/v1/recommendations/candidate-search/` | - | 基准 API 文档中曾保留“未实现”旧说明 | 实际代码与测试均已可用 | 文档应与当前实现一致 | 已确认 | 后端 | 不阻塞联调，后续文档轮次继续清理 |
| INT-006 | 2026-03-19 | 用户详情 / 用户列表 | 前端第一轮真实接入缺少调用方代码 | 前端接入问题 | P1 | 是 | 前端接入 | admin / matchmaker | 当前仓库 | `GET /api/v1/users/` / `GET /api/v1/users/{id}/` | - | 当前仓库最初未发现前端工程、页面代码、状态管理或请求封装，无法直接开展真实接入 | 仅存在后端与文档，未找到可修改的调用方代码 | 需先提供前端/调用方仓库，或将前端代码纳入当前工作区后再接入 | 已关闭 | 前端 / 项目负责人 | 本轮已在当前仓库内补建 `frontend/` |
| INT-007 | 2026-03-19 | frontend | 本地 dev server 启动受限 | 前端接入问题 | P2 | 是 | 前端接入 | admin / matchmaker | 当前执行环境 | `npm run dev` | - | 当前执行环境默认沙箱拒绝监听本地端口，导致 Vite dev server 无法直接启动 | 非提权执行时出现 `listen EPERM: operation not permitted`；放开宿主机上下文后可正常启动，`curl 127.0.0.1:4173` 返回 200 | 需在允许本地端口监听的环境中做最终浏览器态验证 | 已确认 | 前端 / 环境提供方 | 非代码缺陷，属于当前运行环境限制 |
| INT-008 | 2026-03-19 | frontend / backend | 本地后端服务未启动 | 非阻塞项 | P2 | 是 | 前端接入 | admin / matchmaker | 当前执行环境 | `GET /api/v1/users/` | - | 当前环境未启动后端 8000 服务，无法在此处完成浏览器态真实取数验证 | Django `runserver` 已能跑到数据库检查阶段，但 dev 配置默认连接 PostgreSQL `127.0.0.1:5432`，当前无可用 PostgreSQL 服务，报 `django.db.utils.OperationalError` | 需先提供可用 PostgreSQL 和 `.env`，再启动后端服务进行页面级真实取数联调 | 已确认 | 后端 / 环境提供方 | 非接口缺陷，属联调运行前置条件；仓库内 `local/postgresql-16.4` 为源码目录，非可直接启动实例 |
| INT-009 | 2026-03-20 | success | approve / invalidate 后读后延迟 | 非阻塞项 | P3 | 否 | 前端联调 | admin | 真实 dev 环境 | `POST /api/v1/success-applications/{id}/approve/` / `POST /api/v1/success-cases/{id}/invalidate/` / `GET /api/v1/success-cases/` | success_application_id / success_case_id | success approve 或 invalidate 成功后，列表/详情读取结果约 1-2 秒内可能仍为旧状态 | 写操作成功返回后，紧随其后的读取偶发短暂旧值 | 长期结果应与最终状态一致；当前前端已通过本地状态同步做兜底 | 已确认 | 后端 / 前端 | 保留为非阻塞风险备注，不影响前端联调阶段收口结论 |
| INT-010 | 2026-03-20 | notify / success | 企业微信 phase 1 后端真实验收补证 | 非阻塞项 | P3 | 否 | 后端联调 | admin | Windows + 本机 PostgreSQL + Docker Redis | `notify.send_phase1_event` / `success_rejected` | success_application_id=7 | 本轮目标是补齐企业微信通知真实送达验收证据，不重审已收口主链 | 真实环境下已捕获 worker 消费日志、webhook 发送日志和企业微信成功响应；最终返回 `{'errcode': 0, 'errmsg': 'ok'}` | 企业微信群客户端是否可见不作为后端失败判据；后端侧以 worker 消费和 webhook 成功响应为准 | 已关闭 | 后端 | 详见 [13_wecom_smoke_validation.md](/mnt/d/project/User_management_system/docs/13_wecom_smoke_validation.md) §6 |

---

## 二、当前前端联调归档结论

- 截至 2026-03-20，前端联调阶段目标已达成。
- 已收口并完成真实联调的模块：
  - 用户模块
  - recommendation 模块
  - match card 详情
  - matched followup
  - reminder
  - success
  - transfer
  - dashboard
- 当前无 blocker。
- 企业微信通知 phase 1 后端真实验收补证已完成，已可作为联调基线引用。
- 后续默认以上述模块已收口为前提推进工作，不再将其视为待联调模块。

---

## 三、单条问题详情模板

```md
### 问题编号：BUG-XXX

#### 基本信息
- 日期：
- 模块：
- 场景名称：
- 分类：真实后端 bug / 文档口径问题 / 联调执行单理解偏差 / 非阻塞项
- 严重程度：P0 / P1 / P2 / P3
- 是否 blocker：是 / 否
- 提出方：
- 执行角色：
- 当前状态：新建 / 已确认 / 修复中 / 待回归 / 已关闭 / 非问题
- 负责人：

#### 前置信息
- 环境：
- 用户/数据ID：
- 关联接口：
- 请求参数 / 请求体：
- 页面入口：

#### 实际结果
- 响应状态码：
- 响应体：
- 页面表现：
- 日志 / 报错信息：

#### 预期结果
- 预期行为：
- 对应接口 / 规则口径：

#### 影响范围
- 是否阻塞当前主链：
- 影响模块：
- 是否存在回避路径：
- 临时处理方式：

#### 排查与处理
- 后端结论：
- 前端结论：
- 是否复现稳定：
- 修复版本 / 提交：

#### 回归记录
- 回归时间：
- 回归人：
- 回归环境：
- 回归结果：
- 关闭结论：
```

---

## 四、建议字段填写规范

### 模块建议值
- 用户详情
- 用户列表
- recommendation
- candidate-search
- match-card
- followup
- reminder
- success
- transfer
- dashboard
- operation-log

### 严重程度建议
- `P0`：主链阻断、数据错误、权限越权、不可绕过
- `P1`：核心流程异常，但存在临时绕过
- `P2`：局部功能异常，不阻断主链
- `P3`：展示、文案、低风险体验问题

### 当前状态建议
- `新建`：刚登记，未确认
- `已确认`：已复现并确认属实
- `修复中`：已进入修复
- `待回归`：代码已交付，等待验证
- `已关闭`：回归通过
- `非问题`：最终确认不是缺陷

### 分类建议
- `真实后端 bug`：接口/数据/权限/状态机存在真实缺陷
- `文档口径问题`：代码行为正确，但文档说明落后或冲突
- `联调执行单理解偏差`：执行单或联调口径表述与真实实现不一致
- `非阻塞项`：当前不阻断主链联调或上线，可后续处理

---

## 五、联调日报汇总模板

```md
### 联调问题日报

- 日期：
- 统计范围：

#### 今日新增
- BUG-XXX：
- BUG-XXX：

#### 今日关闭
- BUG-XXX：
- BUG-XXX：

#### 当前 blocker
- BUG-XXX：
- BUG-XXX：

#### 明日重点
- 
```
