# DevPilot 项目开发指南

## 项目概述

DevPilot 是一个 AI 驱动的开发编排系统，用户通过自然语言与 AI 交互，AI 驱动开发流程。

## 技术栈

- **前端**: Next.js 14 + shadcn/ui + Tailwind CSS
- **后端**: Python FastAPI + PostgreSQL
- **端口**: 前端 4000，后端 8000

## 目录结构

```
/data/repo/dev-orchestrator/
├── web/
│   ├── frontend/                    # Next.js 前端
│   │   ├── app/                    # 页面组件
│   │   │   ├── projects/           # 项目相关页面
│   │   │   │   └── [id]/
│   │   │   │       ├── page.tsx                    # 项目详情页
│   │   │   │       ├── issues/[issueId]/            # Issue 详情页
│   │   │   │       │   ├── page.tsx
│   │   │   │       │   └── sessions/[sessionId]/   # Session 详情页
│   │   │   │       │       ├── page.tsx
│   │   │   │       │       ├── prompt/page.tsx      # 发送 prompt
│   │   │   │       │       └── agent-prompt/page.tsx
│   │   │   │       ├── prds/[prdId]/                # PRD 详情页
│   │   │   │       └── workers/[workerId]/          # Worker 详情页
│   │   │   ├── api/                   # API 路由
│   │   │   ├── workers/               # Workers 页面
│   │   │   ├── sessions/              # Sessions 页面
│   │   │   └── settings/              # 设置页面
│   │   ├── components/                # UI 组件
│   │   │   ├── message-cards.tsx
│   │   │   └── terminal-output.tsx
│   │   └── lib/                      # 工具函数
│   │       └── message-parser.ts
│   └── backend/                      # FastAPI 后端
│       ├── main.py                   # 入口文件
│       ├── models.py                  # Pydantic 模型
│       ├── db.py                      # 数据库连接
│       ├── routers/                   # 路由模块
│       │   ├── projects.py
│       │   ├── issues.py
│       │   ├── sessions.py
│       │   ├── workers.py
│       │   ├── prds.py
│       │   └── config.py
│       └── services/                  # 业务逻辑
│           ├── project_service.py
│           ├── issue_service.py
│           ├── session_service.py
│           ├── worker_service.py
│           ├── prd_service.py
│           └── config_service.py
├── storage/                           # 数据存储层
│   └── database.py
├── core/                             # 核心引擎
│   └── dispatcher.py
├── skills/                           # Skill 适配层
├── config/                           # 配置文件
├── cli/                              # CLI 工具
├── plugins/                          # 插件
├── docs/                             # 文档
└── tests/                            # 测试
```

## 常用命令

```bash
# 启动后端
cd /data/repo/dev-orchestrator/web/backend
python3 main.py

# 启动前端
cd /data/repo/dev-orchestrator/web/frontend
npm run dev
```

## 数据库

- PostgreSQL 数据库: `dev_orchestrator`
- 连接信息: postgresql://luca:MAZV1QjTbXyPTq1teRFaEH0T@localhost:5432/dev_orchestrator

## 开发注意事项

1. 前端通过 Next.js API 代理访问后端 (http://127.0.0.1:8000)
2. 前端页面端口 4000，后端内部端口 8000
3. 用户只访问前端页面，后端对用户不可见
4. 删除等危险操作必须使用自定义 Dialog 组件确认，禁止使用浏览器原生 confirm()
5. Markdown 渲染使用 `@/components/ui/markdown` 组件，禁止直接使用 react-markdown

## FastAPI 路由规则

**重要**：FastAPI 按路由定义顺序匹配，匹配到第一个命中的路由后就返回，不会继续匹配后续路由。

因此：
- **更具体的路由（如 `/sessions/{id}/data`）必须放在前面**
- **泛化的路由（如 `/sessions/{id}`）必须放在最后兜底**
- 避免使用 `/{id}/action` 这种容易冲突的模式
