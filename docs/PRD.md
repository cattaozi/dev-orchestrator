# DevPilot 产品需求文档 (PRD)

> 版本: v0.1 | 日期: 2026-03-05 | 状态: 待确认

---

## 1. 项目概述

### 名称
**DevPilot** (开发领航员) - AI-Driven Development Orchestration

### 目标
让 AI (我) 能够自主理解需求、拆解任务、调度 Agent 执行、追踪进度、验收代码。

---

## 2. 核心功能

| 功能 | 描述 |
|------|------|
| F01 | 项目初始化 - 输入 GitHub URL 创建项目 |
| F02 | 设计库解析 - 读取 project.yaml + story/ |
| F03 | Story 拆解 - Story → GitHub Issue |
| F04 | Agent 调度 - Claude Code/Codex 执行 |
| F05 | 状态追踪 - PostgreSQL 持久化 |
| F06 | 进度展示 - Dashboard |
| F07 | 日志查看 |
| F08 | 人工干预 |

---

## 3. 技术栈

- 后端: Python / FastAPI / SQLAlchemy / PostgreSQL
- CLI: Click
- 前端: Next.js 14 / shadcn/ui / Tailwind CSS
- Agent: Claude Code / Codex

---

## 4. 页面

| 路径 | 页面 |
|------|------|
| / | Dashboard |
| /projects | 项目列表 |
| /projects/[id] | 项目详情 |
| /sessions | Session 列表 |
| /sessions/[id] | Session 详情 |

---

## 5. 里程碑

- [x] M1: 基础骨架 (项目初始化/GitHub仓库/PostgreSQL/CLI)
- [ ] M2: 核心功能 (设计库解析/Story拆解/Agent调度/状态追踪)
- [ ] M3: Web上线 (Next.js/Dashboard/列表/日志)
- [ ] M4: 增强功能 (实时日志/人工干预/通知)
