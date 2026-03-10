# PRD service
from typing import List, Optional
from db import get_db
from psycopg2.extras import RealDictCursor


def list_prds(project_id: int) -> List[dict]:
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("SELECT * FROM prds WHERE project_id = %s ORDER BY created_at DESC", (project_id,))
    prds = cursor.fetchall()
    conn.close()
    return [dict(p, created_at=str(p['created_at'])) for p in prds]


def get_prd(project_id: int, prd_id: int) -> Optional[dict]:
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("SELECT * FROM prds WHERE id = %s AND project_id = %s", (prd_id, project_id))
    prd = cursor.fetchone()
    conn.close()
    if prd:
        return dict(prd, created_at=str(prd['created_at']))
    return None


def create_prd(project_id: int, title: str, version: str) -> dict:
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    cursor.execute("SELECT id FROM projects WHERE id = %s", (project_id,))
    if not cursor.fetchone():
        conn.close()
        raise ValueError("Project not found")

    cursor.execute("""
        INSERT INTO prds (project_id, title, version)
        VALUES (%s, %s, %s)
        RETURNING *
    """, (project_id, title, version))
    new_prd = cursor.fetchone()
    conn.commit()
    conn.close()
    return dict(new_prd, created_at=str(new_prd['created_at']))