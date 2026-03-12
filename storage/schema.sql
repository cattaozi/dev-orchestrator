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
    repo VARCHAR NOT NULL,
    local_path VARCHAR NOT NULL,
    default_branch VARCHAR DEFAULT 'main',
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
    issue_number INTEGER NOT NULL,
    branch VARCHAR NOT NULL,
    worktree_path VARCHAR NOT NULL,
    status VARCHAR DEFAULT 'pending',  -- pending/running/done/failed
    agent VARCHAR NOT NULL,
    runtime VARCHAR DEFAULT 'tmux',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP
);

-- -----------------------------------------------------------------------------
-- 表: stories (故事表)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS stories (
    id SERIAL PRIMARY KEY,
    project_id INTEGER REFERENCES projects(id),
    story_id VARCHAR NOT NULL,
    title VARCHAR,
    status VARCHAR DEFAULT 'pending',  -- pending/in_progress/awaiting_acceptance/accepted/done
    depends_on TEXT DEFAULT '[]',  -- JSON array
    source_file VARCHAR,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- -----------------------------------------------------------------------------
-- 表: story_issues (故事-Issue 关联表)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS story_issues (
    id SERIAL PRIMARY KEY,
    story_id INTEGER REFERENCES stories(id),
    repo VARCHAR NOT NULL,
    issue_number INTEGER NOT NULL,
    merged BOOLEAN DEFAULT FALSE
);

-- -----------------------------------------------------------------------------
-- 表: events (事件表)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS events (
    id SERIAL PRIMARY KEY,
    session_id INTEGER REFERENCES sessions(id),
    type VARCHAR NOT NULL,  -- created/started/pr_created/merged/failed
    payload TEXT,  -- JSON
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- -----------------------------------------------------------------------------
-- 索引
-- -----------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_sessions_project_id ON sessions(project_id);
CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status);
CREATE INDEX IF NOT EXISTS idx_stories_project_id ON stories(project_id);
CREATE INDEX IF NOT EXISTS idx_stories_status ON stories(status);
CREATE INDEX IF NOT EXISTS idx_events_session_id ON events(session_id);
