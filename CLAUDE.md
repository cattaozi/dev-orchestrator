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
│   ├── frontend/          # Next.js 前端
│   │   ├── app/          # 页面组件
│   │   ├── components/   # UI 组件
│   │   └── lib/         # 工具函数
│   └── backend/          # FastAPI 后端
│       └── main.py
├── storage/               # 数据模型
├── core/                 # 核心引擎
├── skills/               # Skill 适配层
└── docs/                # 文档
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
