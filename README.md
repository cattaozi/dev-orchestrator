# DevOrchestrator - AI 驱动开发编排系统

> 你 ← → 我 ← → Skill ← → 系统

---

## 1. 项目概述

**目标**：构建一个 AI 驱动的开发编排系统，让 AI（我）能够自主理解需求、拆解任务、调度 Agent 执行、追踪进度、验收代码。

**核心理念**：
- 用户只和我（AI Assistant）对话
- 我通过 Skill 操作系统，产生结构化数据
- 系统执行任务并反馈结果
- 我负责决策、汇报、异常处理

---

## 2. 技术选型

### 最终技术栈

| 组件 | 技术 | 说明 |
|------|------|------|
| **语言** | Python 3.10+ | 与 OpenClaw 一致 |
| **CLI 框架** | Click | Python 最流行的 CLI 框架，简单优雅 |
| **数据库** | PostgreSQL | 本地已有，强大的关系型数据库 |
| **ORM** | SQLAlchemy 2.0 | 异步支持，类型安全 |
| **后端 API** | FastAPI | Python 现代 Web 框架 |
| **前端** | Next.js 14 | React 全栈框架 |
| **UI 框架** | shadcn/ui | 基于 Radix UI + Tailwind CSS |
| **样式** | Tailwind CSS | 原子化 CSS |
| **状态管理** | Zustand | 轻量级 |
| **实时** | Server-Sent Events | 事件推送 |

### 为什么选择这些技术？

- **Click**: Python 标准 CLI 库，比 argparse 更优雅，支持命令组
- **PostgreSQL**: 本地已安装，JSON 支持好，复杂查询强
- **Next.js 14**: App Router, Server Components, 前后端同构
- **shadcn/ui**: 可定制、无依赖、完全控制、Accessible

---

## 3. 模块划分

```
dev-orchestrator/
├── cli/                      # 命令行入口
│   ├── main.py               # Click 主入口
│   └── commands/             # 子命令
│
├── core/                     # 核心引擎
│   ├── config.py            # 配置加载
│   ├── session.py           # Session 管理
│   ├── dispatcher.py        # Agent 调度
│   ├── reactions.py         # 事件处理
│   └── events.py            # 事件定义
│
├── plugins/                  # 插件系统
│   ├── runtime/             # tmux / docker
│   ├── agent/               # claude-code / codex
│   ├── tracker/             # github / linear
│   └── notifier/           # console / webhook / feishu
│
├── storage/                  # 数据存储
│   ├── database.py          # SQLAlchemy 模型
│   └── migrations/         # 迁移脚本
│
├── web/                     # Web Dashboard
│   ├── backend/            # FastAPI 后端
│   │   ├── api/           # API 路由
│   │   └── main.py        # 应用入口
│   └── frontend/           # Next.js 前端
│       ├── app/            # App Router
│       ├── components/     # React 组件
│       ├── lib/            # 工具函数
│       └── public/         # 静态资源
│
├── skills/                  # Skill 适配层
│   └── design_reader.py    # 读设计库
│
├── scripts/                 # 辅助脚本
│   └── dispatch.sh         # Agent 调度脚本
│
├── config/                  # 配置示例
│   └── examples/
│
├── tests/                   # 测试
│
└── docs/                    # 文档
```

---

## 4. 数据模型 (PostgreSQL)

```sql
-- 项目表
CREATE TABLE projects (
    id SERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    repo TEXT NOT NULL,
    local_path TEXT NOT NULL,
    default_branch TEXT DEFAULT 'main',
    config_yaml TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP
);

-- Session 表
CREATE TABLE sessions (
    id SERIAL PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id),
    issue_number INTEGER NOT NULL,
    branch TEXT NOT NULL,
    worktree_path TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    agent TEXT NOT NULL,
    runtime TEXT DEFAULT 'tmux',
    created_at TIMESTAMP DEFAULT NOW(),
    started_at TIMESTAMP,
    completed_at TIMESTAMP
);

-- Story 表
CREATE TABLE stories (
    id SERIAL PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id),
    story_id TEXT NOT NULL,
    title TEXT,
    status TEXT DEFAULT 'pending',
    depends_on TEXT DEFAULT '[]',
    source_file TEXT,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Issue 到 Story 映射
CREATE TABLE story_issues (
    id SERIAL PRIMARY KEY,
    story_id INTEGER REFERENCES stories(id),
    repo TEXT NOT NULL,
    issue_number INTEGER NOT NULL,
    merged BOOLEAN DEFAULT FALSE
);

-- 事件表
CREATE TABLE events (
    id SERIAL PRIMARY KEY,
    session_id INTEGER REFERENCES sessions(id),
    type TEXT NOT NULL,
    payload TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

## 5. 前端技术栈详解

### Next.js 14 + shadcn/ui

```
前端目录结构:
frontend/
├── app/                    # Next.js App Router
│   ├── (dashboard)/       # Dashboard 布局组
│   │   ├── page.tsx      # 主页面
│   │   ├── projects/     # 项目管理
│   │   └── sessions/    # Session 监控
│   ├── api/             # API 代理
│   └── layout.tsx       # 根布局
├── components/
│   ├── ui/              # shadcn/ui 组件
│   │   ├── button.tsx
│   │   ├── card.tsx
│   │   ├── dialog.tsx
│   │   └── ...
│   ├── dashboard/       # 业务组件
│   │   ├── project-card.tsx
│   │   ├── session-list.tsx
│   │   └── status-badge.tsx
│   └── nav.tsx          # 导航
├── lib/
│   ├── api.ts           # API 调用
│   ├── store.ts         # Zustand 状态
│   └── utils.ts         # 工具函数
└── public/              # 静态资源
```

### shadcn/ui 组件

| 组件 | 用途 |
|------|------|
| Card | 项目卡片、统计面板 |
| Button | 操作按钮 |
| Dialog | 确认弹窗、详情查看 |
| Table | 列表展示 |
| Badge | 状态标签 |
| Progress | 进度条 |
| Tabs | 切换视图 |
| Avatar | 用户头像 |

---

## 6. API 设计

### Web API

```python
# Projects
GET    /api/projects              # 列表
POST   /api/projects              # 创建
GET    /api/projects/{id}         # 详情
DELETE /api/projects/{id}         # 删除

# Sessions
GET    /api/sessions              # 列表
GET    /api/sessions/{id}         # 详情
POST   /api/sessions              # 创建
DELETE /api/sessions/{id}         # 终止

# Stories
GET    /api/projects/{id}/stories # 项目 Story 列表
PUT    /api/stories/{id}          # 更新状态

# Events
GET    /api/sessions/{id}/events  # Session 事件
WS     /api/events/stream          # 实时事件流 (SSE)

# CLI 命令兼容
GET    /api/status                # do status 等价
POST   /api/spawn                 # do spawn 等价
POST   /api/kill                  # do kill 等价
```

---

## 7. 快速开始

```bash
# 进入项目目录
cd /data/repo/dev-orchestrator

# 安装 Python 依赖
pip install -e ".[dev]"

# 安装前端依赖
cd frontend && npm install

# 初始化数据库
python -c "from storage.database import init_db; init_db()"

# 启动后端
python -m uvicorn web.backend.main:app --reload

# 启动前端 (新终端)
cd frontend && npm run dev
```

---

## 8. 开发路线图

### Phase 1: MVP (1-2周)
- [x] 项目骨架搭建
- [x] PostgreSQL 存储
- [x] CLI 基础命令
- [x] tmux + Claude Code 执行

### Phase 2: Web (2周)
- [ ] Next.js 14 + shadcn/ui
- [ ] Dashboard 页面
- [ ] 实时状态推送

### Phase 3: 增强 (2周)
- [ ] 事件处理 (Reactions)
- [ ] 自动验收流程
- [ ] 多 Agent 支持

### Phase 4: 完善 (1周)
- [ ] 插件系统
- [ ] Linear/Jira 集成
- [ ] 通知集成
