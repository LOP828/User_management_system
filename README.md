# AI红娘配对跟进管理系统

用于红娘团队管理用户、推荐、配对、跟进、提醒、成功审批、转移审批与相关运营协同流程。

## 仓库结构

- `matchmaker_server/`
  Django 后端服务、配置、迁移与后端测试。
- `frontend/`
  PC 管理后台前端工程。
- `docs/`
  项目基线文档、联调记录、发布准备清单与归档文档。

## 快速导航

- [后端说明](./matchmaker_server/README.md)
- [前端说明](./frontend/README.md)
- [文档索引](./docs/README.md)

## 当前文档基线入口

当前默认文档基线、联调基线与发布准备入口统一从 [docs/README.md](./docs/README.md) 进入。

## 配置说明

敏感配置不入仓，例如本地 `.env`、真实密钥、数据库密码、企业微信 webhook 等均不包含在仓库中；请基于示例配置文件自行准备本地或部署环境配置。
