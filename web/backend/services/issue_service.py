# Issue service
from typing import List, Optional
from db import get_db
from psycopg2.extras import RealDictCursor


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
        INSERT INTO issues (project_id, title, content)
        VALUES (%s, %s, %s)
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