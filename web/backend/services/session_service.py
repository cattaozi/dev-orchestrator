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

NOISE_SYSTEM_SUBTYPES = ("init", "status", "compact_boundary")


def _detect_event_type(raw_content: str, role: str) -> str:
    """Infer a stable event_type from SDK raw message."""
    raw = (raw_content or "").strip()
    if role == "user":
        return "user_message"
    if raw.startswith("AssistantMessage("):
        return "assistant_message"
    if raw.startswith("SystemMessage("):
        return "system_message"
    if raw.startswith("ResultMessage("):
        return "result_message"
    if raw.startswith("TaskStartedMessage("):
        return "task_started"
    if raw.startswith("TaskNotificationMessage("):
        return "task_notification"
    return "message"


def _is_noise_event(raw_content: str, role: str) -> bool:
    """
    Filter low-signal SDK events before persistence.
    Keep user messages and meaningful assistant output.
    """
    raw = (raw_content or "").strip()
    if not raw:
        return True

    if role == "user":
        return False

    if raw.startswith("TaskStartedMessage(") or raw.startswith("TaskNotificationMessage("):
        return True

    if raw.startswith("SystemMessage("):
        return any(f"subtype='{subtype}'" in raw for subtype in NOISE_SYSTEM_SUBTYPES)

    if raw.startswith("ResultMessage(") and "subtype='success'" in raw:
        return True

    if (
        "ThinkingBlock(" in raw
        and "TextBlock(" not in raw
        and "ToolUseBlock(" not in raw
        and "ToolResultBlock(" not in raw
    ):
        return True

    return False


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


def _get_worker(cursor, project_id: int, worker_id: Optional[int]):
    """Resolve worker by project override or fallback to first available worker."""
    resolved_worker_id = worker_id
    if not resolved_worker_id:
        cursor.execute("""
            SELECT pw.worker_id
            FROM project_workers pw
            WHERE pw.project_id = %s
            ORDER BY pw.created_at ASC
            LIMIT 1
        """, (project_id,))
        row = cursor.fetchone()
        if row:
            resolved_worker_id = row['worker_id']
        else:
            cursor.execute("SELECT id FROM workers ORDER BY id ASC LIMIT 1")
            fallback = cursor.fetchone()
            if fallback:
                resolved_worker_id = fallback['id']

    if not resolved_worker_id:
        raise ValueError("No worker available")

    cursor.execute("""
        SELECT pw.*, w.name as worker_name, w.agent_type, w.prompt_template as base_prompt, w.prompt_file_path
        FROM project_workers pw
        JOIN workers w ON pw.worker_id = w.id
        WHERE pw.project_id = %s AND pw.worker_id = %s
    """, (project_id, resolved_worker_id))
    project_worker = cursor.fetchone()

    if project_worker:
        return {
            'id': project_worker['worker_id'],
            'name': project_worker['worker_name'],
            'agent_type': project_worker['agent_type'],
            'prompt_template': project_worker['custom_prompt_template'] or project_worker['base_prompt'],
            'prompt_file_path': project_worker.get('prompt_file_path', '')
        }

    cursor.execute("SELECT * FROM workers WHERE id = %s", (resolved_worker_id,))
    worker = cursor.fetchone()
    if not worker:
        raise ValueError("Worker not found")
    return worker


def _upsert_project_chat_session(cursor, project_id: int, session_id: Optional[int], status: str):
    cursor.execute("""
        INSERT INTO project_chat_sessions (project_id, session_id, status, last_active_at, updated_at)
        VALUES (%s, %s, %s, NOW(), NOW())
        ON CONFLICT (project_id) DO UPDATE SET
            session_id = EXCLUDED.session_id,
            status = EXCLUDED.status,
            last_active_at = NOW(),
            updated_at = NOW()
    """, (project_id, session_id, status))


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
    logger.info(
        f"创建 session: issue_id={session_create.issue_id}, project_id={session_create.project_id}, "
        f"worker_id={session_create.worker_id}, runtime={session_create.runtime}"
    )
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    issue = None
    if session_create.issue_id:
        cursor.execute("SELECT * FROM issues WHERE id = %s", (session_create.issue_id,))
        issue = cursor.fetchone()
        if not issue:
            conn.close()
            raise ValueError("Issue not found")
        project_id = issue['project_id']
        worktree_path = f"/home/claude/worktrees/{issue['id']}"
        branch_name = f"task/issue-{issue['id']}"
        prepare_worktree = True
        cleanup_worktree = True
    elif session_create.project_id:
        project_id = session_create.project_id
        worktree_path = ""
        branch_name = ""
        prepare_worktree = False
        cleanup_worktree = False
    else:
        conn.close()
        raise ValueError("Either issue_id or project_id is required")

    # Get project info
    cursor.execute("SELECT * FROM projects WHERE id = %s", (project_id,))
    project = cursor.fetchone()
    if not project:
        conn.close()
        raise ValueError("Project not found")

    try:
        worker = _get_worker(cursor, project['id'], session_create.worker_id)
    except ValueError:
        conn.close()
        raise

    if issue is None:
        selected_path = project.get('local_path')
        if not selected_path or not os.path.isdir(selected_path):
            conn.close()
            raise ValueError(f"Project local_path not found: {project.get('local_path')}")
        worktree_path = selected_path
        branch_name = project.get('default_branch') or "main"
    else:
        # 安全校验
        if not _validate_path(worktree_path):
            conn.close()
            raise ValueError(f"Invalid worktree path: {worktree_path}")
        if not _validate_branch_name(branch_name):
            conn.close()
            raise ValueError(f"Invalid branch name: {branch_name}")

    # ========== Worktree 初始化：幂等模式 (Idempotent Pattern) ==========
    # 目标：无论当前环境状态如何，最终一定能得到可工作的 worktree
    # 场景覆盖：
    #   1. 分支不存在，Worktree 不存在 -> 全新创建 (Add -b)
    #   2. 分支存在，Worktree 不存在 -> 切换到已有分支 (Add)
    #   3. 分支存在，Worktree 已存在 -> 直接重用 (Reuse)

    if prepare_worktree:
        try:
            # Step 0: 同步远端分支信息
            logger.info(f"Fetching latest from remote for project {project['local_path']}")
            subprocess.run(
                ["git", "fetch", "--all"],
                cwd=project['local_path'],
                capture_output=True,
                timeout=60,
                check=True
            )

            # Step 1: 检查 Worktree 是否已存在
            if os.path.exists(worktree_path):
                # 场景 3: Worktree 已存在，直接重用
                logger.info(f"Worktree already exists at {worktree_path}, reusing it")

                # 确保环境清洁：reset 到分支最新状态
                try:
                    subprocess.run(
                        ["git", "reset", "--hard", f"origin/{branch_name}"],
                        cwd=worktree_path,
                        capture_output=True,
                        timeout=30,
                        check=True
                    )
                    logger.info(f"Reset worktree to origin/{branch_name}")
                except subprocess.CalledProcessError as e:
                    # 如果远端分支不存在，尝试 reset 到本地分支
                    logger.warning(f"Failed to reset to origin/{branch_name}, trying local branch: {e.stderr.decode() if e.stderr else str(e)}")
                    try:
                        subprocess.run(
                            ["git", "reset", "--hard", branch_name],
                            cwd=worktree_path,
                            capture_output=True,
                            timeout=30,
                            check=True
                        )
                        logger.info(f"Reset worktree to local branch {branch_name}")
                    except subprocess.CalledProcessError as e2:
                        logger.warning(f"Failed to reset to local branch, continuing anyway: {e2.stderr.decode() if e2.stderr else str(e2)}")
            else:
                # Step 2: Worktree 不存在，需要创建
                try:
                    subprocess.run(
                        ["git", "worktree", "add", worktree_path, "-b", branch_name],
                        cwd=project['local_path'],
                        capture_output=True,
                        timeout=30,
                        check=True
                    )
                    logger.info(f"Created worktree at {worktree_path} with new branch {branch_name}")
                except subprocess.CalledProcessError as e:
                    error_msg = e.stderr.decode() if e.stderr else str(e)

                    # 检查是否是分支已存在的错误
                    if "already exists" in error_msg and "branch" in error_msg:
                        # 场景 2: 分支已存在，切换到已有分支
                        logger.info(f"Branch {branch_name} already exists, switching to existing branch")
                        try:
                            subprocess.run(
                                ["git", "worktree", "add", worktree_path, branch_name],
                                cwd=project['local_path'],
                                capture_output=True,
                                timeout=30,
                                check=True
                            )
                            logger.info(f"Created worktree at {worktree_path} using existing branch {branch_name}")

                            # 确保环境清洁
                            subprocess.run(
                                ["git", "reset", "--hard", f"origin/{branch_name}"],
                                cwd=worktree_path,
                                capture_output=True,
                                timeout=30,
                                check=True
                            )
                        except subprocess.CalledProcessError as e2:
                            error_msg2 = e2.stderr.decode() if e2.stderr else str(e2)
                            logger.error(f"Failed to create worktree with existing branch: {error_msg2}")
                            conn.close()
                            raise RuntimeError(f"Failed to create worktree: {error_msg2}")
                    else:
                        logger.error(f"Failed to create worktree: {error_msg}")
                        conn.close()
                        raise RuntimeError(f"Failed to create worktree: {error_msg}")

            # Step 3: 验证 worktree 最终状态
            if not os.path.exists(worktree_path):
                conn.close()
                raise RuntimeError(f"Worktree creation failed: path {worktree_path} does not exist")

            logger.info(f"Worktree ready at {worktree_path} with branch {branch_name}")

        except subprocess.TimeoutExpired:
            logger.error("Worktree operation timed out")
            conn.close()
            raise RuntimeError("Worktree operation timed out")

    initial_prompt = None
    persist_initial_event = True
    if issue is None:
        initial_prompt = (
            "你是项目级协作助手。当前会话用于快速问答与轻量修改。"
            "在收到用户消息前，不要主动输出。"
        )
        persist_initial_event = False

    return _create_agent_sdk_session(
        cursor,
        conn,
        issue,
        project,
        worker,
        worktree_path,
        branch_name,
        initial_prompt=initial_prompt,
        persist_initial_event=persist_initial_event,
        cleanup_worktree=cleanup_worktree,
    )


def _create_agent_sdk_session(
    cursor,
    conn,
    issue,
    project,
    worker,
    worktree_path,
    branch_name,
    initial_prompt: Optional[str] = None,
    persist_initial_event: bool = True,
    cleanup_worktree: bool = True,
):
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

    if initial_prompt is not None:
        user_prompt = initial_prompt
    elif issue:
        user_prompt = issue.get('content', '') or issue.get('title', '')
    else:
        user_prompt = "请等待用户输入后再继续。"
    if not user_prompt:
        user_prompt = "Please help me with this issue."

    # 环境信息由系统直接注入，不依赖模型推理
    if issue:
        env_info = f"""项目路径: {worktree_path}
分支: {branch_name}

请在此分支上进行开发工作。完成后请汇报结果。"""
    else:
        env_info = f"""项目路径: {worktree_path}
默认分支: {branch_name}

这是项目级快速对话会话，可先回答问题，再按用户要求执行修改。"""

    full_prompt = f"{system_prompt}\n\n{user_prompt}\n\n{env_info}"

    # Create session with branch
    cursor.execute("""
        INSERT INTO sessions (issue_id, project_id, branch, worktree_path, status, agent_type, worker_id, runtime, command, started_at, prompt)
        VALUES (%s, %s, %s, %s, 'running', %s, %s, %s, %s, NOW(), %s)
        RETURNING *
    """, (
        issue['id'] if issue else None,
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

    if persist_initial_event:
        cursor.execute("""
            INSERT INTO session_events (session_id, event_type, role, content)
            VALUES (%s, %s, 'user', %s)
        """, (session_id, _detect_event_type(full_prompt, "user"), full_prompt))

    if issue:
        # 更新 issue 表的 worktree 和 branch
        cursor.execute("""
            UPDATE issues SET worktree = %s, worktree_state = 'exists', branch = %s
            WHERE id = %s
        """, (worktree_path, branch_name, issue['id']))
    else:
        _upsert_project_chat_session(cursor, project['id'], session_id, 'running')

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
            if _is_noise_event(content, role):
                return
            try:
                event_type = _detect_event_type(content, role)
                with db_conn.cursor() as cursor:
                    cursor.execute(
                        "INSERT INTO session_events (session_id, event_type, role, content) VALUES (%s, %s, %s, %s)",
                        (sid, event_type, role, content)
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
                    cursor.execute("""
                        UPDATE project_chat_sessions
                        SET status = %s, last_active_at = NOW(), updated_at = NOW()
                        WHERE session_id = %s
                    """, (status, sid))
                db_conn.commit()
            except Exception as e:
                logger.error(f"DB Update Error: {e}")
                db_conn.rollback()

        async def agent_runner():
            # 清理环境变量，确保不使用云端 API Key（Devpilot 使用 claude-code 本地认证）
            # 必须显式设置为空字符串，不能只是删除（SDK 可能会继承父进程的环境）
            env = dict(os.environ)
            env["CLAUDECODE"] = ""  # 设置为空字符串以允许嵌套运行
            # 权限豁免：跳过所有交互式权限确认，实现全自动 AIDD 流程
            env["CLAUDECODE_DANGEROUSLY_SKIP_PERMISSIONS"] = "true"

            # Create SDK client with working directory
            # permission_mode='bypassPermissions' - SDK 原生参数跳过所有权限确认
            options = ClaudeAgentOptions(
                cwd=worktree,
                max_turns=100,
                env=env,
                permission_mode='bypassPermissions',
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
                    # Clean up worktree - issue sessions only
                    if cleanup_worktree and worktree and os.path.exists(worktree):
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


def get_project_chat_session(project_id: int) -> dict:
    """Get persisted project chat session state."""
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("SELECT id FROM projects WHERE id = %s", (project_id,))
    if not cursor.fetchone():
        conn.close()
        raise ValueError("Project not found")

    cursor.execute("""
        SELECT pcs.project_id, pcs.session_id, pcs.status, pcs.last_active_at, s.status AS session_status
        FROM project_chat_sessions pcs
        LEFT JOIN sessions s ON s.id = pcs.session_id
        WHERE pcs.project_id = %s
    """, (project_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return {
            "project_id": project_id,
            "session_id": None,
            "status": "idle",
            "last_active_at": None,
        }

    status = row["status"] or "idle"
    if row["session_id"] and row.get("session_status") == "running" and row["session_id"] not in sdk_clients:
        status = "stale"
    elif row.get("session_status"):
        status = row["session_status"]

    return {
        "project_id": row["project_id"],
        "session_id": row["session_id"],
        "status": status,
        "last_active_at": str(row["last_active_at"]) if row.get("last_active_at") else None,
    }


def create_project_chat_session(
    project_id: int,
    worker_id: Optional[int] = None,
    runtime: str = "agent-sdk",
    force_new: bool = False,
) -> dict:
    state = get_project_chat_session(project_id)
    existing_session_id = state.get("session_id")
    if existing_session_id:
        existing_session = get_session_by_id(existing_session_id)
        if existing_session and existing_session.get("status") == "running":
            if not force_new:
                return existing_session
            kill_session(existing_session_id)
    return create_session(SessionCreate(project_id=project_id, worker_id=worker_id, runtime=runtime))


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

    is_project_chat = bool(session and not session.get("issue_id"))
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
    if (not is_project_chat) and worktree_path and os.path.exists(worktree_path):
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
    if (not is_project_chat) and branch and project_path:
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
    cursor.execute("""
        UPDATE project_chat_sessions
        SET status = 'cancelled', last_active_at = NOW(), updated_at = NOW()
        WHERE session_id = %s
    """, (session_id,))
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
        if not _is_noise_event(e.get("content") or "", e.get("role") or "")
    ]


def clear_session_events(session_id: int):
    """清空指定 session 的所有事件记录（保留 session 本身）"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM session_events WHERE session_id = %s", (session_id,))
    cursor.execute("""
        UPDATE project_chat_sessions
        SET last_active_at = NOW(), updated_at = NOW()
        WHERE session_id = %s
    """, (session_id,))
    conn.commit()
    conn.close()


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
        if not _is_noise_event(e.get("content") or "", e.get("role") or "")
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
        VALUES (%s, %s, %s, %s)
    """, (session_id, _detect_event_type(content, role), role, content))
    cursor.execute("""
        UPDATE project_chat_sessions
        SET last_active_at = NOW(), updated_at = NOW()
        WHERE session_id = %s
    """, (session_id,))
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
                # Best-effort: interrupt current generation first to avoid old-turn tail events.
                try:
                    await client.interrupt()
                except Exception as interrupt_error:
                    logger.warning(f"Interrupt before new query failed (continuing): {interrupt_error}")

                # Let SDK receive and persist response in the existing receive_messages loop.
                await client.query(content)
            except Exception as e:
                logger.error(f"Error sending message via SDK: {e}")

        # Safely push the coroutine to the agent's event loop (Fire and Forget)
        asyncio.run_coroutine_threadsafe(_send_msg_task(), target_loop)
    else:
        raise ValueError("No active agent for this session")
