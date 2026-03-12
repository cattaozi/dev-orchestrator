# Worker service
from typing import List, Optional
from db import get_db
from psycopg2.extras import RealDictCursor


def list_workers() -> List[dict]:
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("SELECT * FROM workers ORDER BY created_at DESC")
    workers = cursor.fetchall()
    conn.close()
    return [dict(w, created_at=str(w['created_at'])) for w in workers]


def get_worker(worker_id: int) -> Optional[dict]:
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("SELECT * FROM workers WHERE id = %s", (worker_id,))
    worker = cursor.fetchone()
    conn.close()
    if worker:
        return dict(worker, created_at=str(worker['created_at']))
    return None


def create_worker(name: str, emoji: str, agent_type: str, prompt_template: str, prompt_file_path: str = "") -> dict:
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("""
        INSERT INTO workers (name, emoji, agent_type, prompt_template, prompt_file_path)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING *
    """, (name, emoji, agent_type, prompt_template, prompt_file_path))
    new_worker = cursor.fetchone()
    conn.commit()
    conn.close()
    return dict(new_worker, created_at=str(new_worker['created_at']))


def update_worker(worker_id: int, name: str = None, emoji: str = None, agent_type: str = None, prompt_template: str = None, prompt_file_path: str = None, is_builtin: bool = None) -> dict:
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    cursor.execute("SELECT * FROM workers WHERE id = %s", (worker_id,))
    worker = cursor.fetchone()
    if not worker:
        conn.close()
        raise ValueError("Worker not found")

    updates = []
    values = []
    if name is not None:
        updates.append("name = %s")
        values.append(name)
    if emoji is not None:
        updates.append("emoji = %s")
        values.append(emoji)
    if agent_type is not None:
        updates.append("agent_type = %s")
        values.append(agent_type)
    if prompt_template is not None:
        updates.append("prompt_template = %s")
        values.append(prompt_template)
    if prompt_file_path is not None:
        updates.append("prompt_file_path = %s")
        values.append(prompt_file_path)
    if is_builtin is not None:
        updates.append("is_builtin = %s")
        values.append(is_builtin)

    if updates:
        values.append(worker_id)
        cursor.execute(f"UPDATE workers SET {', '.join(updates)} WHERE id = %s RETURNING *", values)
        updated = cursor.fetchone()
        conn.commit()
        conn.close()
        return dict(updated, created_at=str(updated['created_at']))

    conn.close()
    return dict(worker, created_at=str(worker['created_at']))


def delete_worker(worker_id: int):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM workers WHERE id = %s", (worker_id,))
    if not cursor.fetchone():
        conn.close()
        raise ValueError("Worker not found")

    cursor.execute("DELETE FROM workers WHERE id = %s", (worker_id,))
    conn.commit()
    conn.close()


def list_project_workers(project_id: int) -> List[dict]:
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("""
        SELECT pw.id, pw.project_id, pw.worker_id, w.name as worker_name, w.emoji,
               w.agent_type, pw.custom_prompt_template, pw.created_at
        FROM project_workers pw
        JOIN workers w ON pw.worker_id = w.id
        WHERE pw.project_id = %s
        ORDER BY pw.created_at DESC
    """, (project_id,))
    workers = cursor.fetchall()
    conn.close()
    return [dict(w, created_at=str(w['created_at'])) for w in workers]


def create_project_worker(project_id: int, worker_id: int, custom_prompt_template: str) -> dict:
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    cursor.execute("SELECT id FROM projects WHERE id = %s", (project_id,))
    if not cursor.fetchone():
        conn.close()
        raise ValueError("Project not found")

    cursor.execute("SELECT id FROM workers WHERE id = %s", (worker_id,))
    if not cursor.fetchone():
        conn.close()
        raise ValueError("Worker not found")

    cursor.execute("""
        INSERT INTO project_workers (project_id, worker_id, custom_prompt_template)
        VALUES (%s, %s, %s)
        ON CONFLICT (project_id, worker_id)
        DO UPDATE SET custom_prompt_template = EXCLUDED.custom_prompt_template
        RETURNING *
    """, (project_id, worker_id, custom_prompt_template))
    new_pw = cursor.fetchone()

    cursor.execute("SELECT name, emoji, agent_type FROM workers WHERE id = %s", (worker_id,))
    worker = cursor.fetchone()

    conn.commit()
    conn.close()
    return dict(
        id=new_pw['id'],
        project_id=new_pw['project_id'],
        worker_id=new_pw['worker_id'],
        worker_name=worker['name'],
        emoji=worker['emoji'],
        agent_type=worker['agent_type'],
        custom_prompt_template=new_pw['custom_prompt_template'],
        created_at=str(new_pw['created_at'])
    )


def update_project_worker(project_id: int, pw_id: int, custom_prompt_template: str) -> dict:
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    cursor.execute("SELECT * FROM project_workers WHERE id = %s AND project_id = %s", (pw_id, project_id))
    pw = cursor.fetchone()
    if not pw:
        conn.close()
        raise ValueError("Project worker not found")

    cursor.execute(
        "UPDATE project_workers SET custom_prompt_template = %s WHERE id = %s RETURNING *",
        (custom_prompt_template, pw_id)
    )
    updated = cursor.fetchone()
    conn.commit()
    conn.close()
    return dict(updated, created_at=str(updated['created_at']))


def delete_project_worker(project_id: int, pw_id: int):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM project_workers WHERE id = %s AND project_id = %s", (pw_id, project_id))
    if cursor.rowcount == 0:
        conn.close()
        raise ValueError("Project worker not found")

    conn.commit()
    conn.close()


def get_effective_worker(project_id: int, worker_id: int) -> dict:
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    cursor.execute("""
        SELECT pw.*, w.name, w.emoji, w.agent_type, w.prompt_template as base_prompt, w.prompt_file_path
        FROM project_workers pw
        JOIN workers w ON pw.worker_id = w.id
        WHERE pw.project_id = %s AND pw.worker_id = %s
    """, (project_id, worker_id))
    project_worker = cursor.fetchone()

    if project_worker:
        conn.close()
        return {
            "id": project_worker['worker_id'],
            "name": project_worker['name'],
            "emoji": project_worker['emoji'],
            "agent_type": project_worker['agent_type'],
            "prompt_template": project_worker['custom_prompt_template'] or project_worker['base_prompt'],
            "is_builtin": True
        }

    cursor.execute("SELECT * FROM workers WHERE id = %s", (worker_id,))
    worker = cursor.fetchone()
    conn.close()

    if not worker:
        raise ValueError("Worker not found")

    return dict(worker, is_builtin=worker.get('is_builtin', False))


def get_next_worker(project_id: int, issue_id: int) -> dict:
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    cursor.execute("SELECT * FROM issues WHERE id = %s", (issue_id,))
    issue = cursor.fetchone()
    if not issue:
        conn.close()
        return {"error": "Issue not found"}

    cursor.execute("""
        SELECT worker_id FROM sessions
        WHERE issue_id = %s AND worker_id IS NOT NULL
        ORDER BY started_at DESC
        LIMIT 1
    """, (issue_id,))
    last_session = cursor.fetchone()

    cursor.execute("""
        SELECT pw.worker_id, w.name, w.emoji, w.agent_type, pw.custom_prompt_template, w.prompt_template
        FROM project_workers pw
        JOIN workers w ON pw.worker_id = w.id
        WHERE pw.project_id = %s
        ORDER BY pw.created_at
    """, (project_id,))
    project_workers = cursor.fetchall()

    if not project_workers:
        cursor.execute("SELECT * FROM workers ORDER BY created_at")
        project_workers = cursor.fetchall()

    conn.close()

    if last_session and len(project_workers) > 1:
        current_id = last_session['worker_id']
        for i, pw in enumerate(project_workers):
            if pw['worker_id'] == current_id:
                next_idx = (i + 1) % len(project_workers)
                pw = project_workers[next_idx]
                return {
                    "worker_id": pw['worker_id'],
                    "name": pw['name'],
                    "emoji": pw['emoji'],
                    "agent_type": pw['agent_type'],
                    "prompt_template": pw.get('custom_prompt_template') or pw.get('prompt_template', '')
                }

    if project_workers:
        pw = project_workers[0]
        return {
            "worker_id": pw['worker_id'],
            "name": pw['name'],
            "emoji": pw['emoji'],
            "agent_type": pw['agent_type'],
            "prompt_template": pw.get('custom_prompt_template') or pw.get('prompt_template', '')
        }

    return {"error": "No workers available"}