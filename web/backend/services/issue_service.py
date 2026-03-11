# Issue service
from typing import List, Optional
import os
import subprocess
import re
from loguru import logger

from db import get_db
from psycopg2.extras import RealDictCursor


def _validate_path(path: str) -> bool:
    """校验路径安全：防止路径遍历攻击"""
    if not path:
        return False
    if '..' in path:
        return False
    if path.startswith('/') and not path.startswith('/home/claude/worktrees/'):
        return False
    return True


def _validate_branch_name(branch: str) -> bool:
    """校验分支名安全：防止命令注入"""
    if not branch:
        return False
    if not re.match(r'^[a-zA-Z0-9][a-zA-Z0-9/_.-]*$', branch):
        return False
    return True


def list_issues(project_id: int) -> List[dict]:
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("SELECT * FROM issues WHERE project_id = %s ORDER BY created_at DESC", (project_id,))
    issues = cursor.fetchall()
    conn.close()
    return [dict(i, created_at=str(i['created_at'])) for i in issues]


def get_issue(project_id: int, issue_id: int) -> Optional[dict]:
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("SELECT * FROM issues WHERE id = %s AND project_id = %s", (issue_id, project_id))
    issue = cursor.fetchone()
    conn.close()
    if issue:
        return dict(issue, created_at=str(issue['created_at']))
    return None


def create_issue(project_id: int, title: str, content: str) -> dict:
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    cursor.execute("SELECT id FROM projects WHERE id = %s", (project_id,))
    if not cursor.fetchone():
        conn.close()
        raise ValueError("Project not found")

    cursor.execute("""
        INSERT INTO issues (project_id, title, content, status)
        VALUES (%s, %s, %s, 'pending')
        RETURNING *
    """, (project_id, title, content))
    new_issue = cursor.fetchone()
    conn.commit()
    conn.close()
    return dict(new_issue, created_at=str(new_issue['created_at']))


def update_issue(project_id: int, issue_id: int, title: str = None, content: str = None, status: str = None) -> dict:
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    cursor.execute("SELECT * FROM issues WHERE id = %s AND project_id = %s", (issue_id, project_id))
    issue = cursor.fetchone()
    if not issue:
        conn.close()
        raise ValueError("Issue not found")

    updates = []
    values = []
    if title is not None:
        updates.append("title = %s")
        values.append(title)
    if content is not None:
        updates.append("content = %s")
        values.append(content)
    if status is not None:
        updates.append("status = %s")
        values.append(status)

    if updates:
        values.append(issue_id)
        cursor.execute(f"UPDATE issues SET {', '.join(updates)} WHERE id = %s RETURNING *", values)
        updated_issue = cursor.fetchone()
        conn.commit()
        conn.close()
        return dict(updated_issue, created_at=str(updated_issue['created_at']))

    conn.close()
    return dict(issue, created_at=str(issue['created_at']))


def delete_issue(project_id: int, issue_id: int):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM issues WHERE id = %s AND project_id = %s", (issue_id, project_id))
    if not cursor.fetchone():
        conn.close()
        raise ValueError("Issue not found")

    cursor.execute("DELETE FROM issues WHERE id = %s", (issue_id,))
    conn.commit()
    conn.close()


def delete_issue_worktree(project_id: int, issue_id: int):
    """删除 issue 的 worktree"""
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    # 获取 issue 和 project 信息
    cursor.execute("SELECT * FROM issues WHERE id = %s AND project_id = %s", (issue_id, project_id))
    issue = cursor.fetchone()
    if not issue:
        conn.close()
        raise ValueError("Issue not found")

    worktree_path = issue.get('worktree')
    if not worktree_path:
        conn.close()
        raise ValueError("No worktree to delete")

    # 安全校验
    if not _validate_path(worktree_path):
        conn.close()
        raise ValueError(f"Invalid worktree path: {worktree_path}")

    # 删除 worktree
    if os.path.exists(worktree_path):
        try:
            subprocess.run(
                ["git", "worktree", "remove", "--force", worktree_path],
                capture_output=True,
                check=True
            )
            logger.info(f"Deleted worktree: {worktree_path}")
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to delete worktree: {e.stderr}")
            conn.close()
            raise RuntimeError(f"Failed to delete worktree: {e.stderr.decode() if e.stderr else str(e)}")

    # 更新数据库
    cursor.execute("UPDATE issues SET worktree = NULL, worktree_state = NULL WHERE id = %s", (issue_id,))
    conn.commit()
    conn.close()


def delete_issue_branch(project_id: int, issue_id: int):
    """删除 issue 的分支"""
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    # 获取 issue 和 project 信息
    cursor.execute("SELECT * FROM issues WHERE id = %s AND project_id = %s", (issue_id, project_id))
    issue = cursor.fetchone()
    if not issue:
        conn.close()
        raise ValueError("Issue not found")

    branch = issue.get('branch')
    if not branch:
        conn.close()
        raise ValueError("No branch to delete")

    # 获取 project 路径
    cursor.execute("SELECT local_path FROM projects WHERE id = %s", (project_id,))
    project = cursor.fetchone()
    if not project or not project.get('local_path'):
        conn.close()
        raise ValueError("Project path not found")

    project_path = project['local_path']

    # 安全校验
    if not _validate_branch_name(branch):
        conn.close()
        raise ValueError(f"Invalid branch name: {branch}")

    # 删除分支
    try:
        subprocess.run(
            ["git", "branch", "-D", branch],
            cwd=project_path,
            capture_output=True,
            check=True
        )
        logger.info(f"Deleted branch: {branch}")
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to delete branch: {e.stderr}")
        conn.close()
        raise RuntimeError(f"Failed to delete branch: {e.stderr.decode() if e.stderr else str(e)}")

    # 更新数据库
    cursor.execute("UPDATE issues SET branch = NULL, branch_state = NULL WHERE id = %s", (issue_id,))
    conn.commit()
    conn.close()