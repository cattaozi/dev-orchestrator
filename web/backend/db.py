import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

# Load environment variables from project root
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env")
load_dotenv(env_path)

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
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS workers (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            emoji TEXT DEFAULT '',
            agent_type TEXT DEFAULT 'claude-code',
            prompt_template TEXT DEFAULT '',
            prompt_file_path TEXT DEFAULT '',
            is_builtin BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS project_workers (
            id SERIAL PRIMARY KEY,
            project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
            worker_id INTEGER REFERENCES workers(id) ON DELETE CASCADE,
            custom_prompt_template TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT NOW(),
            UNIQUE(project_id, worker_id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS prds (
            id SERIAL PRIMARY KEY,
            project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            version TEXT DEFAULT 'v1.0',
            content TEXT DEFAULT '',
            status TEXT DEFAULT 'draft',
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS issues (
            id SERIAL PRIMARY KEY,
            project_id INTEGER REFERENCES projects(id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            content TEXT DEFAULT '',
            status TEXT DEFAULT 'pending',
            worktree TEXT,
            branch TEXT,
            worktree_state TEXT DEFAULT 'none',
            branch_state TEXT DEFAULT 'none',
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)

    # Schema self-heal for legacy databases:
    # historical `issues.created_at` may be nullable and missing default.
    cursor.execute("ALTER TABLE issues ALTER COLUMN created_at SET DEFAULT NOW()")
    cursor.execute("UPDATE issues SET created_at = NOW() WHERE created_at IS NULL")
    cursor.execute("ALTER TABLE issues ALTER COLUMN created_at SET NOT NULL")

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
            command TEXT,
            prompt TEXT,
            started_at TIMESTAMP,
            completed_at TIMESTAMP
        )
    """)

    # Create session_events table for stream-json mode
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS session_events (
            id SERIAL PRIMARY KEY,
            session_id INTEGER REFERENCES sessions(id) ON DELETE CASCADE,
            event_type TEXT DEFAULT 'message',
            role TEXT DEFAULT 'user',
            content TEXT DEFAULT '',
            tool_name TEXT,
            tool_input TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)

    # Persist project-level chat session lifecycle for reconnect/status restore.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS project_chat_sessions (
            project_id INTEGER PRIMARY KEY,
            session_id INTEGER,
            status TEXT DEFAULT 'idle',
            last_active_at TIMESTAMP DEFAULT NOW(),
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS config (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    # Runtime services observed for each project (first version).
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS project_runtime_services (
            id SERIAL PRIMARY KEY,
            project_id INTEGER NOT NULL,
            pid INTEGER,
            port INTEGER,
            url TEXT,
            command TEXT,
            status TEXT DEFAULT 'running',
            started_at TIMESTAMP DEFAULT NOW(),
            last_seen_at TIMESTAMP DEFAULT NOW(),
            UNIQUE(project_id, pid, port)
        )
    """)

    # Managed service definitions and lifecycle state per project.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS project_services (
            id SERIAL PRIMARY KEY,
            project_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            start_command TEXT NOT NULL,
            stop_command TEXT DEFAULT '',
            workdir TEXT NOT NULL,
            port INTEGER,
            healthcheck_url TEXT DEFAULT '',
            status TEXT DEFAULT 'stopped',
            pid INTEGER,
            last_error TEXT DEFAULT '',
            last_started_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW(),
            UNIQUE(project_id, name)
        )
    """)

    # Generate worker prompt files
    _generate_worker_prompt_files(cursor)

    conn.commit()
    cursor.close()
    conn.close()


def _generate_worker_prompt_files(cursor):
    """Generate prompt files for built-in workers if they don't exist."""
    # Check if we have any workers
    cursor.execute("SELECT COUNT(*) as count FROM workers")
    result = cursor.fetchone()
    if result['count'] > 0:
        return

    # Create default workers
    workers = [
        ("Developer", "👨‍💻", "claude-code", "你是一个专业的开发工程师。负责根据需求实现功能，写单元测试，提交代码。"),
        ("Reviewer", "🔍", "claude-code", "你是一个专业的代码审查工程师。负责审查代码质量，提出改进建议。"),
        ("Tester", "🧪", "claude-code", "你是一个专业的测试工程师。负责编写测试用例，执行测试，发现并报告 bug。"),
    ]

    prompt_base_dir = os.path.expanduser("~/worker-prompts")
    os.makedirs(prompt_base_dir, exist_ok=True)

    for i, (name, emoji, agent_type, template) in enumerate(workers, start=1):
        # Write prompt to file
        prompt_file = os.path.join(prompt_base_dir, f"worker-{i}.txt")
        with open(prompt_file, 'w') as f:
            f.write(template)

        cursor.execute("""
            INSERT INTO workers (name, emoji, agent_type, prompt_template, prompt_file_path, is_builtin)
            VALUES (%s, %s, %s, %s, %s, TRUE)
        """, (name, emoji, agent_type, template, prompt_file))
