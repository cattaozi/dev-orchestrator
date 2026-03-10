from fastapi import APIRouter, HTTPException
from typing import List
from services import project_service
from models import ProjectCreate, ProjectResponse

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("", response_model=List[ProjectResponse])
def list_projects():
    return project_service.list_projects()


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
            project_update.repo,
            project_update.local_path,
            project_update.default_branch,
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
            project.repo,
            project.local_path,
            project.default_branch,
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