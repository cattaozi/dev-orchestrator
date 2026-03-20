from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List
from services import project_service, session_service
from models import ProjectCreate, ProjectResponse, ProjectChatSessionResponse, SessionResponse

router = APIRouter(prefix="/api/projects", tags=["projects"])


class ProjectChatSessionCreate(BaseModel):
    worker_id: int | None = None
    runtime: str = "agent-sdk"
    force_new: bool = False


class ProjectServiceCreate(BaseModel):
    name: str
    start_command: str
    stop_command: str = ""
    workdir: str | None = None
    port: int | None = None
    healthcheck_url: str = ""


class ProjectServiceUpdate(BaseModel):
    name: str
    start_command: str
    stop_command: str = ""
    workdir: str | None = None
    port: int | None = None
    healthcheck_url: str = ""


@router.get("", response_model=List[ProjectResponse])
def list_projects():
    return project_service.list_projects()


@router.get("/runtime-services")
def list_project_runtime_services():
    return project_service.list_project_runtime_services()


@router.get("/dashboard-summary")
def get_dashboard_summary():
    return project_service.get_dashboard_summary()


@router.get("/{project_id}/services")
def list_project_services(project_id: int):
    try:
        return project_service.list_project_services(project_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{project_id}/services")
def create_project_service(project_id: int, service: ProjectServiceCreate):
    try:
        return project_service.create_project_service(
            project_id=project_id,
            name=service.name,
            start_command=service.start_command,
            stop_command=service.stop_command,
            workdir=service.workdir,
            port=service.port,
            healthcheck_url=service.healthcheck_url,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{project_id}/services/{service_id}")
def update_project_service(project_id: int, service_id: int, service: ProjectServiceUpdate):
    try:
        return project_service.update_project_service(
            project_id=project_id,
            service_id=service_id,
            name=service.name,
            start_command=service.start_command,
            stop_command=service.stop_command,
            workdir=service.workdir,
            port=service.port,
            healthcheck_url=service.healthcheck_url,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{project_id}/services/{service_id}")
def delete_project_service(project_id: int, service_id: int):
    try:
        project_service.delete_project_service(project_id, service_id)
        return {"message": "Service deleted"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{project_id}/services/{service_id}/start")
def start_project_service(project_id: int, service_id: int):
    try:
        return project_service.start_project_service(project_id, service_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{project_id}/services/{service_id}/stop")
def stop_project_service(project_id: int, service_id: int):
    try:
        return project_service.stop_project_service(project_id, service_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{project_id}/services/{service_id}/restart")
def restart_project_service(project_id: int, service_id: int):
    try:
        return project_service.restart_project_service(project_id, service_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(project_id: int):
    project = project_service.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.put("/{project_id}", response_model=ProjectResponse)
def update_project(project_id: int, project_update: ProjectCreate):
    try:
        return project_service.update_project(
            project_id,
            project_update.name,
            project_update.description,
            project_update.local_path,
            project_update.favorited
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{project_id}/readme")
def get_project_readme(project_id: int):
    try:
        return project_service.get_project_readme(project_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("", response_model=ProjectResponse)
def create_project(project: ProjectCreate):
    try:
        return project_service.create_project(
            project.name,
            project.description,
            project.local_path,
            project.favorited
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{project_id}")
def delete_project(project_id: int):
    try:
        project_service.delete_project(project_id)
        return {"message": "Project deleted"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{project_id}/favorite")
def toggle_favorite(project_id: int):
    try:
        favorited = project_service.toggle_favorite(project_id)
        return {"favorited": favorited}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{project_id}/chat-session", response_model=ProjectChatSessionResponse)
def get_project_chat_session(project_id: int):
    try:
        return session_service.get_project_chat_session(project_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{project_id}/chat-session", response_model=SessionResponse)
def create_project_chat_session(project_id: int, body: ProjectChatSessionCreate):
    try:
        return session_service.create_project_chat_session(
            project_id, body.worker_id, body.runtime, body.force_new
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
