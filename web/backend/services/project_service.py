# Project service
import os
from typing import List, Optional
from db import get_db
from psycopg2.extras import RealDictCursor


def list_projects() -> List[dict]:
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("SELECT * FROM projects ORDER BY created_at DESC")
    projects = cursor.fetchall()
    conn.close()
    return [dict(p, created_at=str(p['created_at'])) for p in projects]


def get_project(project_id: int) -> Optional[dict]:
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("SELECT * FROM projects WHERE id = %s", (project_id,))
    project = cursor.fetchone()
    conn.close()
    if project:
        return dict(project, created_at=str(project['created_at']))
    return None


def create_project(name: str, description: str, repo: str, local_path: str, default_branch: str, favorited: bool) -> dict:
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    cursor.execute("SELECT id FROM projects WHERE name = %s", (name,))
    if cursor.fetchone():
        conn.close()
        raise ValueError("Project with this name already exists")

    cursor.execute("""
        INSERT INTO projects (name, description, repo, local_path, default_branch, favorited)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING *
    """, (name, description or "", repo or "", local_path, default_branch or "main", favorited))
    new_project = cursor.fetchone()
    conn.commit()
    conn.close()
    return dict(new_project, created_at=str(new_project['created_at']))


def update_project(project_id: int, name: str, description: str, repo: str, local_path: str, default_branch: str, favorited: bool) -> dict:
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    cursor.execute("SELECT * FROM projects WHERE id = %s", (project_id,))
    if not cursor.fetchone():
        conn.close()
        raise ValueError("Project not found")

    cursor.execute("""
        UPDATE projects SET name = %s, description = %s, repo = %s, local_path = %s, default_branch = %s, favorited = %s
        WHERE id = %s
        RETURNING *
    """, (name, description, repo, local_path, default_branch, favorited, project_id))
    updated = cursor.fetchone()
    conn.commit()
    conn.close()
    return dict(updated, created_at=str(updated['created_at']))


def delete_project(project_id: int):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM projects WHERE id = %s", (project_id,))
    if not cursor.fetchone():
        conn.close()
        raise ValueError("Project not found")

    cursor.execute("DELETE FROM projects WHERE id = %s", (project_id,))
    conn.commit()
    conn.close()


def toggle_favorite(project_id: int) -> bool:
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    cursor.execute("SELECT favorited FROM projects WHERE id = %s", (project_id,))
    project = cursor.fetchone()
    if not project:
        conn.close()
        raise ValueError("Project not found")

    new_favorited = not project['favorited']
    cursor.execute("UPDATE projects SET favorited = %s WHERE id = %s", (new_favorited, project_id))
    conn.commit()
    conn.close()
    return new_favorited


def get_project_readme(project_id: int) -> dict:
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("SELECT local_path FROM projects WHERE id = %s", (project_id,))
    project = cursor.fetchone()
    conn.close()

    if not project:
        raise ValueError("Project not found")

    readme_paths = ['README.md', 'README.txt', 'readme.md', 'README.MD', 'CLAUDE.md']
    for readme in readme_paths:
        path = f"{project['local_path']}/{readme}"
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    return {"content": f.read(), "file": readme}
            except Exception:
                continue

    return {"content": "", "file": None}
