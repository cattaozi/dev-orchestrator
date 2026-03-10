# Session service - 业务逻辑层
from typing import List, Optional
import os
import subprocess
import threading
import tempfile
import asyncio

from db import get_db
from models import SessionResponse, SessionCreate
from psycopg2.extras import RealDictCursor


# Track active sessions for stream-json mode
active_sessions = {}

# Track SDK clients for agent-sdk mode
sdk_clients = {}

# Thread-local event loop for async operations
class AsyncRunner:
    """Wrapper to run async code in a thread."""
    _loop = None
    _thread = None

    @classmethod
    def run(cls, coro):
        """Run coroutine in dedicated thread with event loop."""
        if cls._loop is None or cls._loop.is_closed():
            def loop_thread():
                cls._loop = asyncio.new_event_loop()
                asyncio.set_event_loop(cls._loop)
                cls._loop.run_forever()

            cls._thread = threading.Thread(target=loop_thread, daemon=True)
            cls._thread.start()
            # Wait for loop to start
            import time
            time.sleep(0.1)

        # Submit coroutine to running loop
        future = asyncio.run_coroutine_threadsafe(coro, cls._loop)
        return future.result(timeout=60)


def _stream_json_reader(session_id: int, process: subprocess.Popen, project_path: str, init_message: str, footer_message: str):
    """Background thread to read claude output and store events in database."""
    import psycopg2
    from psycopg2.extras import RealDictCursor

    db_conn = psycopg2.connect(
        "postgresql://luca:MAZV1QjTbXyPTq1teRFaEH0T@localhost:5432/dev_orchestrator?client_encoding=utf8"
    )
    db_cursor = db_conn.cursor(cursor_factory=RealDictCursor)

    try:
        stdout_lines = []
        stderr_lines = []

        # Read stdout
        while True:
            line = process.stdout.readline()
            if not line:
                break
            stdout_lines.append(line)
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


def list_sessions() -> List[dict]:
    """获取所有 session 列表"""
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("""
        SELECT id, issue_id, project_id, branch, worktree_path, status, agent_type,
               worker_id, runtime, command, prompt, started_at, completed_at
        FROM sessions ORDER BY started_at DESC
    """)
    sessions = cursor.fetchall()
    conn.close()
    return [dict(s,
        started_at=str(s['started_at']) if s['started_at'] else None,
        completed_at=str(s['completed_at']) if s['completed_at'] else None
    ) for s in sessions]


def get_session_by_id(session_id: int) -> Optional[dict]:
    """根据 ID 获取 session"""
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("SELECT * FROM sessions WHERE id = %s", (session_id,))
    session = cursor.fetchone()
    conn.close()
    if session:
        return dict(session,
            started_at=str(session['started_at']) if session['started_at'] else None,
            completed_at=str(session['completed_at']) if session['completed_at'] else None
        )
    return None


def create_session(session_create: SessionCreate) -> dict:
    """创建 session"""
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    # Get issue info
    cursor.execute("SELECT * FROM issues WHERE id = %s", (session_create.issue_id,))
    issue = cursor.fetchone()
    if not issue:
        conn.close()
        raise ValueError("Issue not found")

    # Get project info
    cursor.execute("SELECT * FROM projects WHERE id = %s", (issue['project_id'],))
    project = cursor.fetchone()
    if not project:
        conn.close()
        raise ValueError("Project not found")

    # Get worker
    if not session_create.worker_id:
        conn.close()
        raise ValueError("worker_id is required")

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
            conn.close()
            raise ValueError("Worker not found")

    # Generate branch name
    branch_name = f"task/issue-{issue['id']}"
    worktree_path = f"/home/claude/worktrees/{issue['id']}"

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

    # Get footer prompt
    cursor.execute("SELECT value FROM config WHERE key = 'agent_footer_prompt'")
    config_result = cursor.fetchone()
    default_footer = f"""请在此分支 `{branch_name}` 上进行开发。
开发完成后，请：
1. 编写单元测试
2. 提交代码到 `{branch_name}` 分支
3. 汇报完成状态"""
    footer_prompt = config_result['value'] if config_result else default_footer

    runtime = session_create.runtime or "agent-sdk"

    if runtime == "stream-json":
        return _create_stream_json_session(cursor, conn, issue, project, worker, branch_name, worktree_path, footer_prompt)
    elif runtime == "agent-sdk":
        return _create_agent_sdk_session(cursor, conn, issue, project, worker, branch_name, worktree_path, footer_prompt)
    else:
        conn.close()
        raise ValueError(f"Unknown runtime: {runtime}")


def _create_stream_json_session(cursor, conn, issue, project, worker, branch_name, worktree_path, footer_prompt):
    """创建 stream-json 模式的 session"""
    prompt_file = worker.get('prompt_file_path', '')
    system_prompt = worker.get('prompt_template', '')

    if prompt_file and os.path.exists(prompt_file):
        with open(prompt_file, 'r') as f:
            system_prompt = f.read()

    user_prompt = issue.get('content', '') or issue.get('title', '')
    if not user_prompt:
        user_prompt = "Please help me with this issue."

    # Build footer prompt
    cursor.execute("SELECT value FROM config WHERE key = 'agent_footer_prompt'")
    config_result = cursor.fetchone()
    if config_result:
        footer_template = config_result['value']
        footer_prompt = footer_template.replace('{branch}', branch_name).replace('{project_path}', worktree_path)
    else:
        footer_prompt = f"\n\n---\n当前分支: {branch_name}\n项目路径: {worktree_path}\n请在此分支上进行开发工作。"

    full_prompt = f"{system_prompt}\n\n{user_prompt}\n\n{footer_prompt}"

    # Prepare environment
    env = os.environ.copy()
    env.pop("CLAUDECODE", None)
    env["ANTHROPIC_API_KEY"] = os.environ.get("ANTHROPIC_API_KEY", "")

    # Build claude command
    claude_cmd = [
        "env", "-u", "CLAUDECODE", "claude",
        "-p",
        "--output-format", "stream-json",
        "--dangerously-skip-permissions",
        "--verbose"
    ]

    if system_prompt:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as pf:
            pf.write(system_prompt)
            system_prompt_file = pf.name
        claude_cmd.extend(["--system-prompt-file", system_prompt_file])

    # Create session
    cursor.execute("""
        INSERT INTO sessions (issue_id, project_id, branch, worktree_path, status, agent_type, worker_id, runtime, command, started_at, prompt)
        VALUES (%s, %s, %s, %s, 'running', %s, %s, %s, %s, NOW(), %s)
        RETURNING *
    """, (
        issue['id'],
        project['id'],
        branch_name,
        worktree_path,
        worker.get('agent_type', 'claude-code'),
        worker.get('id'),
        'stream-json',
        " ".join(claude_cmd),
        full_prompt
    ))
    session = cursor.fetchone()
    if not session:
        conn.close()
        raise ValueError("Failed to create session")

    session_id = session['id']

    # Run claude process
    process = subprocess.Popen(
        claude_cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=worktree_path,
        env=env,
        text=False
    )
    active_sessions[session_id] = process

    # Send initial message
    process.stdin.write(full_prompt.encode('utf-8') + b'\n')
    process.stdin.flush()

    conn.commit()
    conn.close()

    return dict(session,
        started_at=str(session['started_at']) if session['started_at'] else None,
        completed_at=str(session['completed_at']) if session['completed_at'] else None
    )


def _create_agent_sdk_session(cursor, conn, issue, project, worker, branch_name, worktree_path, footer_prompt):
    """创建 agent-sdk 模式的 session - 使用 ClaudeSDKClient 支持双向对话"""
    try:
        from claude_agent_sdk import client as sdk_client
        from claude_agent_sdk import ClaudeAgentOptions
    except ImportError:
        raise ValueError("claude-agent-sdk not installed")

    prompt_file = worker.get('prompt_file_path', '')
    system_prompt = worker.get('prompt_template', '')

    if prompt_file and os.path.exists(prompt_file):
        with open(prompt_file, 'r') as f:
            system_prompt = f.read()

    user_prompt = issue.get('content', '') or issue.get('title', '')
    if not user_prompt:
        user_prompt = "Please help me with this issue."

    # Build footer prompt
    cursor.execute("SELECT value FROM config WHERE key = 'agent_footer_prompt'")
    config_result = cursor.fetchone()
    if config_result:
        footer_template = config_result['value']
        footer_prompt = footer_template.replace('{branch}', branch_name).replace('{project_path}', worktree_path)
    else:
        footer_prompt = f"\n\n---\n当前分支: {branch_name}\n项目路径: {worktree_path}\n请在此分支上进行开发工作。"

    full_prompt = f"{system_prompt}\n\n{user_prompt}\n\n{footer_prompt}"

    # Create session
    cursor.execute("""
        INSERT INTO sessions (issue_id, project_id, branch, worktree_path, status, agent_type, worker_id, runtime, command, started_at, prompt)
        VALUES (%s, %s, %s, %s, 'running', %s, %s, %s, %s, NOW(), %s)
        RETURNING *
    """, (
        issue['id'],
        project['id'],
        branch_name,
        worktree_path,
        worker.get('agent_type', 'claude-code'),
        worker.get('id'),
        'agent-sdk',
        "claude-agent-sdk",
        full_prompt
    ))
    session = cursor.fetchone()
    if not session:
        conn.close()
        raise ValueError("Failed to create session")

    session_id = session['id']

    # Store initial message as event
    cursor.execute("""
        INSERT INTO session_events (session_id, event_type, role, content)
        VALUES (%s, 'message', 'user', %s)
    """, (session_id, full_prompt))
    conn.commit()

    # Run agent using ClaudeSDKClient in background
    def run_agent(sid, prompt, worktree):
        import anyio
        from claude_agent_sdk import ClaudeAgentOptions

        async def agent_runner():
            # Unset CLAUDECODE to avoid nested session issues
            import os
            env = os.environ.copy()
            env.pop("CLAUDECODE", None)
            env["ANTHROPIC_API_KEY"] = os.environ.get("ANTHROPIC_API_KEY", "")

            # Create SDK client with working directory
            options = ClaudeAgentOptions(
                cwd=worktree,
                max_turns=100,
                env=env,
            )

            async with sdk_client.ClaudeSDKClient(options=options) as client:
                # Store client for later use (interrupt/query)
                sdk_clients[sid] = client
                print(f"Agent {sid}: Client registered, starting query...")

                try:
                    # Send the initial prompt
                    await client.query(prompt)

                    # Receive and process messages
                    async for message in client.receive_messages():
                        # Store message in DB
                        msg_type = getattr(message, 'type', 'unknown')
                        msg_content = str(message)

                        db_conn = get_db()
                        db_cursor = db_conn.cursor()
                        try:
                            db_cursor.execute("""
                                INSERT INTO session_events (session_id, event_type, role, content)
                                VALUES (%s, 'message', 'assistant', %s)
                            """, (sid, msg_content))
                            db_conn.commit()
                        except Exception as e:
                            print(f"Error storing message: {e}")
                        finally:
                            db_cursor.close()
                            db_conn.close()

                    # Mark as completed
                    db_conn = get_db()
                    db_cursor = db_conn.cursor()
                    db_cursor.execute("UPDATE sessions SET status = 'completed' WHERE id = %s", (sid,))
                    db_conn.commit()
                    db_cursor.close()
                    db_conn.close()
                except Exception as e:
                    print(f"Agent {sid} error: {e}")
                    import traceback
                    traceback.print_exc()
                    # Mark as failed
                    db_conn = get_db()
                    db_cursor = db_conn.cursor()
                    db_cursor.execute("UPDATE sessions SET status = 'failed' WHERE id = %s", (sid,))
                    db_conn.commit()
                    db_cursor.close()
                    db_conn.close()
                finally:
                    # Remove client when done
                    if sid in sdk_clients:
                        del sdk_clients[sid]

        # Run the async agent using anyio
        try:
            anyio.run(agent_runner)
        except Exception as e:
            print(f"Failed to run agent: {e}")
            import traceback
            traceback.print_exc()

    thread = threading.Thread(target=run_agent, args=(session_id, full_prompt, worktree_path))
    thread.start()

    conn.commit()
    conn.close()

    return dict(session,
        started_at=str(session['started_at']) if session['started_at'] else None,
        completed_at=str(session['completed_at']) if session['completed_at'] else None
    )


def delete_session_data(session_id: int):
    """删除 session 数据（保留记录）"""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM session_events WHERE session_id = %s", (session_id,))
    conn.commit()
    conn.close()


def clear_all_sessions():
    """清空所有 session"""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM session_events")
    cursor.execute("DELETE FROM sessions")
    conn.commit()
    conn.close()


def kill_session(session_id: int):
    """终止 session"""
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    cursor.execute("SELECT * FROM sessions WHERE id = %s", (session_id,))
    session = cursor.fetchone()

    runtime = session.get("runtime") if session else None
    worktree_path = session.get("worktree_path") if session else None
    branch = session.get("branch") if session else None
    project_path = None

    if session and session.get("project_id"):
        cursor.execute("SELECT local_path FROM projects WHERE id = %s", (session["project_id"],))
        project = cursor.fetchone()
        if project:
            project_path = project["local_path"]

    # Kill stream-json process
    if session_id in active_sessions:
        try:
            process = active_sessions[session_id]
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
            del active_sessions[session_id]
        except Exception as e:
            print(f"Error killing process: {e}")

    # Kill agent-sdk session via SDK client interrupt
    if runtime == "agent-sdk" and session_id in sdk_clients:
        try:
            client = sdk_clients[session_id]

            # Run interrupt in thread
            def do_interrupt():
                try:
                    import anyio
                    async def interrupt_async():
                        await client.interrupt()
                    anyio.run(interrupt_async)
                except Exception as e:
                    print(f"Error interrupting SDK client: {e}")

            interrupt_thread = threading.Thread(target=do_interrupt)
            interrupt_thread.start()
            interrupt_thread.join(timeout=10)

            del sdk_clients[session_id]
        except Exception as e:
            print(f"Error killing SDK session: {e}")

    # Clean up worktree
    if worktree_path and os.path.exists(worktree_path):
        try:
            subprocess.run(["git", "worktree", "remove", "--force", worktree_path], capture_output=True)
        except Exception:
            pass

    # Clean up branch
    if branch and project_path:
        try:
            subprocess.run(["git", "branch", "-D", branch], cwd=project_path, capture_output=True)
        except Exception:
            pass

    cursor.execute("UPDATE sessions SET status = 'cancelled' WHERE id = %s", (session_id,))
    conn.commit()
    conn.close()


def get_session_events(session_id: int, after_id: int = 0):
    """获取 session 事件"""
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    cursor.execute("""
        SELECT id, event_type, role, content, tool_name, tool_input, created_at
        FROM session_events
        WHERE session_id = %s AND id > %s
        ORDER BY created_at ASC, id ASC
    """, (session_id, after_id))
    events = cursor.fetchall()
    conn.close()

    return [
        {
            "id": e["id"],
            "event_type": e["event_type"],
            "role": e["role"],
            "content": e["content"],
            "tool_name": e["tool_name"],
            "tool_input": e["tool_input"],
            "created_at": str(e["created_at"]) if e["created_at"] else None
        }
        for e in events
    ]


def get_session_history(session_id: int):
    """获取 session 完整历史"""
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    cursor.execute("""
        SELECT role, content, tool_name, tool_input, created_at
        FROM session_events
        WHERE session_id = %s
        ORDER BY created_at ASC, id ASC
    """, (session_id,))
    events = cursor.fetchall()
    conn.close()

    return [
        {
            "role": e["role"],
            "content": e["content"],
            "tool_name": e["tool_name"],
            "tool_input": e["tool_input"],
            "created_at": str(e["created_at"]) if e["created_at"] else None
        }
        for e in events
    ]


def send_session_message(session_id: int, role: str, content: str):
    """发送消息到 session"""
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    cursor.execute("SELECT runtime, status FROM sessions WHERE id = %s", (session_id,))
    session = cursor.fetchone()
    if not session:
        conn.close()
        raise ValueError("Session not found")

    if session["status"] != "running":
        conn.close()
        raise ValueError("Session is not running")

    runtime = session["runtime"]

    # Store message
    cursor.execute("""
        INSERT INTO session_events (session_id, event_type, role, content)
        VALUES (%s, 'message', %s, %s)
    """, (session_id, role, content))
    conn.commit()

    # For stream-json mode, send to process
    if runtime == "stream-json":
        if session_id in active_sessions:
            process = active_sessions[session_id]
            process.stdin.write(content.encode('utf-8') + b'\n')
            process.stdin.flush()
        else:
            conn.close()
            raise ValueError("No active process for this session")

    # For agent-sdk mode, send via SDK client
    elif runtime == "agent-sdk":
        if session_id in sdk_clients:
            client = sdk_clients[session_id]

            # Run query in thread
            def do_query():
                try:
                    import anyio
                    async def query_async():
                        async for msg in await client.query(content):
                            pass
                    anyio.run(query_async)
                except Exception as e:
                    print(f"Error sending message via SDK: {e}")

            query_thread = threading.Thread(target=do_query)
            query_thread.start()
        else:
            conn.close()
            raise ValueError("No active agent for this session")

    conn.close()