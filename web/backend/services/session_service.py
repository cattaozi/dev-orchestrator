# Session service - 业务逻辑层
from loguru import logger
import re
from typing import List, Optional
import os
import subprocess
import threading
import asyncio

from db import get_db
from models import SessionResponse, SessionCreate
from psycopg2.extras import RealDictCursor

# Track SDK clients for agent-sdk mode
# Structure: {session_id: {"client": client, "loop": event_loop, "db_conn": db_connection}}
sdk_clients = {}


def _validate_path(path: str) -> bool:
    """校验路径安全：防止路径遍历攻击"""
    if not path:
        return False
    # 禁止 .. 路径遍历
    if '..' in path:
        return False
    # 禁止绝对路径逃逸
    if path.startswith('/') and not path.startswith('/home/claude/worktrees/'):
        return False
    return True


def _validate_branch_name(branch: str) -> bool:
    """校验分支名安全：防止命令注入"""
    if not branch:
        return False
    # Git 分支名只允许：字母、数字、-、_、/
    if not re.match(r'^[a-zA-Z0-9][a-zA-Z0-9/_.-]*$', branch):
        return False
    return True


def list_sessions() -> List[dict]:
    """获取所有 session 列表"""
    logger.debug("获取 session 列表")
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("""
        SELECT id, issue_id, project_id, branch, worktree_path, status, agent_type,
               worker_id, runtime, command, prompt, started_at, completed_at
        FROM sessions ORDER BY started_at DESC
    """)
    sessions = cursor.fetchall()
    conn.close()
    result = [dict(s,
        started_at=str(s['started_at']) if s['started_at'] else None,
        completed_at=str(s['completed_at']) if s['completed_at'] else None
    ) for s in sessions]
    logger.debug(f"返回 {len(result)} 个 sessions")
    return result


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
    logger.info(f"创建 session: issue_id={session_create.issue_id}, worker_id={session_create.worker_id}, runtime={session_create.runtime}")
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

    # Worktree path based on issue id
    worktree_path = f"/home/claude/worktrees/{issue['id']}"
    branch_name = f"task/issue-{issue['id']}"

    # 安全校验
    if not _validate_path(worktree_path):
        conn.close()
        raise ValueError(f"Invalid worktree path: {worktree_path}")
    if not _validate_branch_name(branch_name):
        conn.close()
        raise ValueError(f"Invalid branch name: {branch_name}")

    # Create worktree with dedicated branch (MVP: 强制物理隔离)
    try:
        if os.path.exists(worktree_path):
            logger.info(f"Worktree path already exists: {worktree_path}, reusing it")
        else:
            # 强制创建带分支的 Worktree
            subprocess.run(
                ["git", "worktree", "add", worktree_path, "-b", branch_name],
                cwd=project['local_path'],
                capture_output=True,
                timeout=30,
                check=True
            )
            logger.info(f"Created worktree at {worktree_path} with branch {branch_name}")
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to create worktree: {e.stderr}")
        conn.close()
        raise RuntimeError(f"Failed to create worktree: {e.stderr.decode() if e.stderr else str(e)}")
    except subprocess.TimeoutExpired:
        logger.error("Worktree creation timed out")
        conn.close()
        raise RuntimeError("Worktree creation timed out")

    # Get footer prompt with explicit branch instruction
    cursor.execute("SELECT value FROM config WHERE key = 'agent_footer_prompt'")
    config_result = cursor.fetchone()
    default_footer = f"""项目路径: {worktree_path}

请在此分支 `{branch_name}` 上进行开发工作。完成后请汇报结果。"""
    footer_prompt = config_result['value'] if config_result else default_footer

    return _create_agent_sdk_session(cursor, conn, issue, project, worker, worktree_path, branch_name, footer_prompt)


def _create_agent_sdk_session(cursor, conn, issue, project, worker, worktree_path, branch_name, footer_prompt):
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
        footer_prompt = config_result['value'].replace('{project_path}', worktree_path)

    full_prompt = f"{system_prompt}\n\n{user_prompt}\n\n{footer_prompt}"

    # Create session with branch
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

    # 更新 issue 表的 worktree 和 branch
    cursor.execute("""
        UPDATE issues SET worktree = %s, worktree_state = 'exists', branch = %s
        WHERE id = %s
    """, (worktree_path, branch_name, issue['id']))

    conn.commit()
    conn.close()

    # Run agent using ClaudeSDKClient in background thread with its own event loop
    def run_agent(sid, prompt, worktree):
        # Create a dedicated event loop for this agent
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # === 线程启动时获取一次 DB 连接，复用整个生命周期 ===
        db_conn = get_db()

        # 定义线程内复用的保存函数（使用同一个 db_conn）
        def save_message(role, content):
            """线程内复用连接保存消息"""
            try:
                with db_conn.cursor() as cursor:
                    cursor.execute(
                        "INSERT INTO session_events (session_id, event_type, role, content) VALUES (%s, 'message', %s, %s)",
                        (sid, role, content)
                    )
                db_conn.commit()
            except Exception as e:
                logger.error(f"DB Insert Error: {e}")
                db_conn.rollback()

        def update_status(status):
            """线程内复用连接更新状态"""
            try:
                with db_conn.cursor() as cursor:
                    cursor.execute("UPDATE sessions SET status = %s WHERE id = %s", (status, sid))
                db_conn.commit()
            except Exception as e:
                logger.error(f"DB Update Error: {e}")
                db_conn.rollback()

        async def agent_runner():
            # 清理环境变量，确保不使用云端 API Key（Devpilot 使用 claude-code 本地认证）
            # 必须显式设置为空字符串，不能只是删除（SDK 可能会继承父进程的环境）
            env = dict(os.environ)
            env["CLAUDECODE"] = ""  # 设置为空字符串以允许嵌套运行

            # Create SDK client with working directory
            options = ClaudeAgentOptions(
                cwd=worktree,
                max_turns=100,
                env=env,
            )

            async with sdk_client.ClaudeSDKClient(options=options) as client:
                # === 关键：在调用 query 之前就保存 client ===
                # 这样用户可以立即发送消息，不需要等待 query 完成
                sdk_clients[sid] = {"client": client, "loop": loop, "db_conn": db_conn}
                logger.info(f"Agent {sid}: Client registered with event loop, starting query...")

                try:
                    # Send the initial prompt
                    await client.query(prompt)

                    # Receive and process messages
                    async for message in client.receive_messages():
                        msg_content = str(message)
                        # 直接调用线程内复用的保存函数，不创建新连接
                        save_message('assistant', msg_content)

                    # Mark as completed
                    update_status('completed')

                except Exception as e:
                    logger.error(f"Agent {sid} error: {e}")
                    import traceback
                    traceback.print_exc()
                    # Mark as failed
                    update_status('failed')
                finally:
                    # Clean up worktree - 使用 check=True
                    if worktree and os.path.exists(worktree):
                        try:
                            subprocess.run(
                                ["git", "worktree", "remove", "--force", worktree],
                                capture_output=True,
                                check=True  # 防御性：失败时抛出异常
                            )
                        except subprocess.CalledProcessError as e:
                            logger.error(f"Failed to clean up worktree {worktree}: {e.stderr}")
                        except Exception as e:
                            logger.error(f"Error cleaning up worktree: {e}")

                    # Remove client when done
                    if sid in sdk_clients:
                        del sdk_clients[sid]

        # Run the async agent on this thread's event loop
        try:
            loop.run_until_complete(agent_runner())
        except Exception as e:
            logger.error(f"Failed to run agent: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # === 线程结束时统一关闭数据库连接 ===
            try:
                db_conn.close()
            except Exception as e:
                logger.error(f"Error closing db connection: {e}")
            loop.close()

    thread = threading.Thread(target=run_agent, args=(session_id, full_prompt, worktree_path))
    thread.daemon = True  # 确保主进程退出时自动回收
    thread.start()

    session_dict = dict(session,
        started_at=str(session['started_at']) if session['started_at'] else None,
        completed_at=str(session['completed_at']) if session['completed_at'] else None
    )
    return session_dict


def delete_session_data(session_id: int):
    """删除 session：只清理 session 和 session_events 表，不清理 worktree 和 branch（它们属于 issue）"""
    logger.info(f"删除 session {session_id}")
    conn = get_db()
    cursor = conn.cursor()

    # 删除 session events
    cursor.execute("DELETE FROM session_events WHERE session_id = %s", (session_id,))
    conn.commit()
    logger.info(f"已删除 session_events")

    # 删除 session 记录
    cursor.execute("DELETE FROM sessions WHERE id = %s", (session_id,))
    conn.commit()
    logger.info(f"已删除 session 记录")

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

    worktree_path = session.get("worktree_path") if session else None
    branch = session.get("branch") if session else None
    project_path = None

    if session and session.get("project_id"):
        cursor.execute("SELECT local_path FROM projects WHERE id = %s", (session["project_id"],))
        project = cursor.fetchone()
        if project:
            project_path = project["local_path"]

    # Kill agent-sdk session via SDK client interrupt
    # Use call_soon_threadsafe to safely invoke interrupt in the agent's event loop
    if session_id in sdk_clients:
        try:
            client_data = sdk_clients[session_id]
            client = client_data["client"]
            target_loop = client_data["loop"]

            def _interrupt_safe():
                """Create interrupt task in target loop"""
                asyncio.create_task(client.interrupt())

            # Safely schedule interrupt in the agent's event loop
            target_loop.call_soon_threadsafe(_interrupt_safe)

            # Wait a bit for interrupt to take effect
            import time
            time.sleep(0.5)

            del sdk_clients[session_id]
        except Exception as e:
            logger.error(f"Error killing SDK session: {e}")

    # Clean up worktree - 使用 check=True
    if worktree_path and os.path.exists(worktree_path):
        if not _validate_path(worktree_path):
            logger.warning(f"Invalid worktree path skipped: {worktree_path}")
        else:
            try:
                subprocess.run(
                    ["git", "worktree", "remove", "--force", worktree_path],
                    capture_output=True,
                    check=True  # 防御性：失败时抛出异常
                )
            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to remove worktree {worktree_path}: {e.stderr}")
            except Exception as e:
                logger.error(f"Error removing worktree: {e}")

    # Clean up branch - 使用 check=True
    if branch and project_path:
        if not _validate_branch_name(branch):
            logger.warning(f"Invalid branch name skipped: {branch}")
        else:
            try:
                subprocess.run(
                    ["git", "branch", "-D", branch],
                    cwd=project_path,
                    capture_output=True,
                    check=True  # 防御性：失败时抛出异常
                )
            except subprocess.CalledProcessError as e:
                logger.error(f"Failed to delete branch {branch}: {e.stderr}")
            except Exception as e:
                logger.error(f"Error deleting branch: {e}")

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

    cursor.execute("SELECT status FROM sessions WHERE id = %s", (session_id,))
    session = cursor.fetchone()
    if not session:
        conn.close()
        raise ValueError("Session not found")

    if session["status"] != "running":
        conn.close()
        raise ValueError("Session is not running")

    # Store message
    cursor.execute("""
        INSERT INTO session_events (session_id, event_type, role, content)
        VALUES (%s, 'message', %s, %s)
    """, (session_id, role, content))
    conn.commit()
    conn.close()

    # For agent-sdk mode, send via SDK client using run_coroutine_threadsafe
    if session_id in sdk_clients:
        client_data = sdk_clients[session_id]
        client = client_data["client"]
        target_loop = client_data["loop"]
        db_conn = client_data.get("db_conn")  # 复用线程的数据库连接

        async def _send_msg_task():
            """Async task to send message via SDK client"""
            try:
                async for msg in await client.query(content):
                    msg_content = str(msg)
                    # 使用线程复用的数据库连接保存消息
                    if db_conn:
                        try:
                            with db_conn.cursor() as cursor:
                                cursor.execute(
                                    "INSERT INTO session_events (session_id, event_type, role, content) VALUES (%s, 'message', %s, %s)",
                                    (session_id, 'assistant', msg_content)
                                )
                            db_conn.commit()
                        except Exception as e:
                            logger.error(f"DB Insert Error: {e}")
                            db_conn.rollback()
            except Exception as e:
                logger.error(f"Error sending message via SDK: {e}")

        # Safely push the coroutine to the agent's event loop (Fire and Forget)
        asyncio.run_coroutine_threadsafe(_send_msg_task(), target_loop)
    else:
        raise ValueError("No active agent for this session")