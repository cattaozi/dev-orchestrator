"""
FastAPI Backend for DevPilot - with PostgreSQL
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import os
import subprocess
import tempfile
import threading
import json
import asyncio

app = FastAPI(title="DevPilot API", version="0.1.0")

# Store active subprocesses for stream-json sessions
# Key: session_id, Value: {"process": subprocess.Popen, "lock": threading.Lock}
active_sessions: dict = {}

# Message queues for agent-sdk sessions (session_id -> list of messages)
agent_message_queues: dict = {}

# Stop flags for agent-sdk sessions (session_id -> bool)
agent_stop_flags: dict = {}

# Stop messages for agent-sdk sessions (session_id -> str)
agent_stop_messages: dict = {}

# Agent SDK clients (session_id -> ClaudeSDKClient instance) for calling interrupt
agent_clients: dict = {}

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4000", "http://43.167.203.165:4000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database setup
import psycopg2
from psycopg2.extras import RealDictCursor

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://luca:MAZV1QjTbXyPTq1teRFaEH0T@localhost:5432/dev_orchestrator?client_encoding=utf8"
)

def get_db():
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    return conn


# Init database tables
def init_db():
    from psycopg2.extras import RealDictCursor
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id SERIAL PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            description TEXT,
            repo TEXT,
            local_path TEXT NOT NULL,
            default_branch TEXT DEFAULT 'main',
            status TEXT DEFAULT 'active',
            favorited BOOLEAN DEFAULT FALSE,
            config_yaml TEXT,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP
        )
    """)

    # Migration: add columns if not exists
    try:
        cursor.execute("ALTER TABLE projects ADD COLUMN IF NOT EXISTS description TEXT")
    except Exception:
        pass

    # Migration: add favorited column if not exists
    cursor.execute("""
        ALTER TABLE projects ADD COLUMN IF NOT EXISTS favorited BOOLEAN DEFAULT FALSE
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS prds (
            id SERIAL PRIMARY KEY,
            project_id INTEGER REFERENCES projects(id),
            title TEXT NOT NULL,
            version TEXT DEFAULT 'v1.0',
            status TEXT DEFAULT 'draft',
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS issues (
            id SERIAL PRIMARY KEY,
            project_id INTEGER REFERENCES projects(id),
            prd_id INTEGER REFERENCES prds(id),
            repo TEXT,
            github_number INTEGER,
            title TEXT NOT NULL,
            content TEXT,
            status TEXT DEFAULT 'pending',
            pr_number INTEGER,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS workers (
            id SERIAL PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            emoji TEXT DEFAULT '',
            agent_type TEXT NOT NULL,
            prompt_template TEXT,
            is_builtin BOOLEAN DEFAULT FALSE
        )
    """)

    # Migration: add columns if not exists
    try:
        cursor.execute("ALTER TABLE workers ADD COLUMN IF NOT EXISTS emoji TEXT DEFAULT ''")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE workers ADD COLUMN IF NOT EXISTS is_builtin BOOLEAN DEFAULT FALSE")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE workers ADD COLUMN IF NOT EXISTS prompt_file_path TEXT")
    except Exception:
        pass

    # Create config table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS config (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    # Initialize default config
    cursor.execute("""
        INSERT INTO config (key, value) VALUES ('worker_prompt_dir', '~/.worker-prompt')
        ON CONFLICT (key) DO NOTHING
    """)

    # Add unique constraint on name if not exists
    try:
        cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS workers_name_unique ON workers(name)")
    except Exception:
        pass

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id SERIAL PRIMARY KEY,
            issue_id INTEGER REFERENCES issues(id),
            project_id INTEGER REFERENCES projects(id),
            branch TEXT NOT NULL,
            worktree_path TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            agent_type TEXT DEFAULT 'claude-code',
            worker_id INTEGER REFERENCES workers(id),
            runtime TEXT,
            log_path TEXT,
            tmux_session TEXT,
            command TEXT,
            process_id INTEGER,
            created_at TIMESTAMP DEFAULT NOW(),
            started_at TIMESTAMP,
            completed_at TIMESTAMP
        )
    """)

    # Add process_id column if not exists
    cursor.execute("ALTER TABLE sessions ADD COLUMN IF NOT EXISTS process_id INTEGER")

    # Create session_events table for stream-json mode
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS session_events (
            id SERIAL PRIMARY KEY,
            session_id INTEGER REFERENCES sessions(id) ON DELETE CASCADE,
            event_type TEXT NOT NULL,
            role TEXT,
            content TEXT,
            tool_name TEXT,
            tool_input TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)

    # Insert sample workers if not exists
    cursor.execute("""
        INSERT INTO workers (name, emoji, agent_type, prompt_template, is_builtin)
        VALUES
            ('Developer', '👨‍💻', 'claude-code', '你是一个专业的开发工程师。负责根据需求实现功能，写单元测试，提交代码。', TRUE),
            ('Reviewer', '👀', 'claude-code', '你是一个专业的代码审查工程师。负责检查代码质量、逻辑正确性、安全性，并提出改进建议。', TRUE),
            ('Tester', '🧪', 'claude-code', '你是一个专业的测试工程师。负责编写测试用例、执行测试、验证功能是否符合需求。', TRUE)
        ON CONFLICT (name) DO NOTHING
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS project_workers (
            id SERIAL PRIMARY KEY,
            project_id INTEGER REFERENCES projects(id),
            worker_id INTEGER REFERENCES workers(id),
            custom_prompt_template TEXT,
            created_at TIMESTAMP DEFAULT NOW(),
            UNIQUE(project_id, worker_id)
        )
    """)

    conn.commit()

    # Generate worker prompt files after workers are inserted
    _generate_worker_prompt_files(cursor)
    conn.commit()

    conn.close()


def _generate_worker_prompt_files(cursor):
    """Generate worker prompt files if they don't exist."""
    # Get prompt directory from config
    cursor.execute("SELECT value FROM config WHERE key = 'worker_prompt_dir'")
    result = cursor.fetchone()
    # Handle both regular tuple and RealDictRow
    if result:
        prompt_dir = result[0] if isinstance(result, tuple) else result.get('value', '~/.worker-prompt')
    else:
        prompt_dir = '~/.worker-prompt'

    # Expand ~
    prompt_dir = os.path.expanduser(prompt_dir)

    # Create directory if not exists
    os.makedirs(prompt_dir, exist_ok=True)

    # Add prompt_file_path column to project_workers if not exists
    try:
        cursor.execute("ALTER TABLE project_workers ADD COLUMN IF NOT EXISTS prompt_file_path TEXT")
    except Exception:
        pass

    # ===== Handle system workers =====
    cursor.execute("SELECT id, name, prompt_template FROM workers")
    workers = cursor.fetchall()

    for worker in workers:
        # Handle both tuple and RealDictRow
        if isinstance(worker, tuple):
            worker_id, worker_name, prompt_template = worker
        else:
            worker_id = worker.get('id')
            worker_name = worker.get('name')
            prompt_template = worker.get('prompt_template')

        if not prompt_template:
            continue

        # Generate filename: worker-{id}-{name}.md
        safe_name = worker_name.lower().replace(' ', '-')
        filename = f"worker-{worker_id}-{safe_name}.md"
        filepath = os.path.join(prompt_dir, filename)

        # Write file if not exists, or update if prompt_template changed
        needs_write = not os.path.exists(filepath)
        if not needs_write:
            # Check if content changed
            with open(filepath, 'r', encoding='utf-8') as f:
                existing_content = f.read()
            if existing_content != prompt_template:
                needs_write = True

        if needs_write:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(prompt_template)
            print(f"Generated/Updated prompt file: {filepath}")

        # Always update worker record with file path
        cursor.execute(
            "UPDATE workers SET prompt_file_path = %s WHERE id = %s",
            (filepath, worker_id)
        )

    # ===== Handle project workers (custom prompts) =====
    cursor.execute("""
        SELECT pw.id, pw.project_id, pw.worker_id, pw.custom_prompt_template, w.name as worker_name
        FROM project_workers pw
        JOIN workers w ON pw.worker_id = w.id
        WHERE pw.custom_prompt_template IS NOT NULL AND pw.custom_prompt_template != ''
    """)
    project_workers = cursor.fetchall()

    for pw in project_workers:
        if isinstance(pw, tuple):
            pw_id, project_id, worker_id, custom_prompt, worker_name = pw
        else:
            pw_id = pw.get('id')
            project_id = pw.get('project_id')
            worker_id = pw.get('worker_id')
            custom_prompt = pw.get('custom_prompt_template')
            worker_name = pw.get('worker_name')

        if not custom_prompt:
            continue

        # Generate filename: project-{project_id}-worker-{worker_id}-{name}.md
        safe_name = worker_name.lower().replace(' ', '-')
        filename = f"project-{project_id}-worker-{worker_id}-{safe_name}.md"
        filepath = os.path.join(prompt_dir, filename)

        # Write file if not exists, or update if custom_prompt changed
        needs_write = not os.path.exists(filepath)
        if not needs_write:
            with open(filepath, 'r', encoding='utf-8') as f:
                existing_content = f.read()
            if existing_content != custom_prompt:
                needs_write = True

        if needs_write:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(custom_prompt)
            print(f"Generated/Updated project prompt file: {filepath}")

        # Always update project_worker record with file path
        cursor.execute(
            "UPDATE project_workers SET prompt_file_path = %s WHERE id = %s",
            (filepath, pw_id)
        )


def _sync_sessions_with_tmux(cursor):
    """Check tmux sessions and update session table status."""
    # Get all running sessions from database
    cursor.execute("SELECT id, tmux_session, status FROM sessions WHERE status = 'running'")
    db_sessions = cursor.fetchall()

    for session in db_sessions:
        if isinstance(session, tuple):
            session_id, tmux_session, status = session
        else:
            session_id = session.get('id')
            tmux_session = session.get('tmux_session')
            status = session.get('status')

        if not tmux_session:
            continue

        # Check if tmux session exists
        result = subprocess.run(
            ["tmux", "has-session", "-t", tmux_session],
            capture_output=True
        )

        if result.returncode != 0:
            # Session doesn't exist, mark as failed/completed
            cursor.execute("""
                UPDATE sessions SET status = 'failed', completed_at = NOW()
                WHERE id = %s
            """, (session_id,))
            print(f"Session {session_id}: tmux session '{tmux_session}' not found, marked as failed")

    # Commit changes
    conn.commit()


# Initialize on startup
init_db()

# Sync sessions with tmux
conn = get_db()
cursor = conn.cursor(cursor_factory=RealDictCursor)
_sync_sessions_with_tmux(cursor)
conn.commit()
conn.close()


# Pydantic Models
class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None
    repo: str = ""
    local_path: str
    default_branch: str = "main"
    favorited: bool = False


class ProjectResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    repo: str
    local_path: str
    status: str
    favorited: bool = False
    created_at: str


class SessionResponse(BaseModel):
    id: int
    issue_id: int
    project_id: int
    branch: str
    worktree_path: str
    status: str
    agent_type: str
    worker_id: Optional[int] = None
    runtime: Optional[str] = None
    log_path: Optional[str] = None
    tmux_session: Optional[str] = None
    command: Optional[str] = None
    prompt: Optional[str] = None
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class SessionCreate(BaseModel):
    issue_id: int
    worker_id: Optional[int] = None
    runtime: Optional[str] = "tmux"  # "tmux", "stream-json", or "agent-sdk"


class WorkerResponse(BaseModel):
    id: int
    name: str
    emoji: str
    agent_type: str
    prompt_template: str
    is_builtin: bool = False


class WorkerCreate(BaseModel):
    name: str
    emoji: str = ""
    agent_type: str = "claude-code"
    prompt_template: str = ""


class WorkerUpdate(BaseModel):
    name: Optional[str] = None
    emoji: Optional[str] = None
    agent_type: Optional[str] = None
    prompt_template: Optional[str] = None
    is_builtin: Optional[bool] = None


class ProjectWorkerCreate(BaseModel):
    project_id: int
    worker_id: int
    custom_prompt_template: str = ""


class ProjectWorkerUpdate(BaseModel):
    custom_prompt_template: Optional[str] = None


class ProjectWorkerResponse(BaseModel):
    id: int
    project_id: int
    worker_id: int
    worker_name: Optional[str] = None
    emoji: Optional[str] = None
    agent_type: Optional[str] = None
    custom_prompt_template: str
    created_at: str


class PRDCreate(BaseModel):
    project_id: int
    title: str
    version: str = "v1.0"


class PRDResponse(BaseModel):
    id: int
    project_id: int
    title: str
    version: str
    status: str
    created_at: str


class IssueCreate(BaseModel):
    title: str
    content: str


class IssueUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    status: Optional[str] = None


class IssueResponse(BaseModel):
    id: int
    project_id: int
    title: Optional[str] = None
    content: str
    status: str
    created_at: str


# API Routes

@app.get("/")
def root():
    return {"message": "DevPilot API", "version": "0.1.0"}


# Projects
@app.get("/api/projects", response_model=List[ProjectResponse])
def list_projects():
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("SELECT * FROM projects ORDER BY created_at DESC")
    projects = cursor.fetchall()
    conn.close()
    # Convert datetime to string
    return [dict(p, created_at=str(p['created_at'])) for p in projects]


@app.get("/api/projects/{project_id}", response_model=ProjectResponse)
def get_project(project_id: int):
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("SELECT * FROM projects WHERE id = %s", (project_id,))
    project = cursor.fetchone()
    conn.close()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return dict(project, created_at=str(project['created_at']))


@app.put("/api/projects/{project_id}", response_model=ProjectResponse)
def update_project(project_id: int, project_update: ProjectCreate):
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("SELECT * FROM projects WHERE id = %s", (project_id,))
    project = cursor.fetchone()
    if not project:
        conn.close()
        raise HTTPException(status_code=404, detail="Project not found")

    update_fields = []
    update_values = []

    if project_update.name is not None:
        update_fields.append("name = %s")
        update_values.append(project_update.name)
    if project_update.description is not None:
        update_fields.append("description = %s")
        update_values.append(project_update.description)

    if update_fields:
        update_values.append(project_id)
        cursor.execute(f"UPDATE projects SET {', '.join(update_fields)} WHERE id = %s RETURNING *", update_values)
        updated = cursor.fetchone()
        conn.commit()
        conn.close()
        return dict(updated, created_at=str(updated['created_at']))

    conn.close()
    return dict(project, created_at=str(project['created_at']))


@app.get("/api/projects/{project_id}/readme")
def get_project_readme(project_id: int):
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("SELECT local_path FROM projects WHERE id = %s", (project_id,))
    project = cursor.fetchone()
    conn.close()

    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    local_path = project['local_path']
    readme_path = None

    # Check for README.md first, then CLAUDE.md
    for filename in ['README.md', 'CLAUDE.md']:
        path = os.path.join(local_path, filename)
        if os.path.exists(path):
            readme_path = path
            break

    if not readme_path:
        return {"content": "", "filename": ""}

    try:
        with open(readme_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return {"content": content, "filename": os.path.basename(readme_path)}
    except Exception:
        return {"content": "", "filename": ""}


@app.post("/api/projects", response_model=ProjectResponse)
def create_project(project: ProjectCreate):
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    try:
        cursor.execute("""
            INSERT INTO projects (name, description, repo, local_path, default_branch, status)
            VALUES (%s, %s, %s, %s, %s, 'active')
            RETURNING *
        """, (project.name, project.description, project.repo, project.local_path, project.default_branch))
        new_project = cursor.fetchone()
        conn.commit()
        return dict(new_project, created_at=str(new_project['created_at']))
    except psycopg2.IntegrityError:
        raise HTTPException(status_code=400, detail="Project already exists")
    finally:
        conn.close()


@app.delete("/api/projects/{project_id}")
def delete_project(project_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM projects WHERE id = %s", (project_id,))
    conn.commit()
    conn.close()
    return {"message": "Project deleted"}


@app.post("/api/projects/{project_id}/favorite")
def toggle_favorite(project_id: int):
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("SELECT favorited FROM projects WHERE id = %s", (project_id,))
    project = cursor.fetchone()
    if not project:
        conn.close()
        raise HTTPException(status_code=404, detail="Project not found")

    new_favorited = not project['favorited']
    cursor.execute("UPDATE projects SET favorited = %s WHERE id = %s", (new_favorited, project_id))
    conn.commit()
    conn.close()
    return {"favorited": new_favorited}


# PRDs
@app.get("/api/projects/{project_id}/prds", response_model=List[PRDResponse])
def list_prds(project_id: int):
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("SELECT * FROM prds WHERE project_id = %s ORDER BY created_at DESC", (project_id,))
    prds = cursor.fetchall()
    conn.close()
    return [dict(p, created_at=str(p['created_at'])) for p in prds]


@app.get("/api/projects/{project_id}/prds/{prd_id}", response_model=PRDResponse)
def get_prd(project_id: int, prd_id: int):
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("SELECT * FROM prds WHERE id = %s AND project_id = %s", (prd_id, project_id))
    prd = cursor.fetchone()
    conn.close()
    if not prd:
        raise HTTPException(status_code=404, detail="PRD not found")
    return dict(prd, created_at=str(prd['created_at']))


@app.post("/api/projects/{project_id}/prds", response_model=PRDResponse)
def create_prd(project_id: int, prd: PRDCreate):
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("""
        INSERT INTO prds (project_id, title, version, status)
        VALUES (%s, %s, %s, 'draft')
        RETURNING *
    """, (project_id, prd.title, prd.version))
    new_prd = cursor.fetchone()
    conn.commit()
    conn.close()
    return dict(new_prd, created_at=str(new_prd['created_at']))


# Issues
@app.get("/api/projects/{project_id}/issues", response_model=List[IssueResponse])
def list_issues(project_id: int):
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("SELECT * FROM issues WHERE project_id = %s ORDER BY created_at DESC", (project_id,))
    issues = cursor.fetchall()
    conn.close()
    return [dict(i, created_at=str(i['created_at'])) for i in issues]


@app.get("/api/projects/{project_id}/issues/{issue_id}", response_model=IssueResponse)
def get_issue(project_id: int, issue_id: int):
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("SELECT * FROM issues WHERE id = %s AND project_id = %s", (issue_id, project_id))
    issue = cursor.fetchone()
    conn.close()
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")
    return dict(issue, created_at=str(issue['created_at']))


@app.post("/api/projects/{project_id}/issues", response_model=IssueResponse)
def create_issue(project_id: int, issue: IssueCreate):
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("""
        INSERT INTO issues (project_id, title, content, status)
        VALUES (%s, %s, %s, 'pending')
        RETURNING *
    """, (project_id, issue.title, issue.content))
    new_issue = cursor.fetchone()
    conn.commit()
    conn.close()
    return dict(new_issue, created_at=str(new_issue['created_at']))


@app.delete("/api/projects/{project_id}/issues/{issue_id}")
def delete_issue(project_id: int, issue_id: int):
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("SELECT * FROM issues WHERE id = %s AND project_id = %s", (issue_id, project_id))
    issue = cursor.fetchone()
    if not issue:
        conn.close()
        raise HTTPException(status_code=404, detail="Issue not found")
    cursor.execute("DELETE FROM issues WHERE id = %s", (issue_id,))
    conn.commit()
    conn.close()
    return {"message": "Issue deleted"}


@app.put("/api/projects/{project_id}/issues/{issue_id}", response_model=IssueResponse)
def update_issue(project_id: int, issue_id: int, issue_update: IssueUpdate):
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("SELECT * FROM issues WHERE id = %s AND project_id = %s", (issue_id, project_id))
    issue = cursor.fetchone()
    if not issue:
        conn.close()
        raise HTTPException(status_code=404, detail="Issue not found")

    update_fields = []
    update_values = []
    if issue_update.title is not None:
        update_fields.append("title = %s")
        update_values.append(issue_update.title)
    if issue_update.content is not None:
        update_fields.append("content = %s")
        update_values.append(issue_update.content)
    if issue_update.status is not None:
        update_fields.append("status = %s")
        update_values.append(issue_update.status)

    if update_fields:
        update_values.extend([issue_id, project_id])
        cursor.execute(
            f"UPDATE issues SET {', '.join(update_fields)} WHERE id = %s AND project_id = %s RETURNING *",
            update_values
        )
        updated_issue = cursor.fetchone()
        conn.commit()
    else:
        updated_issue = issue

    conn.close()
    return dict(updated_issue, created_at=str(updated_issue['created_at']))


# Sessions
@app.get("/api/sessions", response_model=List[SessionResponse])
def list_sessions():
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("SELECT * FROM sessions ORDER BY created_at DESC")
    sessions = cursor.fetchall()
    conn.close()
    return [dict(s, 
        created_at=str(s['created_at']) if s['created_at'] else None,
        started_at=str(s['started_at']) if s['started_at'] else None,
        completed_at=str(s['completed_at']) if s['completed_at'] else None
    ) for s in sessions]


def _stream_json_reader(session_id: int, process: subprocess.Popen, project_path: str, init_message: str, footer_message: str):
    """Background thread to read claude output and store events in database."""
    import psycopg2
    from psycopg2.extras import RealDictCursor

    # Connect to database
    db_conn = psycopg2.connect(
        "postgresql://luca:MAZV1QjTbXyPTq1teRFaEH0T@localhost:5432/dev_orchestrator?client_encoding=utf8"
    )
    db_cursor = db_conn.cursor(cursor_factory=RealDictCursor)

    try:
        # Read from stderr (--verbose outputs to stderr)
        # Also read stdout for the response
        import select

        # Wait for process to complete and read output
        stdout_lines = []
        stderr_lines = []

        # Read stdout
        while True:
            line = process.stdout.readline()
            if not line:
                break
            stdout_lines.append(line)

            # Store as event
            db_cursor.execute("""
                INSERT INTO session_events (session_id, event_type, role, content)
                VALUES (%s, %s, %s, %s)
            """, (session_id, "stdout", "assistant", line))
            db_conn.commit()

        # Read any remaining stderr
        stderr_output = process.stderr.read()
        if stderr_output:
            for line in stderr_output.split('\n'):
                if line.strip():
                    db_cursor.execute("""
                        INSERT INTO session_events (session_id, event_type, role, content)
                        VALUES (%s, %s, %s, %s)
                    """, (session_id, "stderr", "system", line))
                    db_conn.commit()

        # Mark session as completed
        db_cursor.execute("UPDATE sessions SET status = 'completed' WHERE id = %s", (session_id,))
        db_conn.commit()

    except Exception as e:
        print(f"Error in stream reader: {e}")
    finally:
        db_cursor.close()
        db_conn.close()


@app.post("/api/sessions", response_model=SessionResponse)
def create_session(session_create: SessionCreate):
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    # Get issue info
    cursor.execute("SELECT * FROM issues WHERE id = %s", (session_create.issue_id,))
    issue = cursor.fetchone()
    if not issue:
        conn.close()
        raise HTTPException(status_code=404, detail="Issue not found")

    # Get project info
    cursor.execute("SELECT * FROM projects WHERE id = %s", (issue['project_id'],))
    project = cursor.fetchone()
    if not project:
        conn.close()
        raise HTTPException(status_code=404, detail="Project not found")

    # Get worker - must specify worker_id
    if not session_create.worker_id:
        raise HTTPException(status_code=400, detail="worker_id is required")

    # Check project worker override first
    cursor.execute("""
        SELECT pw.*, w.name as worker_name, w.agent_type, w.prompt_template as base_prompt, w.prompt_file_path
        FROM project_workers pw
        JOIN workers w ON pw.worker_id = w.id
        WHERE pw.project_id = %s AND pw.worker_id = %s
    """, (project['id'], session_create.worker_id))
    project_worker = cursor.fetchone()

    if project_worker:
        worker = {
            'id': project_worker['worker_id'],
            'name': project_worker['worker_name'],
            'agent_type': project_worker['agent_type'],
            'prompt_template': project_worker['custom_prompt_template'] or project_worker['base_prompt'],
            'prompt_file_path': project_worker.get('prompt_file_path', '')
        }
    else:
        cursor.execute("SELECT * FROM workers WHERE id = %s", (session_create.worker_id,))
        worker = cursor.fetchone()
        if not worker:
            raise HTTPException(status_code=404, detail="Worker not found")

    # Generate branch name
    branch_name = f"task/issue-{issue['id']}"
    worktree_path = f"/home/claude/worktrees/{issue['id']}"
    tmux_session = f"issue-{issue['id']}"
    log_path = f"/home/claude/issue-{issue['id']}.log"

    # Create worktree
    try:
        subprocess.run(
            ["git", "worktree", "add", worktree_path, "-b", branch_name],
            cwd=project['local_path'],
            capture_output=True,
            timeout=30
        )
    except:
        pass

    # Prepare prompts
    user_prompt = issue['content'] or issue['title']

    # Get footer prompt from config table, use default if not set
    cursor.execute("SELECT value FROM config WHERE key = 'agent_footer_prompt'")
    config_result = cursor.fetchone()
    default_footer = f"""请在此分支 `{branch_name}` 上进行开发。
开发完成后，请：
1. 编写单元测试
2. 提交代码到 `{branch_name}` 分支
3. 汇报完成状态"""
    footer_prompt = config_result['value'] if config_result else default_footer

    runtime = session_create.runtime or "stream-json"

    if runtime == "stream-json":
        # Interactive mode: run Claude Code with stdin/stdout for real-time conversation
        import time

        prompt_file = worker.get('prompt_file_path', '')
        system_prompt = worker.get('prompt_template', '')

        if prompt_file and os.path.exists(prompt_file):
            with open(prompt_file, 'r') as f:
                system_prompt = f.read()

        # Get user prompt from issue
        user_prompt = issue.get('content', '') or issue.get('title', '')
        if not user_prompt:
            user_prompt = "Please help me with this issue."

        # Build footer prompt - use config with placeholder replacement
        # Get from config first, with fallback
        cursor.execute("SELECT value FROM config WHERE key = 'agent_footer_prompt'")
        config_result = cursor.fetchone()
        if config_result:
            footer_template = config_result['value']
            # Replace placeholders
            footer_prompt = footer_template.replace('{branch}', branch_name).replace('{project_path}', worktree_path)
        else:
            footer_prompt = f"\n\n---\n当前分支: {branch_name}\n项目路径: {worktree_path}\n请在此分支上进行开发工作。"

        full_prompt = f"{system_prompt}\n\n{user_prompt}\n\n{footer_prompt}"

        # Prepare environment
        env = os.environ.copy()
        env.pop("CLAUDECODE", None)
        env["ANTHROPIC_API_KEY"] = os.environ.get("ANTHROPIC_API_KEY", "")

        # Build claude command for interactive mode
        # Use -p for non-interactive (print) mode
        # Use --output-format stream-json for structured output
        # Use --dangerously-skip-permissions to avoid interactive prompts
        claude_cmd = [
            "env", "-u", "CLAUDECODE", "claude",
            "-p",
            "--output-format", "stream-json",
            "--dangerously-skip-permissions",
            "--verbose"
        ]

        if system_prompt:
            # Write system prompt to temp file to avoid CLI length limits
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as pf:
                pf.write(system_prompt)
                system_prompt_file = pf.name
            claude_cmd.extend(["--system-prompt-file", system_prompt_file])

        # Create session first
        cursor.execute("""
            INSERT INTO sessions (issue_id, project_id, branch, worktree_path, status, agent_type, worker_id, runtime, log_path, tmux_session, command, started_at, prompt)
            VALUES (%s, %s, %s, %s, 'running', %s, %s, %s, %s, %s, %s, NOW(), %s)
            RETURNING *
        """, (
            issue['id'],
            project['id'],
            branch_name,
            worktree_path,
            worker.get('agent_type', 'claude-code'),
            worker.get('id'),
            'stream-json',
            log_path,
            tmux_session,
            " ".join(claude_cmd),
            full_prompt
        ))
        session = cursor.fetchone()
        if not session:
            raise HTTPException(status_code=500, detail="Failed to create session")

        session_id = session['id']

        # Start background thread to run interactive claude
        def run_interactive_claude():
            try:
                # Prepare process
                proc = subprocess.Popen(
                    claude_cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    cwd=worktree_path,
                    env=env,
                    text=True,
                    bufsize=1
                )

                # Store process for message sending
                active_sessions[session_id] = {"process": proc}

                # Send initial prompt as plain text
                proc.stdin.write(full_prompt + "\n")
                proc.stdin.flush()

                # Read all output using communicate
                stdout, _ = proc.communicate(timeout=120)

                # Store output as events
                import psycopg2
                from psycopg2.extras import RealDictCursor
                db_conn = psycopg2.connect(DATABASE_URL)
                db_cursor = db_conn.cursor(cursor_factory=RealDictCursor)

                # Store each line as an event
                for line in stdout.split('\n'):
                    if line.strip():
                        db_cursor.execute("""
                            INSERT INTO session_events (session_id, event_type, role, content)
                            VALUES (%s, 'output', 'assistant', %s)
                        """, (session_id, line[:10000]))
                db_conn.commit()

                # Update session status
                status = 'completed' if proc.returncode == 0 else 'failed'
                db_cursor.execute("UPDATE sessions SET status = %s WHERE id = %s", (status, session_id))
                db_conn.commit()
                db_cursor.close()
                db_conn.close()

            except Exception as e:
                print(f"Error in interactive claude: {e}")
                try:
                    import psycopg2
                    db_conn = psycopg2.connect(DATABASE_URL)
                    db_cursor = db_conn.cursor()
                    db_cursor.execute("UPDATE sessions SET status = 'failed' WHERE id = %s", (session_id,))
                    db_conn.commit()
                    db_cursor.close()
                    db_conn.close()
                except:
                    pass
            finally:
                if session_id in active_sessions:
                    del active_sessions[session_id]

        # Start the background thread
        thread = threading.Thread(target=run_interactive_claude, daemon=True)
        thread.start()

        # Return the session immediately
        conn.commit()
        conn.close()
        return dict(session,
            created_at=str(session['created_at']) if session['created_at'] else None,
            started_at=str(session['started_at']) if session['started_at'] else None,
            completed_at=str(session['completed_at']) if session['completed_at'] else None
        )

    elif runtime == "agent-sdk":
        # Agent SDK mode - use Claude Agent SDK for streaming interactive sessions
        # Multi-round conversation: maintain a loop, inject user messages from queue
        prompt_file = worker.get('prompt_file_path', '')
        system_prompt = worker.get('prompt_template', '')

        if prompt_file and os.path.exists(prompt_file):
            with open(prompt_file, 'r') as f:
                system_prompt = f.read()

        full_prompt = f"{system_prompt}\n\n{user_prompt}\n\n{footer_prompt}"

        try:
            # Prepare environment
            # Set API key in environment for the SDK
            if "ANTHROPIC_API_KEY" not in os.environ:
                raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not set in environment")

            # Insert session first
            cursor.execute("""
                INSERT INTO sessions (issue_id, project_id, branch, worktree_path, status, agent_type, worker_id, runtime, log_path, tmux_session, command, started_at, prompt)
                VALUES (%s, %s, %s, %s, 'running', %s, %s, %s, %s, %s, %s, NOW(), %s)
                RETURNING *
            """, (
                issue['id'],
                project['id'],
                branch_name,
                worktree_path,
                worker.get('agent_type', 'claude-code'),
                worker.get('id'),
                'agent-sdk',
                log_path,
                tmux_session,
                "claude-agent-sdk",
                full_prompt
            ))
            session = cursor.fetchone()
            if not session:
                raise HTTPException(status_code=500, detail="Failed to create session")

            session_id = session['id']

            # Initialize message queue and stop flag for this session
            agent_message_queues[session_id] = []
            agent_stop_flags[session_id] = False

            # Define async function to run agent with continuous loop
            def run_agent():
                import asyncio
                import os
                import time

                print(f"Session {session_id}: Starting agent thread for worktree {worktree_path}")

                # Unset CLAUDECODE to allow nested sessions
                os.environ.pop("CLAUDECODE", None)

                try:
                    # Change to worktree directory so Claude runs in the project
                    if os.path.exists(worktree_path):
                        os.chdir(worktree_path)
                    else:
                        print(f"Session {session_id}: Worktree path does not exist: {worktree_path}")
                except Exception as e:
                    print(f"Session {session_id}: Failed to change to worktree: {e}")

                async def agent_task():
                    try:
                        from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions
                        import psycopg2
                        from psycopg2.extras import RealDictCursor

                        db_conn = psycopg2.connect(
                            "postgresql://luca:MAZV1QjTbXyPTq1teRFaEH0T@localhost:5432/dev_orchestrator?client_encoding=utf8"
                        )
                        db_cursor = db_conn.cursor(cursor_factory=RealDictCursor)

                        # Create client for bidirectional communication
                        # Enable streaming mode so interrupt() works
                        client = ClaudeSDKClient(
                            options=ClaudeAgentOptions(
                                allowed_tools=["Read", "Write", "Edit", "Bash", "Glob", "Grep", "WebSearch", "WebFetch"],
                                cwd=worktree_path,
                                output_format="stream-json",
                            )
                        )

                        # Store client reference for interrupt
                        agent_clients[session_id] = client

                        # Connect to the agent
                        await client.connect()

                        # Send initial prompt
                        await client.query(full_prompt)

                        # Run agent loop - receive messages and check for user input
                        while not agent_stop_flags.get(session_id, False):
                            try:
                                # Check for stop flag immediately at start of loop
                                if agent_stop_flags.get(session_id, False):
                                    print(f"Session {session_id}: Stop flag detected at loop start")
                                    break

                                # Check for pending user messages BEFORE waiting for more
                                user_messages = []
                                if session_id in agent_message_queues:
                                    user_messages = agent_message_queues.pop(session_id, [])

                                if user_messages:
                                    # Send user messages to the agent
                                    for msg in user_messages:
                                        print(f"Session {session_id}: Sending user message: {msg[:50]}...")
                                        await client.query(msg)
                                        # Check stop flag after each message
                                        if agent_stop_flags.get(session_id, False):
                                            break
                                    if agent_stop_flags.get(session_id, False):
                                        break

                                # Check for stop message
                                if session_id in agent_stop_messages:
                                    stop_msg = agent_stop_messages.pop(session_id, "请停止任何操作！")
                                    print(f"Session {session_id}: Sending stop message: {stop_msg}")
                                    await client.query(stop_msg)
                                    agent_stop_flags[session_id] = True
                                    break

                                # Receive messages from agent with periodic stop checks
                                try:
                                    async for message in client.receive_messages():
                                        # Store each message as an event
                                        msg_type = getattr(message, 'type', 'unknown')
                                        msg_subtype = getattr(message, 'subtype', '')
                                        content = ""

                                        if hasattr(message, 'result'):
                                            content = str(message.result)
                                        elif hasattr(message, 'text'):
                                            content = str(message.text)
                                        elif hasattr(message, 'content'):
                                            content = str(message.content)

                                        if content:
                                            db_cursor.execute("""
                                                INSERT INTO session_events (session_id, event_type, role, content)
                                                VALUES (%s, %s, %s, %s)
                                            """, (session_id, f"{msg_type}_{msg_subtype}", "assistant", content))
                                            db_conn.commit()

                                        # Check for completion (agent finished its task)
                                        if hasattr(message, 'subtype') and message.subtype == 'finish':
                                            print(f"Session {session_id}: Agent finished task, waiting for user input...")
                                            break

                                        # Also check for user messages while receiving
                                        pending_messages = []
                                        if session_id in agent_message_queues:
                                            pending_messages = agent_message_queues.pop(session_id, [])
                                        if pending_messages:
                                            print(f"Session {session_id}: Got {len(pending_messages)} pending messages")
                                            for msg in pending_messages:
                                                print(f"Session {session_id}: Sending user message: {msg[:50]}...")
                                                await client.query(msg)

                                        # Check stop flag while receiving
                                        if agent_stop_flags.get(session_id, False):
                                            print(f"Session {session_id}: Stop flag detected during receive")
                                            break

                                    # After receiving all messages, check stop message again
                                    if agent_stop_flags.get(session_id, False):
                                        break

                                    if session_id in agent_stop_messages:
                                        stop_msg = agent_stop_messages.pop(session_id, "请停止任何操作！")
                                        print(f"Session {session_id}: Sending stop message: {stop_msg}")
                                        await client.query(stop_msg)
                                        agent_stop_flags[session_id] = True
                                        break
                                except asyncio.TimeoutError:
                                    # If receive_messages times out, check stop flag and continue
                                    if agent_stop_flags.get(session_id, False):
                                        print(f"Session {session_id}: Stop flag detected after timeout")
                                        break
                                    continue

                                # Check if we should continue waiting for user input
                                # Small delay before checking queue again
                                await asyncio.sleep(0.5)

                            except Exception as e:
                                print(f"Session {session_id}: Receive error: {e}")
                                if agent_stop_flags.get(session_id, False):
                                    break
                                await asyncio.sleep(2)

                        # Disconnect
                        await client.disconnect()

                        # Session ended - mark as completed
                        db_cursor.execute("UPDATE sessions SET status = 'completed' WHERE id = %s", (session_id,))
                        db_conn.commit()
                        db_cursor.close()
                        db_conn.close()

                        # Cleanup
                        if session_id in agent_message_queues:
                            del agent_message_queues[session_id]
                        if session_id in agent_stop_flags:
                            del agent_stop_flags[session_id]
                        if session_id in agent_stop_messages:
                            del agent_stop_messages[session_id]
                        if session_id in agent_clients:
                            del agent_clients[session_id]

                    except Exception as e:
                        print(f"Agent error: {e}")
                        try:
                            import psycopg2
                            db_conn = psycopg2.connect(
                                "postgresql://luca:MAZV1QjTbXyPTq1teRFaEH0T@localhost:5432/dev_orchestrator?client_encoding=utf8"
                            )
                            db_cursor = db_conn.cursor()
                            db_cursor.execute("UPDATE sessions SET status = 'failed' WHERE id = %s", (session_id,))
                            db_conn.commit()
                            db_cursor.close()
                            db_conn.close()
                        except:
                            pass
                        # Cleanup on error
                        if session_id in agent_message_queues:
                            del agent_message_queues[session_id]
                        if session_id in agent_stop_flags:
                            del agent_stop_flags[session_id]
                        if session_id in agent_stop_messages:
                            del agent_stop_messages[session_id]
                        if session_id in agent_clients:
                            del agent_clients[session_id]

                asyncio.run(agent_task())

            # Start agent in background thread
            agent_thread = threading.Thread(target=run_agent, daemon=True)
            agent_thread.start()

            # Return the session immediately
            conn.commit()
            conn.close()
            return dict(session,
                created_at=str(session['created_at']) if session['created_at'] else None,
                started_at=str(session['started_at']) if session['started_at'] else None,
                completed_at=str(session['completed_at']) if session['completed_at'] else None
            )

        except ImportError:
            raise HTTPException(status_code=500, detail="claude-agent-sdk not installed")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to start agent: {str(e)}")
    else:
        # Legacy tmux mode - keep existing behavior
        prompt_file = worker.get('prompt_file_path', '')

        if not prompt_file:
            system_prompt = worker.get('prompt_template', '')
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                f.write(system_prompt)
                prompt_file = f.name
            use_temp_file = True
        else:
            use_temp_file = False

        run_command = [
            "/home/claude/claude-run.sh",
            "--session=" + tmux_session,
            "--project=" + project['local_path'],
            "--prompt-file=" + prompt_file,
            "--init-msg=" + user_prompt,
            "--footer-msg=" + footer_prompt
        ]
        run_command_str = " ".join(run_command)

        try:
            subprocess.Popen(run_command)
        except Exception as e:
            if use_temp_file and prompt_file:
                os.unlink(prompt_file)
            raise HTTPException(status_code=500, detail=f"Failed to start agent: {str(e)}")

        if use_temp_file and prompt_file:
            os.unlink(prompt_file)

        cursor.execute("""
            INSERT INTO sessions (issue_id, project_id, branch, worktree_path, status, agent_type, worker_id, runtime, log_path, tmux_session, command, started_at)
            VALUES (%s, %s, %s, %s, 'running', %s, %s, %s, %s, %s, %s, NOW())
            RETURNING *
        """, (
            issue['id'],
            project['id'],
            branch_name,
            worktree_path,
            worker.get('agent_type', 'claude-code'),
            worker.get('id'),
            'tmux',
            log_path,
            tmux_session,
            run_command_str
        ))

    session = cursor.fetchone()
    session_id = session['id']

    # Update issue status
    cursor.execute("UPDATE issues SET status = 'in_progress' WHERE id = %s", (issue['id'],))

    conn.commit()
    conn.close()

    return dict(session,
        created_at=str(session['created_at']) if session['created_at'] else None,
        started_at=str(session['started_at']) if session['started_at'] else None,
        completed_at=str(session['completed_at']) if session['completed_at'] else None
    )


@app.delete("/api/sessions/{session_id}/data")
def delete_session_data(session_id: int):
    """Delete session, session events, worktree and branch."""
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    # Get session info first
    cursor.execute("SELECT * FROM sessions WHERE id = %s", (session_id,))
    session = cursor.fetchone()

    if not session:
        conn.close()
        raise HTTPException(status_code=404, detail="Session not found")

    worktree_path = session.get("worktree_path")
    branch = session.get("branch")
    project_path = None

    # Get project path
    if session.get("project_id"):
        cursor.execute("SELECT local_path FROM projects WHERE id = %s", (session["project_id"],))
        project = cursor.fetchone()
        if project:
            project_path = project["local_path"]

    # Stop agent if running (for agent-sdk mode)
    if session_id in agent_stop_flags:
        agent_stop_flags[session_id] = True
    if session_id in agent_message_queues:
        try:
            del agent_message_queues[session_id]
        except:
            pass

    # Delete session events first
    cursor.execute("DELETE FROM session_events WHERE session_id = %s", (session_id,))

    # Delete session
    cursor.execute("DELETE FROM sessions WHERE id = %s", (session_id,))
    conn.commit()
    conn.close()

    # Clean up git worktree and branch
    if worktree_path and project_path and branch:
        try:
            # First try normal worktree removal
            result = subprocess.run(
                ["git", "-C", project_path, "worktree", "remove", "--force", worktree_path],
                capture_output=True, timeout=30
            )
            if result.returncode != 0:
                # If that fails, try cleaning up stale worktree entries
                subprocess.run(["git", "-C", project_path, "worktree", "prune"], capture_output=True)
                # Try to remove the directory directly if it's orphaned
                if os.path.exists(worktree_path):
                    import shutil
                    shutil.rmtree(worktree_path, ignore_errors=True)
                # Remove worktree entry from .git/worktrees if it exists
                worktree_git_dir = os.path.join(project_path, ".git", "worktrees", os.path.basename(worktree_path))
                if os.path.exists(worktree_git_dir):
                    import shutil
                    shutil.rmtree(worktree_git_dir, ignore_errors=True)
            print(f"Removed worktree: {worktree_path}")
        except Exception as e:
            print(f"Failed to remove worktree: {e}")
            # Try direct cleanup as fallback
            try:
                if os.path.exists(worktree_path):
                    import shutil
                    shutil.rmtree(worktree_path, ignore_errors=True)
            except:
                pass

        try:
            # Delete branch
            subprocess.run(["git", "-C", project_path, "branch", "-D", branch],
                          capture_output=True, timeout=30)
            print(f"Deleted branch: {branch}")
        except Exception as e:
            print(f"Failed to delete branch: {e}")

    return {"message": "Session data deleted"}


@app.delete("/api/sessions")
def clear_all_sessions():
    """Clear all sessions and session events."""
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    # Get all sessions first to clean up worktrees
    cursor.execute("SELECT * FROM sessions")
    sessions = cursor.fetchall()

    # Get project paths
    project_paths = {}
    for s in sessions:
        if s.get("project_id") and s["project_id"] not in project_paths:
            cursor.execute("SELECT local_path FROM projects WHERE id = %s", (s["project_id"],))
            project = cursor.fetchone()
            if project:
                project_paths[s["project_id"]] = project["local_path"]

    # Clean up worktrees and branches for all sessions
    for session in sessions:
        worktree_path = session.get("worktree_path")
        branch = session.get("branch")
        project_id = session.get("project_id")
        project_path = project_paths.get(project_id) if project_id else None

        if worktree_path and project_path and branch:
            try:
                subprocess.run(["git", "-C", project_path, "worktree", "remove", "--force", worktree_path],
                              capture_output=True, timeout=30)
            except:
                pass
            try:
                subprocess.run(["git", "-C", project_path, "branch", "-D", branch],
                              capture_output=True, timeout=30)
            except:
                pass
            # Also try to remove the directory if it still exists
            if os.path.exists(worktree_path):
                import shutil
                shutil.rmtree(worktree_path, ignore_errors=True)

    # Delete from database
    cursor.execute("DELETE FROM session_events")
    cursor.execute("DELETE FROM sessions")
    conn.commit()
    conn.close()
    return {"message": "All sessions cleared"}


# 泛化路由放最后兜底 - 必须放在所有具体路由之后
@app.get("/api/sessions/{session_id}", response_model=SessionResponse)
def get_session(session_id: int):
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("SELECT * FROM sessions WHERE id = %s", (session_id,))
    session = cursor.fetchone()
    conn.close()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return dict(session,
        created_at=str(session['created_at']) if session['created_at'] else None,
        started_at=str(session['started_at']) if session['started_at'] else None,
        completed_at=str(session['completed_at']) if session['completed_at'] else None
    )


@app.delete("/api/sessions/{session_id}")
def kill_session(session_id: int):
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    # Get session info for cleanup
    cursor.execute("SELECT * FROM sessions WHERE id = %s", (session_id,))
    session = cursor.fetchone()

    worktree_path = session.get("worktree_path") if session else None
    branch = session.get("branch") if session else None
    project_path = None

    if session and session.get("project_id"):
        cursor.execute("SELECT local_path FROM projects WHERE id = %s", (session["project_id"],))
        project = cursor.fetchone()
        if project:
            project_path = project["local_path"]

    # Check if there's an active process to kill (for stream-json mode)
    if session_id in active_sessions:
        try:
            session_data = active_sessions[session_id]
            process = session_data.get("process")
            if process and process.poll() is None:
                process.terminate()
                process.wait(timeout=5)
        except Exception as e:
            print(f"Error killing process: {e}")
        finally:
            del active_sessions[session_id]

    # For agent-sdk mode, call interrupt to stop the agent
    if session_id in agent_clients:
        try:
            import asyncio
            client = agent_clients[session_id]
            asyncio.run(client.interrupt())
            print(f"Session {session_id}: Called interrupt")
        except Exception as e:
            print(f"Error calling interrupt: {e}")
        finally:
            try:
                del agent_clients[session_id]
            except:
                pass

    cursor.execute("""
        UPDATE sessions SET status = 'failed', completed_at = NOW()
        WHERE id = %s
    """, (session_id,))
    conn.commit()
    conn.close()

    # Clean up worktree and branch
    if worktree_path and project_path and branch:
        try:
            subprocess.run(["git", "-C", project_path, "worktree", "remove", "--force", worktree_path],
                          capture_output=True, timeout=30)
        except:
            pass
        try:
            if os.path.exists(worktree_path):
                import shutil
                shutil.rmtree(worktree_path, ignore_errors=True)
        except:
            pass
        try:
            subprocess.run(["git", "-C", project_path, "branch", "-D", branch],
                          capture_output=True, timeout=30)
        except:
            pass

    return {"message": "Session killed"}


@app.get("/api/sessions/{session_id}/log")
def get_session_log(session_id: int):
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("SELECT log_path FROM sessions WHERE id = %s", (session_id,))
    session = cursor.fetchone()
    conn.close()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    log_path = session.get('log_path')
    if not log_path:
        return {"content": ""}

    try:
        # Read last 100 lines
        result = subprocess.run(
            ["tail", "-n", "100", log_path],
            capture_output=True,
            text=True,
            timeout=5
        )
        # Return raw content - xterm.js will handle ANSI codes
        # Filter out problematic Unicode characters
        import re
        content = result.stdout

        # Remove ALL escape sequences (complete reset)
        # Match any escape character followed by any sequence
        content = re.sub(r'\x1b\[[0-9;?]*[a-zA-Z]', '', content)  # CSI sequences
        content = re.sub(r'\x1b\][^\x07]*\x07', '', content)  # OSC sequences
        content = re.sub(r'\x1b[()][AB012]', '', content)  # ESC sequences
        content = re.sub(r'\x1b', '', content)  # Any remaining ESC

        # Remove bracketed paste mode sequences
        content = re.sub(r'\?2026[hl]', '', content)
        content = re.sub(r'\?2004[hl]', '', content)
        content = re.sub(r'\?[^ ]+', '', content)  # Any bracketed mode

        # Replace ALL special Unicode characters with spaces
        content = re.sub(r'[↔↕▚■●◉○▪▫▬▲▼◀▶◆◇□■]', ' ', content)
        content = re.sub(r'[░▒▓]', ' ', content)
        content = re.sub(r'[─│┌┐└┘├┤┬┴┼═║╔╗╚╝╠╣╦╩╬]', ' ', content)
        # Replace Unicode bullets and dots
        content = re.sub(r'[•·●○◦◉◎]', ' ', content)
        # Replace thinking indicators and arrows
        content = re.sub(r'[◼◻◽◾▤▥▦▧▨▩▪▫]', ' ', content)
        # Replace fancy arrows
        content = re.sub(r'[←→↑↓↔↕⇐⇒]', ' ', content)
        # Replace TUI indicators (the main offenders)
        content = re.sub(r'[✽✻✶✢✱✿❯⎿◼︎✓✕★☆♡♥♢♧]', ' ', content)
        # Replace more box chars
        content = re.sub(r'[┏┓┗┛━┃┏┓┗┛]', ' ', content)
        # Replace any remaining special Unicode in common ranges
        content = re.sub(r'[\u2500-\u259F]', ' ', content)  # Box Drawing
        content = re.sub(r'[\u2500-\u259F]', ' ', content)

        # Collapse multiple spaces
        content = re.sub(r' +', ' ', content)

        # Remove thinking indicators and status markers
        content = re.sub(r'\*+', '', content)  # Remove * markers
        content = re.sub(r'\([^)]*thinking[^)]*\)', '', content)  # Remove (thinking) patterns
        content = re.sub(r'\(thought for \d+s\)', '', content)  # Remove thought timers
        content = re.sub(r'\(ctrl\+[^)]+\)', '', content)  # Remove ctrl hints
        content = re.sub(r'[⏵⏶⏷⏸⏹⏺]', '', content)  # Remove control symbols

        # Collapse again after removal
        content = re.sub(r' +', ' ', content)
        # Remove empty lines
        content = re.sub(r'\n\s*\n', '\n', content)

        return {"content": content}
    except Exception as e:
        return {"content": f"Error reading log: {str(e)}"}


# Stream-json mode API endpoints
@app.get("/api/sessions/{session_id}/events")
def get_session_events(session_id: int, after_id: int = 0):
    """Get events for a session (for stream-json mode). Supports incremental fetching with after_id parameter."""
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    # Check if session exists and is stream-json mode
    cursor.execute("SELECT runtime, status FROM sessions WHERE id = %s", (session_id,))
    session = cursor.fetchone()
    if not session:
        conn.close()
        raise HTTPException(status_code=404, detail="Session not found")

    # Get events - optionally filter by after_id for incremental fetching
    if after_id > 0:
        cursor.execute("""
            SELECT id, event_type, role, content, tool_name, tool_input, created_at
            FROM session_events
            WHERE session_id = %s AND id > %s
            ORDER BY created_at ASC, id ASC
        """, (session_id, after_id))
    else:
        cursor.execute("""
            SELECT id, event_type, role, content, tool_name, tool_input, created_at
            FROM session_events
            WHERE session_id = %s
            ORDER BY created_at ASC, id ASC
        """, (session_id,))
    events = cursor.fetchall()
    conn.close()

    # Convert to dict list
    result = []
    for e in events:
        result.append({
            "id": e["id"],
            "type": e["event_type"],
            "role": e["role"],
            "content": e["content"],
            "tool_name": e["tool_name"],
            "tool_input": e["tool_input"],
            "created_at": str(e["created_at"]) if e["created_at"] else None
        })

    return {"events": result, "status": session["status"]}


@app.get("/api/sessions/{session_id}/history")
def get_session_history(session_id: int):
    """Get conversation history for a session."""
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    cursor.execute("SELECT runtime FROM sessions WHERE id = %s", (session_id,))
    session = cursor.fetchone()
    if not session:
        conn.close()
        raise HTTPException(status_code=404, detail="Session not found")

    # Get events grouped by role
    cursor.execute("""
        SELECT role, content, tool_name, tool_input, created_at
        FROM session_events
        WHERE session_id = %s AND role IS NOT NULL AND role != ''
        ORDER BY created_at ASC, id ASC
    """, (session_id,))
    events = cursor.fetchall()
    conn.close()

    # Build conversation history
    history = []
    for e in events:
        entry = {
            "role": e["role"],
            "content": e["content"]
        }
        if e["tool_name"]:
            entry["tool"] = e["tool_name"]
            try:
                entry["tool_input"] = json.loads(e["tool_input"]) if e["tool_input"] else {}
            except:
                entry["tool_input"] = e["tool_input"]
        history.append(entry)

    return {"history": history}


class MessageInput(BaseModel):
    content: str
    role: str = "user"


@app.post("/api/sessions/{session_id}/messages")
def send_session_message(session_id: int, message: MessageInput):
    """Send a message to the agent (for stream-json and agent-sdk modes)."""
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    # Check if session exists
    cursor.execute("SELECT runtime, status, process_id FROM sessions WHERE id = %s", (session_id,))
    session = cursor.fetchone()
    if not session:
        conn.close()
        raise HTTPException(status_code=404, detail="Session not found")

    if session["status"] != "running":
        conn.close()
        raise HTTPException(status_code=400, detail="Session is not running")

    # Store user message in events (works for both stream-json and agent-sdk)
    cursor.execute("""
        INSERT INTO session_events (session_id, event_type, role, content)
        VALUES (%s, 'message', %s, %s)
    """, (session_id, message.role, message.content))
    conn.commit()

    # For stream-json mode, send to process
    if session["runtime"] == "stream-json":
        # Check if we have an active process
        if session_id not in active_sessions:
            conn.close()
            raise HTTPException(status_code=400, detail="Session process not found")

        session_data = active_sessions[session_id]
        process = session_data["process"]

        # Check if process is still running
        if process.poll() is not None:
            cursor.execute("UPDATE sessions SET status = 'completed' WHERE id = %s", (session_id,))
            conn.commit()
            conn.close()
            raise HTTPException(status_code=400, detail="Session process has ended")

        try:
            # Send message to process
            msg = {
                "role": message.role,
                "content": message.content
            }
            process.stdin.write(json.dumps(msg) + "\n")
            process.stdin.flush()
        except Exception as e:
            conn.close()
            raise HTTPException(status_code=500, detail=f"Failed to send message: {str(e)}")

    # For agent-sdk mode, add message to queue for the agent loop to process
    elif session["runtime"] == "agent-sdk":
        # Auto-initialize if missing (agent may be starting)
        if session_id not in agent_message_queues:
            agent_message_queues[session_id] = []

        # Add message to queue
        if session_id not in agent_message_queues:
            agent_message_queues[session_id] = []
        agent_message_queues[session_id].append(message.content)
        print(f"Session {session_id}: Queued message: {message.content[:50]}...")

    conn.close()
    return {"message": "Message sent"}


# Workers
# Config API
@app.get("/api/config")
def get_config():
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("SELECT key, value FROM config")
    rows = cursor.fetchall()
    # Handle RealDictRow
    config = {row['key']: row['value'] for row in rows}
    conn.close()
    return config


@app.post("/api/config")
def update_config(config_data: dict):
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    for key, value in config_data.items():
        cursor.execute(
            "INSERT INTO config (key, value) VALUES (%s, %s) ON CONFLICT (key) DO UPDATE SET value = %s",
            (key, value, value)
        )
    conn.commit()
    conn.close()
    return {"success": True}


@app.get("/api/workers", response_model=List[WorkerResponse])
def list_workers():
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("SELECT * FROM workers")
    workers = cursor.fetchall()
    conn.close()
    return list(workers)


@app.post("/api/workers", response_model=WorkerResponse)
def create_worker(worker: WorkerCreate):
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    cursor.execute("""
        INSERT INTO workers (name, emoji, agent_type, prompt_template)
        VALUES (%s, %s, %s, %s)
        RETURNING *
    """, (worker.name, worker.emoji, worker.agent_type, worker.prompt_template))
    new_worker = cursor.fetchone()
    conn.commit()
    conn.close()
    return dict(new_worker)


@app.get("/api/workers/{worker_id}", response_model=WorkerResponse)
def get_worker(worker_id: int):
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("SELECT * FROM workers WHERE id = %s", (worker_id,))
    worker = cursor.fetchone()
    conn.close()
    if not worker:
        raise HTTPException(status_code=404, detail="Worker not found")
    return dict(worker)


@app.put("/api/workers/{worker_id}", response_model=WorkerResponse)
def update_worker(worker_id: int, worker_update: WorkerUpdate):
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    # Check if worker exists
    cursor.execute("SELECT * FROM workers WHERE id = %s", (worker_id,))
    worker = cursor.fetchone()
    if not worker:
        conn.close()
        raise HTTPException(status_code=404, detail="Worker not found")

    update_fields = []
    update_values = []

    if worker_update.name is not None:
        update_fields.append("name = %s")
        update_values.append(worker_update.name)
    if worker_update.emoji is not None:
        update_fields.append("emoji = %s")
        update_values.append(worker_update.emoji)
    if worker_update.agent_type is not None:
        update_fields.append("agent_type = %s")
        update_values.append(worker_update.agent_type)
    if worker_update.prompt_template is not None:
        update_fields.append("prompt_template = %s")
        update_values.append(worker_update.prompt_template)
    if worker_update.is_builtin is not None:
        update_fields.append("is_builtin = %s")
        update_values.append(worker_update.is_builtin)

    if update_fields:
        update_values.append(worker_id)
        cursor.execute(
            f"UPDATE workers SET {', '.join(update_fields)} WHERE id = %s RETURNING *",
            update_values
        )
        updated_worker = cursor.fetchone()
        conn.commit()
    else:
        updated_worker = worker

    conn.close()
    return dict(updated_worker)


@app.delete("/api/workers/{worker_id}")
def delete_worker(worker_id: int):
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    # Check if worker exists
    cursor.execute("SELECT * FROM workers WHERE id = %s", (worker_id,))
    worker = cursor.fetchone()
    if not worker:
        conn.close()
        raise HTTPException(status_code=404, detail="Worker not found")

    # Prevent deleting builtin workers
    if worker.get('is_builtin'):
        conn.close()
        raise HTTPException(status_code=400, detail="Cannot delete builtin worker")

    cursor.execute("DELETE FROM workers WHERE id = %s", (worker_id,))
    conn.commit()
    conn.close()
    return {"message": "Worker deleted"}


# Project Workers
@app.get("/api/projects/{project_id}/workers", response_model=List[ProjectWorkerResponse])
def list_project_workers(project_id: int):
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("""
        SELECT pw.*, w.name as worker_name, w.emoji, w.agent_type
        FROM project_workers pw
        JOIN workers w ON pw.worker_id = w.id
        WHERE pw.project_id = %s
        ORDER BY pw.created_at DESC
    """, (project_id,))
    workers = cursor.fetchall()
    conn.close()
    return [dict(w, created_at=str(w['created_at'])) for w in workers]


@app.post("/api/projects/{project_id}/workers", response_model=ProjectWorkerResponse)
def create_project_worker(project_id: int, pw: ProjectWorkerCreate):
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    # Verify project exists
    cursor.execute("SELECT id FROM projects WHERE id = %s", (project_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Project not found")

    # Verify worker exists
    cursor.execute("SELECT id FROM workers WHERE id = %s", (pw.worker_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Worker not found")

    cursor.execute("""
        INSERT INTO project_workers (project_id, worker_id, custom_prompt_template)
        VALUES (%s, %s, %s)
        ON CONFLICT (project_id, worker_id)
        DO UPDATE SET custom_prompt_template = EXCLUDED.custom_prompt_template
        RETURNING *
    """, (project_id, pw.worker_id, pw.custom_prompt_template))
    new_pw = cursor.fetchone()
    conn.commit()
    conn.close()
    return dict(new_pw, created_at=str(new_pw['created_at']))


@app.put("/api/projects/{project_id}/workers/{pw_id}", response_model=ProjectWorkerResponse)
def update_project_worker(project_id: int, pw_id: int, pw_update: ProjectWorkerUpdate):
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    cursor.execute("SELECT * FROM project_workers WHERE id = %s AND project_id = %s", (pw_id, project_id))
    pw = cursor.fetchone()
    if not pw:
        conn.close()
        raise HTTPException(status_code=404, detail="Project worker not found")

    update_fields = []
    update_values = []

    if pw_update.custom_prompt_template is not None:
        update_fields.append("custom_prompt_template = %s")
        update_values.append(pw_update.custom_prompt_template)

    if update_fields:
        update_values.append(pw_id)
        cursor.execute(
            f"UPDATE project_workers SET {', '.join(update_fields)} WHERE id = %s RETURNING *",
            update_values
        )
        updated_pw = cursor.fetchone()
        conn.commit()
    else:
        updated_pw = pw

    conn.close()
    return dict(updated_pw, created_at=str(updated_pw['created_at']))


@app.delete("/api/projects/{project_id}/workers/{pw_id}")
def delete_project_worker(project_id: int, pw_id: int):
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("DELETE FROM project_workers WHERE id = %s AND project_id = %s RETURNING id", (pw_id, project_id))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="Project worker not found")
    conn.commit()
    conn.close()
    return {"message": "Project worker deleted"}


# Get effective worker for a project (for starting sessions)
@app.get("/api/projects/{project_id}/effective-worker")
def get_effective_worker(project_id: int, worker_id: int):
    """Get the effective worker for a project with specific worker_id, considering project-level overrides"""
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    # Check project worker override first
    cursor.execute("""
        SELECT pw.*, w.name as worker_name, w.agent_type, w.prompt_template as base_prompt
        FROM project_workers pw
        JOIN workers w ON pw.worker_id = w.id
        WHERE pw.project_id = %s AND pw.worker_id = %s
    """, (project_id, worker_id))
    project_worker = cursor.fetchone()

    if project_worker:
        conn.close()
        return {
            "worker_id": project_worker['worker_id'],
            "worker_name": project_worker['worker_name'],
            "agent_type": project_worker['agent_type'],
            "prompt_template": project_worker['custom_prompt_template'] or project_worker['base_prompt']
        }

    # Fall back to system worker
    cursor.execute("SELECT * FROM workers WHERE id = %s", (worker_id,))
    system_worker = cursor.fetchone()

    conn.close()

    if system_worker:
        return {
            "worker_id": system_worker['id'],
            "worker_name": system_worker['name'],
            "agent_type": system_worker['agent_type'],
            "prompt_template": system_worker['prompt_template']
        }

    raise HTTPException(status_code=404, detail="Worker not found")


# Get worker for issue based on status
@app.get("/api/issues/{issue_id}/next-worker")
def get_next_worker(issue_id: int):
    """Get the appropriate worker for an issue based on its current status"""
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    # Get issue with project info
    cursor.execute("""
        SELECT i.*, p.id as project_id
        FROM issues i
        JOIN projects p ON i.project_id = p.id
        WHERE i.id = %s
    """, (issue_id,))
    issue = cursor.fetchone()

    if not issue:
        conn.close()
        raise HTTPException(status_code=404, detail="Issue not found")

    project_id = issue['project_id']
    status = issue['status']

    # Map status to worker name
    worker_map = {
        'pending': 'Developer',
        'in_progress': 'Developer',
        'need_review': 'Reviewer',
        'need_test': 'Tester'
    }

    worker_name = worker_map.get(status, 'Developer')

    # First check project worker
    cursor.execute("""
        SELECT pw.*, w.name as worker_name, w.emoji, w.agent_type, w.prompt_template as base_prompt
        FROM project_workers pw
        JOIN workers w ON pw.worker_id = w.id
        WHERE pw.project_id = %s AND w.name = %s
    """, (project_id, worker_name))
    project_worker = cursor.fetchone()

    if project_worker:
        conn.close()
        return {
            "worker_id": project_worker['worker_id'],
            "worker_name": project_worker['worker_name'],
            "emoji": project_worker.get('emoji', ''),
            "agent_type": project_worker['agent_type'],
            "prompt_template": project_worker['custom_prompt_template'] or project_worker['base_prompt'],
            "next_status": 'in_progress' if status == 'pending' else
                          'need_review' if status == 'in_progress' else
                          'need_test' if status == 'need_review' else 'done'
        }

    # Fall back to system worker
    cursor.execute("SELECT * FROM workers WHERE name = %s", (worker_name,))
    system_worker = cursor.fetchone()

    conn.close()

    if system_worker:
        return {
            "worker_id": system_worker['id'],
            "worker_name": system_worker['name'],
            "emoji": system_worker.get('emoji', ''),
            "agent_type": system_worker['agent_type'],
            "prompt_template": system_worker['prompt_template'],
            "next_status": 'in_progress' if status == 'pending' else
                          'need_review' if status == 'in_progress' else
                          'need_test' if status == 'need_review' else 'done'
        }

    raise HTTPException(status_code=404, detail=f"Worker '{worker_name}' not found")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
