-- =============================================================================
-- DevOrchestrator Database Schema
-- =============================================================================
-- Version: 1.0.0
-- Created: 2026-03-12
-- Description: 数据库结构定义文档
--
-- 修改记录:
-- | 版本   | 日期       | 描述                    |
-- |--------|------------|------------------------|
-- | 1.0.0  | 2026-03-12 | 初始版本                |
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 表: projects (项目表)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS projects (
    id SERIAL PRIMARY KEY,
    name VARCHAR NOT NULL UNIQUE,
    description TEXT DEFAULT '',
    repo VARCHAR NOT NULL DEFAULT '',
    local_path VARCHAR NOT NULL,
    default_branch VARCHAR DEFAULT 'main',
    status VARCHAR DEFAULT 'active',
    favorited BOOLEAN DEFAULT FALSE,
    config_yaml TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- -----------------------------------------------------------------------------
-- 表: sessions (会话表)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS sessions (
    id SERIAL PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id),
    issue_id INTEGER,
    branch VARCHAR NOT NULL,
    worktree_path VARCHAR NOT NULL,
    status VARCHAR DEFAULT 'pending',  -- pending/running/done/failed/cancelled
    agent_type VARCHAR NOT NULL,
    worker_id INTEGER,
    runtime VARCHAR DEFAULT 'agent-sdk',
    command VARCHAR,
    prompt TEXT,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- -----------------------------------------------------------------------------
-- 表: issues (Issue 表)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS issues (
    id SERIAL PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id),
    prd_id INTEGER,
    repo VARCHAR NOT NULL DEFAULT '',
    title VARCHAR,
    content TEXT,
    status VARCHAR DEFAULT 'pending',  -- pending/in_progress/done/closed
    worktree VARCHAR,
    worktree_state VARCHAR DEFAULT 'none',
    branch VARCHAR,
    branch_state VARCHAR DEFAULT 'none',
    github_number INTEGER,
    pr_number INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- -----------------------------------------------------------------------------
-- 表: prds (PRD 表)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS prds (
    id SERIAL PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id),
    title VARCHAR NOT NULL,
    version VARCHAR DEFAULT 'v1.0',
    status VARCHAR DEFAULT 'draft',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- -----------------------------------------------------------------------------
-- 表: workers (Worker 表)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS workers (
    id SERIAL PRIMARY KEY,
    name VARCHAR NOT NULL UNIQUE,
    agent_type VARCHAR NOT NULL,
    prompt_template TEXT,
    prompt_file_path TEXT,
    emoji VARCHAR DEFAULT '',
    is_builtin BOOLEAN DEFAULT FALSE,
    is_default BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- -----------------------------------------------------------------------------
-- 表: project_workers (项目-Worker 关联表)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS project_workers (
    id SERIAL PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id),
    worker_id INTEGER REFERENCES workers(id),
    custom_prompt_template TEXT,
    prompt_file_path TEXT,
    is_default BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(project_id, worker_id)
);

-- -----------------------------------------------------------------------------
-- 表: session_events (会话事件表)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS session_events (
    id SERIAL PRIMARY KEY,
    session_id INTEGER REFERENCES sessions(id),
    event_type VARCHAR NOT NULL,
    role VARCHAR NOT NULL,
    content TEXT,
    tool_name VARCHAR,
    tool_input TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- -----------------------------------------------------------------------------
-- 索引
-- -----------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_sessions_project_id ON sessions(project_id);
CREATE INDEX IF NOT EXISTS idx_sessions_issue_id ON sessions(issue_id);
CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status);
CREATE INDEX IF NOT EXISTS idx_issues_project_id ON issues(project_id);
CREATE INDEX IF NOT EXISTS idx_issues_status ON issues(status);
CREATE INDEX IF NOT EXISTS idx_session_events_session_id ON session_events(session_id);
CREATE INDEX IF NOT EXISTS idx_prds_project_id ON prds(project_id);
CREATE INDEX IF NOT EXISTS idx_project_workers_project_id ON project_workers(project_id);
