# DevPilot 编码实践总纲

本目录用于给编码 Agent 和开发者提供按技术域加载的最佳实践，避免每次会话都引入无关上下文。

## 文档分层

- `frontend.md`：前端（Next.js 14 + TypeScript + shadcn/ui + Tailwind CSS）
- `backend.md`：后端（FastAPI + PostgreSQL）

## 使用规则（Agent）

- 修改 `web/frontend/**` 时，优先遵循 `docs/best-practices/frontend.md`。
- 修改 `web/backend/**`、`storage/**` 时，优先遵循 `docs/best-practices/backend.md`。
- 同时修改前后端时，两份文档都需要遵循。
- 规则冲突时，优先级为：`CLAUDE.md` > 本目录文档 > 代码内注释。

## 强制执行原则（跨端）

- 禁止硬编码环境相关配置（地址、端口、密钥）；统一走环境变量与配置层。
- 危险操作（删除、覆盖、不可逆变更）必须有显式二次确认。
- 新增配置项时必须同步更新 `.env.example` 与文档。
- 变更 PR 必须描述验证步骤与影响范围。
