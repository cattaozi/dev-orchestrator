# Project service
import os
import re
import signal
import subprocess
import time
from typing import List, Optional
from db import get_db
from psycopg2.extras import RealDictCursor


def _serialize_project_row(project: dict) -> dict:
    row = dict(project)
    row["status"] = row.get("status") or "active"
    row["created_at"] = str(row["created_at"])
    return row


def list_projects() -> List[dict]:
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("SELECT * FROM projects ORDER BY created_at DESC")
    projects = cursor.fetchall()
    conn.close()
    return [_serialize_project_row(p) for p in projects]


def get_project(project_id: int) -> Optional[dict]:
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("SELECT * FROM projects WHERE id = %s", (project_id,))
    project = cursor.fetchone()
    conn.close()
    if project:
        return _serialize_project_row(project)
    return None


def create_project(name: str, description: str, local_path: str, favorited: bool) -> dict:
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    cursor.execute("SELECT id FROM projects WHERE name = %s", (name,))
    if cursor.fetchone():
        conn.close()
        raise ValueError("Project with this name already exists")

    cursor.execute("""
        INSERT INTO projects (name, description, local_path, favorited)
        VALUES (%s, %s, %s, %s)
        RETURNING *
    """, (name, description or "", local_path, favorited))
    new_project = cursor.fetchone()
    conn.commit()
    conn.close()
    return _serialize_project_row(new_project)


def update_project(project_id: int, name: str, description: str, local_path: str, favorited: bool) -> dict:
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    cursor.execute("SELECT * FROM projects WHERE id = %s", (project_id,))
    if not cursor.fetchone():
        conn.close()
        raise ValueError("Project not found")

    cursor.execute("""
        UPDATE projects SET name = %s, description = %s, local_path = %s, favorited = %s
        WHERE id = %s
        RETURNING *
    """, (name, description, local_path, favorited, project_id))
    updated = cursor.fetchone()
    conn.commit()
    conn.close()
    return _serialize_project_row(updated)


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


def _is_pid_running(pid: Optional[int]) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _resolve_workdir(project_path: str, workdir: Optional[str]) -> str:
    base = os.path.realpath(project_path or "")
    target = os.path.realpath(workdir or project_path or "")
    if not base or not os.path.isdir(base):
        raise ValueError(f"Project local_path not found: {project_path}")
    if not target or not os.path.isdir(target):
        raise ValueError(f"Service workdir not found: {workdir}")
    try:
        common = os.path.commonpath([base, target])
    except ValueError:
        common = ""
    if common != base:
        raise ValueError("Service workdir must be under project local_path")
    return target


def _serialize_project_service(row: dict) -> dict:
    port = row.get("port")
    healthcheck_url = (row.get("healthcheck_url") or "").strip()
    return {
        "id": row["id"],
        "project_id": row["project_id"],
        "name": row["name"],
        "start_command": row["start_command"],
        "stop_command": row.get("stop_command") or "",
        "workdir": row["workdir"],
        "port": port,
        "healthcheck_url": healthcheck_url,
        "url": healthcheck_url or (f"http://localhost:{port}" if port else ""),
        "status": row["status"],
        "pid": row.get("pid"),
        "last_error": row.get("last_error") or "",
        "last_started_at": str(row["last_started_at"]) if row.get("last_started_at") else None,
        "created_at": str(row["created_at"]) if row.get("created_at") else None,
        "updated_at": str(row["updated_at"]) if row.get("updated_at") else None,
    }


def _refresh_managed_service_statuses(cursor, project_id: Optional[int] = None):
    where_sql = "WHERE status = 'running'" if project_id is None else "WHERE status = 'running' AND project_id = %s"
    params = tuple() if project_id is None else (project_id,)
    cursor.execute(
        f"""
        SELECT id, pid FROM project_services
        {where_sql}
        """,
        params,
    )
    rows = cursor.fetchall()
    for row in rows:
        if row.get("pid") and not _is_pid_running(row["pid"]):
            cursor.execute(
                """
                UPDATE project_services
                SET status = 'stopped', pid = NULL, updated_at = NOW()
                WHERE id = %s
                """,
                (row["id"],),
            )


def _collect_listening_processes_by_port() -> dict:
    by_port: dict[int, list] = {}
    for proc in _list_listening_processes():
        pid = proc.get("pid")
        addr = proc.get("name", "")
        if not pid:
            continue
        m = re.search(r":(\d+)$", addr)
        if not m:
            continue
        cwd = _pid_cwd(pid)
        if not cwd:
            continue
        port = int(m.group(1))
        by_port.setdefault(port, []).append(
            {
                "pid": int(pid),
                "cwd": os.path.realpath(cwd),
                "command": proc.get("command") or "",
            }
        )
    return by_port


def _infer_runtime_process(service: dict, by_port: dict) -> Optional[dict]:
    port = service.get("port")
    if not port:
        return None
    candidates = by_port.get(int(port), [])
    if not candidates:
        return None

    service_workdir = os.path.realpath(service.get("workdir") or "")
    if service_workdir:
        for proc in candidates:
            if proc["cwd"].startswith(service_workdir):
                return proc

    if len(candidates) == 1:
        return candidates[0]
    return None


def list_project_services(project_id: int) -> List[dict]:
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("SELECT id FROM projects WHERE id = %s", (project_id,))
    if not cursor.fetchone():
        conn.close()
        raise ValueError("Project not found")

    _refresh_managed_service_statuses(cursor, project_id)
    cursor.execute(
        """
        SELECT *
        FROM project_services
        WHERE project_id = %s
        ORDER BY id ASC
        """,
        (project_id,),
    )
    rows = cursor.fetchall()
    by_port = _collect_listening_processes_by_port()

    for row in rows:
        inferred = _infer_runtime_process(row, by_port)
        if inferred:
            if row.get("status") != "running" or row.get("pid") != inferred["pid"]:
                cursor.execute(
                    """
                    UPDATE project_services
                    SET
                        status = 'running',
                        pid = %s,
                        last_error = '',
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (inferred["pid"], row["id"]),
                )
                row["status"] = "running"
                row["pid"] = inferred["pid"]
        elif row.get("status") == "running" and not _is_pid_running(row.get("pid")):
            cursor.execute(
                """
                UPDATE project_services
                SET status = 'stopped', pid = NULL, updated_at = NOW()
                WHERE id = %s
                """,
                (row["id"],),
            )
            row["status"] = "stopped"
            row["pid"] = None

    conn.commit()
    conn.close()
    return [_serialize_project_service(row) for row in rows]


def create_project_service(
    project_id: int,
    name: str,
    start_command: str,
    stop_command: str,
    workdir: Optional[str],
    port: Optional[int],
    healthcheck_url: str,
) -> dict:
    service_name = (name or "").strip()
    start_cmd = (start_command or "").strip()
    if not service_name:
        raise ValueError("Service name is required")
    if not start_cmd:
        raise ValueError("start_command is required")

    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("SELECT id, local_path FROM projects WHERE id = %s", (project_id,))
    project = cursor.fetchone()
    if not project:
        conn.close()
        raise ValueError("Project not found")

    resolved_workdir = _resolve_workdir(project["local_path"], workdir)
    try:
        cursor.execute(
            """
            INSERT INTO project_services (
                project_id, name, start_command, stop_command, workdir, port, healthcheck_url
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                project_id,
                service_name,
                start_cmd,
                (stop_command or "").strip(),
                resolved_workdir,
                port,
                (healthcheck_url or "").strip(),
            ),
        )
    except Exception as e:
        conn.close()
        if "project_services_project_id_name_key" in str(e):
            raise ValueError("Service with this name already exists")
        raise

    created = cursor.fetchone()
    conn.commit()
    conn.close()
    return _serialize_project_service(created)


def update_project_service(
    project_id: int,
    service_id: int,
    name: str,
    start_command: str,
    stop_command: str,
    workdir: Optional[str],
    port: Optional[int],
    healthcheck_url: str,
) -> dict:
    service_name = (name or "").strip()
    start_cmd = (start_command or "").strip()
    if not service_name:
        raise ValueError("Service name is required")
    if not start_cmd:
        raise ValueError("start_command is required")

    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("SELECT id, local_path FROM projects WHERE id = %s", (project_id,))
    project = cursor.fetchone()
    if not project:
        conn.close()
        raise ValueError("Project not found")
    cursor.execute("SELECT * FROM project_services WHERE id = %s AND project_id = %s", (service_id, project_id))
    existing = cursor.fetchone()
    if not existing:
        conn.close()
        raise ValueError("Service not found")

    resolved_workdir = _resolve_workdir(project["local_path"], workdir)
    cursor.execute(
        """
        UPDATE project_services
        SET
            name = %s,
            start_command = %s,
            stop_command = %s,
            workdir = %s,
            port = %s,
            healthcheck_url = %s,
            updated_at = NOW()
        WHERE id = %s
        RETURNING *
        """,
        (
            service_name,
            start_cmd,
            (stop_command or "").strip(),
            resolved_workdir,
            port,
            (healthcheck_url or "").strip(),
            service_id,
        ),
    )
    updated = cursor.fetchone()
    conn.commit()
    conn.close()
    return _serialize_project_service(updated)


def delete_project_service(project_id: int, service_id: int):
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("SELECT * FROM project_services WHERE id = %s AND project_id = %s", (service_id, project_id))
    service = cursor.fetchone()
    if not service:
        conn.close()
        raise ValueError("Service not found")
    if service.get("status") == "running":
        conn.close()
        raise ValueError("Please stop service before deleting")
    cursor.execute("DELETE FROM project_services WHERE id = %s", (service_id,))
    conn.commit()
    conn.close()


def _get_project_service(cursor, project_id: int, service_id: int) -> tuple[dict, dict]:
    cursor.execute("SELECT id, local_path FROM projects WHERE id = %s", (project_id,))
    project = cursor.fetchone()
    if not project:
        raise ValueError("Project not found")
    cursor.execute("SELECT * FROM project_services WHERE id = %s AND project_id = %s", (service_id, project_id))
    service = cursor.fetchone()
    if not service:
        raise ValueError("Service not found")
    return project, service


def start_project_service(project_id: int, service_id: int) -> dict:
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    project, service = _get_project_service(cursor, project_id, service_id)

    if service.get("status") == "running" and _is_pid_running(service.get("pid")):
        conn.close()
        return _serialize_project_service(service)

    cwd = _resolve_workdir(project["local_path"], service["workdir"])
    process = subprocess.Popen(
        service["start_command"],
        cwd=cwd,
        shell=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        preexec_fn=os.setsid,
    )
    time.sleep(0.35)
    if process.poll() is not None:
        cursor.execute(
            """
            UPDATE project_services
            SET status = 'failed', pid = NULL, last_error = %s, updated_at = NOW()
            WHERE id = %s
            """,
            (f"Process exited with code {process.returncode}", service_id),
        )
    else:
        cursor.execute(
            """
            UPDATE project_services
            SET
                status = 'running',
                pid = %s,
                last_error = '',
                last_started_at = NOW(),
                updated_at = NOW()
            WHERE id = %s
            """,
            (process.pid, service_id),
        )
    cursor.execute("SELECT * FROM project_services WHERE id = %s", (service_id,))
    updated = cursor.fetchone()
    conn.commit()
    conn.close()
    return _serialize_project_service(updated)


def stop_project_service(project_id: int, service_id: int) -> dict:
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    project, service = _get_project_service(cursor, project_id, service_id)
    cwd = _resolve_workdir(project["local_path"], service["workdir"])
    stop_error = ""

    stop_cmd = (service.get("stop_command") or "").strip()
    if stop_cmd:
        try:
            subprocess.run(
                stop_cmd,
                cwd=cwd,
                shell=True,
                check=True,
                capture_output=True,
                timeout=20,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            stop_error = (e.stderr or e.stdout or str(e)).strip()[:500]
        except Exception as e:
            stop_error = str(e)[:500]

    pid = service.get("pid")
    if pid and _is_pid_running(pid):
        try:
            os.killpg(pid, signal.SIGTERM)
            time.sleep(0.4)
            if _is_pid_running(pid):
                os.killpg(pid, signal.SIGKILL)
        except Exception:
            try:
                os.kill(pid, signal.SIGTERM)
            except Exception:
                pass

    cursor.execute(
        """
        UPDATE project_services
        SET
            status = 'stopped',
            pid = NULL,
            last_error = %s,
            updated_at = NOW()
        WHERE id = %s
        RETURNING *
        """,
        (stop_error, service_id),
    )
    updated = cursor.fetchone()
    conn.commit()
    conn.close()
    return _serialize_project_service(updated)


def restart_project_service(project_id: int, service_id: int) -> dict:
    stop_project_service(project_id, service_id)
    return start_project_service(project_id, service_id)


def _list_listening_processes() -> List[dict]:
    """Best-effort detection of listening processes on current host."""
    try:
        result = subprocess.run(
            ["lsof", "-nP", "-iTCP", "-sTCP:LISTEN", "-Fpcn"],
            capture_output=True,
            text=True,
            timeout=4,
            check=True,
        )
    except Exception:
        return []

    processes: List[dict] = []
    current = {"pid": None, "command": "", "name": ""}
    for line in result.stdout.splitlines():
        if not line:
            continue
        prefix, value = line[0], line[1:]
        if prefix == "p":
            if current["pid"] and current["name"]:
                processes.append(current.copy())
            current = {"pid": value, "command": "", "name": ""}
        elif prefix == "c":
            current["command"] = value
        elif prefix == "n":
            current["name"] = value
    if current["pid"] and current["name"]:
        processes.append(current.copy())
    return processes


def _pid_cwd(pid: str) -> Optional[str]:
    try:
        result = subprocess.run(
            ["lsof", "-a", "-p", pid, "-d", "cwd", "-Fn"],
            capture_output=True,
            text=True,
            timeout=2,
            check=True,
        )
    except Exception:
        return None
    for line in result.stdout.splitlines():
        if line.startswith("n"):
            return line[1:]
    return None


def list_project_runtime_services() -> dict:
    """Return runtime services grouped by project_id (managed first, port-aware fallback)."""
    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    cursor.execute("SELECT id, local_path FROM projects")
    projects = cursor.fetchall()
    project_map = {p["id"]: p.get("local_path") for p in projects}

    grouped: dict[int, list] = {pid: [] for pid in project_map.keys()}

    _refresh_managed_service_statuses(cursor)
    cursor.execute(
        """
        SELECT *
        FROM project_services
        WHERE status = 'running'
        ORDER BY id ASC
        """
    )
    managed_rows = cursor.fetchall()
    for row in managed_rows:
        pid = row.get("pid")
        port = row.get("port")
        healthcheck_url = (row.get("healthcheck_url") or "").strip()
        grouped.setdefault(row["project_id"], [])
        grouped[row["project_id"]].append(
            {
                "id": row["id"],
                "name": row["name"],
                "pid": pid,
                "port": port,
                "url": healthcheck_url or (f"http://localhost:{port}" if port else ""),
                "command": row.get("start_command") or "",
                "status": row.get("status") or "running",
                "managed": True,
            }
        )

    # Build expected ports from project service config.
    expected_ports: dict[int, set[int]] = {pid: set() for pid in project_map.keys()}
    cursor.execute(
        """
        SELECT project_id, port, healthcheck_url
        FROM project_services
        """
    )
    for row in cursor.fetchall():
        project_id = row.get("project_id")
        if project_id not in expected_ports:
            continue
        port = row.get("port")
        if port:
            expected_ports[project_id].add(int(port))
        healthcheck_url = (row.get("healthcheck_url") or "").strip()
        if healthcheck_url:
            m = re.search(r":(\d+)", healthcheck_url)
            if m:
                expected_ports[project_id].add(int(m.group(1)))

    detected_grouped: dict[int, list] = {pid: [] for pid in project_map.keys()}
    processes = _list_listening_processes()

    for proc in processes:
        pid = proc.get("pid")
        addr = proc.get("name", "")
        if not pid:
            continue
        m = re.search(r":(\d+)$", addr)
        if not m:
            continue
        port = int(m.group(1))
        cwd = _pid_cwd(pid)
        if not cwd:
            continue

        for project_id, project_path in project_map.items():
            if not project_path:
                continue
            if cwd.startswith(project_path):
                # Only trust ports explicitly configured for this project.
                # This prevents IDE/tooling background ports from being misclassified as project services.
                if port not in expected_ports.get(project_id, set()):
                    continue
                detected_grouped[project_id].append(
                    {
                        "pid": int(pid),
                        "port": port,
                        "url": f"http://localhost:{port}",
                        "command": proc.get("command") or "",
                        "status": "running",
                        "managed": False,
                    }
                )
                break

    # Persist detection snapshot
    cursor.execute("UPDATE project_runtime_services SET status = 'stopped' WHERE status = 'running'")
    for project_id, services in detected_grouped.items():
        for svc in services:
            cursor.execute("""
                INSERT INTO project_runtime_services (project_id, pid, port, url, command, status, last_seen_at)
                VALUES (%s, %s, %s, %s, %s, 'running', NOW())
                ON CONFLICT (project_id, pid, port)
                DO UPDATE SET
                    url = EXCLUDED.url,
                    command = EXCLUDED.command,
                    status = 'running',
                    last_seen_at = NOW()
            """, (project_id, svc["pid"], svc["port"], svc["url"], svc["command"]))

    # Merge detected services only when not already covered by managed ones.
    for project_id, services in detected_grouped.items():
        existing_keys = {(svc.get("pid"), svc.get("port")) for svc in grouped[project_id]}
        for svc in services:
            key = (svc.get("pid"), svc.get("port"))
            if key not in existing_keys:
                grouped[project_id].append(svc)
                existing_keys.add(key)

    conn.commit()
    conn.close()

    result = {}
    for project_id, services in grouped.items():
        result[project_id] = {
            "running": len(services) > 0,
            "count": len(services),
            "services": services,
        }
    return result


def get_dashboard_summary() -> dict:
    runtime_map = list_project_runtime_services()

    running_projects = 0
    running_services = 0
    for runtime in runtime_map.values():
        if runtime.get("running"):
            running_projects += 1
        running_services += int(runtime.get("count", 0))

    conn = get_db()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    cursor.execute("SELECT COUNT(*) AS count FROM projects")
    total_projects = int(cursor.fetchone()["count"])

    cursor.execute("SELECT COUNT(*) AS count FROM issues")
    total_tasks = int(cursor.fetchone()["count"])

    cursor.execute("SELECT COUNT(*) AS count FROM issues WHERE status = 'done'")
    done_tasks = int(cursor.fetchone()["count"])

    cursor.execute("SELECT COUNT(*) AS count FROM issues WHERE status = 'blocked'")
    blocked_tasks = int(cursor.fetchone()["count"])

    cursor.execute("SELECT COUNT(*) AS count FROM issues WHERE status = 'in_progress'")
    in_progress_tasks = int(cursor.fetchone()["count"])

    cursor.execute("SELECT COUNT(*) AS count FROM sessions")
    total_sessions = int(cursor.fetchone()["count"])

    cursor.execute("SELECT COUNT(*) AS count FROM sessions WHERE status IN ('running', 'pending')")
    active_sessions = int(cursor.fetchone()["count"])

    cursor.execute(
        """
        SELECT i.id, i.project_id, i.title, i.status, i.created_at, p.name AS project_name
        FROM issues i
        JOIN projects p ON p.id = i.project_id
        ORDER BY i.created_at DESC
        LIMIT 8
        """
    )
    recent_tasks = [
        {
            "id": row["id"],
            "project_id": row["project_id"],
            "project_name": row["project_name"],
            "title": row["title"],
            "status": row["status"],
            "created_at": str(row["created_at"]) if row.get("created_at") else None,
        }
        for row in cursor.fetchall()
    ]

    cursor.execute(
        """
        SELECT s.id, s.project_id, s.issue_id, s.status, s.started_at, p.name AS project_name
        FROM sessions s
        LEFT JOIN projects p ON p.id = s.project_id
        ORDER BY COALESCE(s.started_at, NOW()) DESC
        LIMIT 8
        """
    )
    recent_sessions = [
        {
            "id": row["id"],
            "project_id": row.get("project_id"),
            "project_name": row.get("project_name") or "Unknown project",
            "task_id": row.get("issue_id"),
            "status": row["status"],
            "started_at": str(row["started_at"]) if row.get("started_at") else None,
        }
        for row in cursor.fetchall()
    ]

    conn.close()

    return {
        "stats": {
            "total_projects": total_projects,
            "running_projects": running_projects,
            "running_services": running_services,
            "total_tasks": total_tasks,
            "done_tasks": done_tasks,
            "blocked_tasks": blocked_tasks,
            "in_progress_tasks": in_progress_tasks,
            "total_sessions": total_sessions,
            "active_sessions": active_sessions,
        },
        "recent_tasks": recent_tasks,
        "recent_sessions": recent_sessions,
    }
