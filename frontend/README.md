# PC 管理后台前端

当前为 React + Ant Design 的最小可运行骨架。

## 联调基线

截至 2026-03-20，前端联调阶段目标已达成，当前默认基线如下：
- 用户模块：已收口，真实联调通过
- recommendation 模块：已收口，真实联调通过
- match card 详情：已收口，真实联调通过
- matched followup：已收口，真实联调通过
- reminder：已收口，真实联调通过
- success：已收口，真实联调通过
- transfer：已收口，真实联调通过
- dashboard：已收口，真实联调通过

当前阶段判断：
- 前端联调已进入收尾态
- 当前无 blocker
- 后续工作默认以上述模块已收口为前提，不再重复回到本阶段做扩散性检查

已知非阻塞遗留项：
- success approve / invalidate 后存在约 1-2 秒读后延迟
- 前端已做本地状态同步兜底
- 该项继续保留在 bug / 风险备注中跟踪，不影响当前阶段收口结论

## 本地启动

1. 安装依赖

```bash
npm install
```

2. 启动开发环境

```bash
npm run dev
```

默认开发地址：
- `http://127.0.0.1:5173`

## 后端联通

开发环境默认通过 Vite 代理转发 `/api` 到：
- `http://127.0.0.1:8000`

如需调整，可复制 `.env.example` 自定义：

```bash
VITE_API_BASE_URL=
VITE_API_PROXY_TARGET=http://127.0.0.1:8000
```

## 当前已接入

- `GET /api/v1/users/`
- `GET /api/v1/users/{id}/`
- `ordering=priority_score / -priority_score`
- recommendation / match card / matched followup / reminder / success / transfer / dashboard 已完成真实联调闭环

## 认证说明

当前未接完整登录流。

页面顶部预留了 token 输入框，支持把 Bearer token 的原始值写入本地存储后带到请求头。
