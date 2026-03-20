# AI红娘配对跟进管理系统 技术选型文档 v1.1

## 1. 文档信息

- 文档名称：技术选型文档
- 版本：v1.1
- 依赖文档：MVP PRD v1.3、数据库设计文档 v1.1
- 文档用途：确定 MVP 阶段的技术栈、架构方案、部署方案，供后续 API 契约、开发、部署使用。

---

## 2. 架构总览

```
┌─────────────────────────────────────────────────────────┐
│                       客户端                              │
│                                                         │
│   ┌─────────────────┐     ┌─────────────────────────┐   │
│   │  PC 管理后台      │     │  微信小程序（红娘端）     │   │
│   │  React + Ant Design│     │  原生微信小程序          │   │
│   │  端口: 3000       │     │                         │   │
│   └────────┬──────────┘     └───────────┬─────────────┘   │
│            │                            │                 │
└────────────┼────────────────────────────┼─────────────────┘
             │         HTTPS / JSON       │
             ▼                            ▼
┌─────────────────────────────────────────────────────────┐
│                     后端 API 层                           │
│                                                         │
│   ┌─────────────────────────────────────────────────┐   │
│   │  Django 5.x + Django REST Framework 3.x         │   │
│   │  Python 3.12+                                   │   │
│   │  端口: 8000                                      │   │
│   └────────┬──────────────┬──────────────┬──────────┘   │
│            │              │              │               │
│            ▼              ▼              ▼               │
│   ┌──────────────┐┌──────────────┐┌──────────────────┐  │
│   │ PostgreSQL   ││  Redis       ││  Celery          │  │
│   │ 16+          ││ 7.x         ││ 定时任务 + 异步队列│  │
│   │ 数据存储      ││ 缓存/会话    ││ 提醒调度          │  │
│   │ 端口: 5432   ││ 端口: 6379  ││                  │  │
│   └──────────────┘└──────────────┘└──────────────────┘  │
│                                                         │
│   ┌──────────────────────────────────────────────────┐  │
│   │  企业微信机器人 Webhook                             │  │
│   │  提醒消息推送                                       │  │
│   └──────────────────────────────────────────────────┘  │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## 3. 后端技术栈

### 3.1 核心框架

| 组件 | 选型 | 版本 | 用途 |
|------|------|------|------|
| 语言 | Python | 3.12+ | — |
| Web框架 | Django | 5.x | 全家桶：ORM、Admin、Auth、Migrations |
| API框架 | Django REST Framework (DRF) | 3.15+ | RESTful API 层，序列化、权限、分页、过滤 |
| 数据库 | PostgreSQL | 16+ | 主数据库，JSON字段、全文搜索原生支持 |
| 缓存 | Redis | 7.x | 会话存储、频率限制、Celery Broker |
| 异步任务 | Celery | 5.x | 定时任务（提醒调度）、异步消息推送 |
| 定时调度 | Celery Beat | — | 每日提醒扫描、汇总消息发送 |
| 消息推送 | 企业微信机器人 Webhook | — | 红娘微信提醒 |

### 3.2 后端依赖包

| 包名 | 用途 |
|------|------|
| djangorestframework | API 层 |
| django-filter | 列表页筛选（未配对池、已配对池的筛选项） |
| django-cors-headers | 跨域支持（前后端分离必需） |
| psycopg[binary] | PostgreSQL 驱动 |
| redis | Redis 客户端 |
| celery[redis] | 异步任务 + Redis 作为 Broker |
| django-celery-beat | 定时任务管理 |
| requests | 企业微信 Webhook 调用 |
| djangorestframework-simplejwt | JWT 认证 |
| drf-spectacular | API 文档自动生成（OpenAPI/Swagger） |
| gunicorn | 生产环境 WSGI 服务器 |
| python-dotenv | 环境变量管理 |

### 3.3 Django 项目结构

```
matchmaker_server/
├── manage.py
├── requirements.txt
├── .env                          # 环境变量（不入Git）
├── config/                       # 项目配置
│   ├── __init__.py
│   ├── settings/
│   │   ├── base.py               # 通用配置
│   │   ├── dev.py                # 开发环境
│   │   └── prod.py               # 生产环境
│   ├── urls.py                   # 根路由
│   ├── celery.py                 # Celery 配置
│   └── wsgi.py
│
├── apps/
│   ├── staff/                    # 红娘/管理员
│   │   ├── models.py
│   │   ├── serializers.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   ├── permissions.py        # 自定义权限类
│   │   └── filters.py
│   │
│   ├── user/                     # 用户档案
│   │   ├── models.py
│   │   ├── serializers.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   ├── filters.py
│   │   └── services.py           # 业务逻辑（状态流转、回流等）
│   │
│   ├── recommendation/           # 推荐批次 + 候选明细
│   │   ├── models.py
│   │   ├── serializers.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   └── services.py
│   │
│   ├── matchcard/                # 配对卡
│   │   ├── models.py
│   │   ├── serializers.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   ├── permissions.py        # 双红娘权限逻辑
│   │   └── services.py           # 阶段流转、结束回流
│   │
│   ├── followup/                 # 跟进记录
│   │   ├── models.py
│   │   ├── serializers.py
│   │   ├── views.py
│   │   └── urls.py
│   │
│   ├── success/                  # 成功案例申请 + 成功案例
│   │   ├── models.py
│   │   ├── serializers.py
│   │   ├── views.py
│   │   └── urls.py
│   │
│   ├── transfer/                 # 用户转移
│   │   ├── models.py
│   │   ├── serializers.py
│   │   ├── views.py
│   │   └── urls.py
│   │
│   ├── reminder/                 # 提醒记录 + 调度逻辑
│   │   ├── models.py
│   │   ├── serializers.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   └── tasks.py              # Celery 定时任务
│   │
│   ├── oplog/                    # 操作日志
│   │   ├── models.py
│   │   ├── serializers.py
│   │   ├── views.py
│   │   └── urls.py
│   │
│   ├── config_mgmt/              # 原因枚举 + 付费等级
│   │   ├── models.py
│   │   ├── serializers.py
│   │   ├── views.py
│   │   └── urls.py
│   │
│   └── notify/                   # 企业微信通知
│       ├── services.py           # Webhook 封装
│       └── tasks.py              # 异步发送任务
│
└── utils/
    ├── enums.py                  # 全局枚举定义
    ├── exceptions.py             # 自定义异常
    ├── pagination.py             # 统一分页
    └── mixins.py                 # 通用 Mixin（软删除等）
```

### 3.4 关键设计约定

#### 认证方案

采用 JWT（JSON Web Token）：
- PC端：登录获取 access_token + refresh_token，存储在内存/httpOnly cookie
- 小程序端：通过微信 openid 换取 JWT token
- access_token 有效期：2 小时
- refresh_token 有效期：7 天

#### API 风格

RESTful，URL 规范：
```
/api/v1/users/                    # 用户列表/创建
/api/v1/users/{id}/               # 用户详情/编辑
/api/v1/users/{id}/pause/         # 用户暂停（自定义动作）
/api/v1/users/{id}/resume/        # 用户恢复
/api/v1/match-cards/              # 配对卡列表/创建
/api/v1/match-cards/{id}/end/     # 结束配对
/api/v1/match-cards/{id}/apply-success/  # 发起成功申请
```

#### 错误响应格式

统一 JSON 格式：
```json
{
  "code": "USER_PROFILE_INCOMPLETE",
  "message": "请先补全资料卡",
  "details": {
    "missing_fields": ["profile_detail"]
  }
}
```

#### 分页格式

```json
{
  "count": 120,
  "page": 1,
  "page_size": 20,
  "results": [...]
}
```

#### 业务逻辑层

所有复杂业务逻辑放在 `services.py` 中，不写在 `views.py` 或 `serializers.py` 里：
- `views.py` 只负责参数接收和响应返回
- `serializers.py` 只负责数据校验和序列化
- `services.py` 负责状态流转、联动操作、权限判断等核心逻辑

这样做的好处是：业务规则集中，Codex审计时只需要重点看 services.py 和 permissions.py。

---

## 4. PC 前端技术栈

### 4.1 核心框架

| 组件 | 选型 | 版本 | 用途 |
|------|------|------|------|
| 框架 | React | 18.x | UI 层 |
| 语言 | TypeScript | 5.x | 类型安全 |
| UI组件库 | Ant Design | 5.x | 管理后台组件（Table、Form、Modal 等） |
| 高级组件 | Ant Design ProComponents | 4.x | ProTable、ProForm 快速搭建列表页和表单页 |
| 路由 | React Router | 6.x | 页面路由 |
| 状态管理 | Zustand | 4.x | 轻量状态管理（比 Redux 简单） |
| HTTP | Axios | 1.x | API 请求封装 |
| 构建工具 | Vite | 5.x | 开发/打包 |

### 4.2 PC 前端项目结构

```
matchmaker_web/
├── package.json
├── vite.config.ts
├── tsconfig.json
├── .env.development
├── .env.production
│
├── public/
│
├── src/
│   ├── main.tsx                   # 入口
│   ├── App.tsx                    # 根组件 + 路由
│   │
│   ├── api/                       # API 层
│   │   ├── client.ts              # Axios 实例（拦截器、Token 注入）
│   │   ├── user.ts                # 用户相关接口
│   │   ├── matchCard.ts           # 配对卡相关接口
│   │   ├── recommendation.ts
│   │   ├── followUp.ts
│   │   ├── success.ts
│   │   ├── transfer.ts
│   │   └── configMgmt.ts
│   │
│   ├── pages/                     # 页面
│   │   ├── home/                  # 红娘首页
│   │   ├── unmatchedPool/         # 未配对池列表
│   │   ├── matchedPool/           # 已配对池列表
│   │   ├── userDetail/            # 用户详情
│   │   ├── matchCardDetail/       # 配对卡详情
│   │   ├── recommend/             # 推荐批次创建
│   │   ├── search/                # 全局搜索结果
│   │   ├── admin/                 # 管理员页面
│   │   │   ├── overdueOverview/   # 超时总览
│   │   │   ├── transferApproval/  # 转移审批
│   │   │   ├── successApproval/   # 成功案例审批
│   │   │   ├── operationLog/      # 操作日志
│   │   │   ├── reasonConfig/      # 原因枚举管理
│   │   │   └── paymentLevel/      # 付费等级管理
│   │   └── login/                 # 登录页
│   │
│   ├── components/                # 通用组件
│   │   ├── FollowUpModal/         # 跟进记录弹窗
│   │   ├── StatusTag/             # 状态标签
│   │   ├── RiskBadge/             # 风险等级标记
│   │   ├── UserCard/              # 用户信息卡片
│   │   └── PageLayout/            # 页面布局框架
│   │
│   ├── stores/                    # Zustand 状态
│   │   ├── authStore.ts           # 登录态
│   │   └── globalStore.ts         # 全局状态（枚举缓存等）
│   │
│   ├── hooks/                     # 自定义 Hooks
│   │   ├── useAuth.ts
│   │   └── usePermission.ts
│   │
│   ├── types/                     # TypeScript 类型定义
│   │   ├── user.ts
│   │   ├── matchCard.ts
│   │   └── common.ts
│   │
│   └── utils/
│       ├── constants.ts           # 枚举常量
│       ├── format.ts              # 格式化工具
│       └── permission.ts          # 权限判断工具函数
```

---

## 5. 微信小程序技术栈

### 5.1 核心框架

| 组件 | 选型 | 说明 |
|------|------|------|
| 框架 | 原生微信小程序 | 无编译层，AI辅助开发质量高 |
| 语言 | JavaScript | 小程序原生支持 |
| UI组件库 | WeUI | 微信官方组件库，风格统一 |
| 网络请求 | wx.request 封装 | 统一封装，自动注入 Token |

### 5.2 小程序页面清单

小程序只做"快速处理"，不做完整后台功能：

```
miniprogram/
├── app.js
├── app.json
├── app.wxss
│
├── pages/
│   ├── login/                     # 登录页（企业微信/手机号登录）
│   ├── home/                      # 首页（今日待处理列表）
│   │   ├── index.js
│   │   ├── index.wxml
│   │   ├── index.wxss
│   │   └── index.json
│   ├── userQuick/                 # 用户快速处理页
│   ├── matchCardQuick/            # 配对卡快速处理页
│   └── followUpForm/              # 写跟进表单页
│
├── components/
│   ├── status-tag/                # 状态标签
│   ├── risk-badge/                # 风险标记
│   └── remind-card/               # 提醒卡片
│
├── utils/
│   ├── api.js                     # API 封装（统一请求、Token 注入）
│   ├── auth.js                    # 登录态管理
│   └── constants.js               # 枚举常量
│
└── config/
    └── env.js                     # 环境变量（API 地址等）
```

### 5.3 小程序与PC端的功能边界

| 功能 | PC端 | 小程序 |
|------|------|--------|
| 新用户建档 | ✅ | ❌ |
| 未配对池列表/筛选 | ✅ | ❌ |
| 已配对池列表/筛选 | ✅ | ❌ |
| 用户完整详情 | ✅ | ❌（摘要展示） |
| 配对卡完整详情 | ✅ | ❌（摘要展示） |
| 推荐批次创建 | ✅ | ❌ |
| 全局搜索 | ✅ | ❌ |
| 今日待处理列表 | ✅ | ✅ |
| 写跟进记录 | ✅ | ✅ |
| 标记已处理 | ✅ | ✅ |
| 改状态 | ✅ | ✅（快速操作） |
| 设置下次提醒 | ✅ | ✅ |
| 管理员审批 | ✅ | ❌ |
| 管理员配置 | ✅ | ❌ |
| 操作日志查看 | ✅ | ❌ |

原则：**小程序只做"收到提醒 → 快速处理"闭环，复杂操作回PC端。**

---

## 6. 企业微信提醒方案

### 6.1 实现方式

使用企业微信群机器人 Webhook，通过 HTTP POST 发送消息。

### 6.2 Webhook 配置

```python
# config
WECHAT_WEBHOOK_URL = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key={机器人KEY}"
```

### 6.3 消息发送封装

```python
# apps/notify/services.py
import requests

def send_wechat_message(webhook_url: str, content: str):
    """发送企业微信文本消息"""
    payload = {
        "msgtype": "text",
        "text": {
            "content": content
        }
    }
    response = requests.post(webhook_url, json=payload, timeout=5)
    return response.json()

def send_wechat_markdown(webhook_url: str, content: str):
    """发送企业微信 Markdown 消息（支持标题、加粗、链接）"""
    payload = {
        "msgtype": "markdown",
        "markdown": {
            "content": content
        }
    }
    response = requests.post(webhook_url, json=payload, timeout=5)
    return response.json()
```

### 6.4 消息模板

#### 早晚汇总（Markdown格式）

```markdown
**📋 早间工作提醒**
您今日有 **8** 项待处理：
> 未配对超时：<font color="warning">3 人</font>
> 已配对待回访：<font color="info">4 对</font>
> 未首见超时：<font color="warning">1 人</font>

[点击查看详情](https://xxx.com/home)
```

#### 紧急提醒（Markdown格式）

```markdown
**🚨 紧急提醒**
**张某某 × 李某某** 配对卡需要立即处理
> 超时 **5** 天 | 风险等级：<font color="warning">高风险</font>
> 原因：一方降温

[立即处理](https://xxx.com/match-card/123)
```

### 6.5 Celery 定时任务

```python
# apps/reminder/tasks.py

from celery import shared_task
from celery.schedules import crontab

# 每日提醒扫描（凌晨2点执行）
@shared_task
def scan_and_generate_reminders():
    """扫描所有用户和配对卡，生成当日提醒"""
    pass

# 早上汇总（每日9:00）
@shared_task
def send_morning_summary():
    """汇总每个红娘的待处理项，发送企业微信消息"""
    pass

# 晚上汇总（每日20:00）
@shared_task
def send_evening_summary():
    """汇总每个红娘当日未处理的项目，发送企业微信消息"""
    pass

# 紧急提醒检查（每小时执行一次）
@shared_task
def check_urgent_reminders():
    """计算 urgency_score，达到阈值的立即推送"""
    pass


# Celery Beat 定时调度配置
CELERY_BEAT_SCHEDULE = {
    'scan-reminders': {
        'task': 'apps.reminder.tasks.scan_and_generate_reminders',
        'schedule': crontab(hour=2, minute=0),
    },
    'morning-summary': {
        'task': 'apps.reminder.tasks.send_morning_summary',
        'schedule': crontab(hour=9, minute=0),
    },
    'evening-summary': {
        'task': 'apps.reminder.tasks.send_evening_summary',
        'schedule': crontab(hour=20, minute=0),
    },
    'urgent-check': {
        'task': 'apps.reminder.tasks.check_urgent_reminders',
        'schedule': crontab(minute=0),  # 每小时整点
    },
}
```

---

## 7. 部署方案

### 7.1 MVP 阶段部署架构

MVP 阶段采用单服务器部署，降低运维成本：

```
┌─────────────────────────────────────────┐
│           VPS（你的 DMIT VPS 或云服务器）  │
│                                         │
│   ┌─────────────┐  ┌─────────────────┐  │
│   │   Nginx      │  │  PostgreSQL 16  │  │
│   │   反向代理    │  │  端口: 5432     │  │
│   │   静态文件    │  │                 │  │
│   │   SSL        │  └─────────────────┘  │
│   └──────┬──────┘                        │
│          │         ┌─────────────────┐   │
│          ▼         │  Redis 7        │   │
│   ┌─────────────┐  │  端口: 6379     │   │
│   │  Gunicorn    │  └─────────────────┘   │
│   │  Django API  │                        │
│   │  端口: 8000  │  ┌─────────────────┐   │
│   └─────────────┘  │  Celery Worker   │   │
│                    │  + Celery Beat   │   │
│                    └─────────────────┘   │
└─────────────────────────────────────────┘
```

### 7.2 Nginx 职责

- 反向代理 Django API（/api/ → localhost:8000）
- 托管 React 打包后的静态文件（/ → /var/www/matchmaker_web/dist/）
- SSL 证书（Let's Encrypt）
- Gzip 压缩

### 7.3 进程管理

使用 systemd 管理所有服务进程：

| 服务 | systemd 服务名 | 说明 |
|------|---------------|------|
| Django API | matchmaker-api.service | Gunicorn 4 workers |
| Celery Worker | matchmaker-worker.service | 并发数 4 |
| Celery Beat | matchmaker-beat.service | 定时调度（单进程） |

### 7.4 数据备份

- PostgreSQL：每日凌晨 pg_dump 全量备份
- 备份文件保留 7 天
- 备份脚本通过 cron 执行

---

## 8. 开发环境搭建

### 8.1 本地开发环境要求

| 工具 | 版本 | 用途 |
|------|------|------|
| Python | 3.12+ | 后端 |
| Node.js | 20 LTS | PC前端构建 |
| PostgreSQL | 16+ | 数据库 |
| Redis | 7.x | 缓存和消息队列 |
| 微信开发者工具 | 最新版 | 小程序开发调试 |
| Git | — | 版本控制 |
| Claude Code | — | 主力开发环境 |

### 8.2 环境变量

```bash
# .env（后端）
DEBUG=True
SECRET_KEY=your-secret-key
DATABASE_URL=postgres://user:pass@localhost:5432/matchmaker
REDIS_URL=redis://localhost:6379/0
WECHAT_WEBHOOK_URL=https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx
ALLOWED_HOSTS=localhost,127.0.0.1
CORS_ALLOWED_ORIGINS=http://localhost:3000

# .env.development（PC前端）
VITE_API_BASE_URL=http://localhost:8000/api/v1

# config/env.js（小程序）
const API_BASE_URL = 'http://localhost:8000/api/v1'
```

### 8.3 本地启动命令

```bash
# 后端
cd matchmaker_server
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver

# Celery Worker（另一个终端）
celery -A config worker -l info

# Celery Beat（另一个终端）
celery -A config beat -l info

# PC 前端
cd matchmaker_web
npm install
npm run dev

# 小程序
# 用微信开发者工具打开 miniprogram/ 目录
```

---

## 9. Git 仓库结构

```
ai-matchmaker/
├── matchmaker_server/            # Django 后端
├── matchmaker_web/               # React PC 前端
├── miniprogram/                  # 微信小程序
├── docs/                         # 项目文档
│   ├── 01_mvp_prd_v1.2.md
│   ├── 02_business_flow_v1.0.md
│   ├── 03_database_schema_v1.0.md
│   ├── 04_business_rules_v1.0.md
│   ├── 05_tech_stack_v1.0.md
│   └── ...
├── .gitignore
└── README.md
```

建议使用单仓库（monorepo），三端代码在同一个 Git 仓库中管理，文档也放在 docs/ 目录下。MVP阶段单仓库最简单，后续规模大了再拆。

---

## 10. 安全基线

| 项目 | 措施 |
|------|------|
| 认证 | JWT Token，access 2小时，refresh 7天 |
| 密码存储 | Django 默认 PBKDF2-SHA256 |
| API权限 | DRF Permission Classes，每个视图显式声明 |
| CORS | 白名单配置，仅允许前端域名 |
| SQL注入 | Django ORM 参数化查询（不写裸SQL） |
| XSS | React 默认转义 + DRF 序列化输出 |
| CSRF | 前后端分离 + JWT，禁用 Django CSRF（API场景不适用） |
| 敏感数据 | 环境变量管理，不硬编码 |
| 操作日志 | 不可篡改，数据库层限制 UPDATE/DELETE |
| HTTPS | Nginx + Let's Encrypt |
| 依赖安全 | 上线前 Codex 审计 OWASP Top 10 |

---

## 11. 版本记录

| 版本 | 日期 | 修改内容 |
|-----|------|---------|
| v1.0 | — | 初始版本，确定完整技术栈 |
