# Config service
from db import get_db
from psycopg2.extras import RealDictCursor


def get_config() -> dict:
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("SELECT key, value FROM config")
    config = cursor.fetchall()
    conn.close()
    return {c["key"]: c["value"] for c in config}


def update_config(config_data: dict):
    conn = get_db()
    cursor = conn.cursor()

    for key, value in config_data.items():
        cursor.execute("""
            INSERT INTO config (key, value)
            VALUES (%s, %s)
            ON CONFLICT (key)
            DO UPDATE SET value = EXCLUDED.value
        """, (key, value))

    conn.commit()
    conn.close()