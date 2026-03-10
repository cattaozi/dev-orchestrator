from fastapi import APIRouter, HTTPException
from typing import List
from services import worker_service
from models import WorkerResponse, WorkerCreate, WorkerUpdate, ProjectWorkerCreate, ProjectWorkerUpdate, ProjectWorkerResponse

router = APIRouter(tags=["workers"])


# Global worker endpoints
@router.get("/api/workers", response_model=List[WorkerResponse])
def list_workers():
    return worker_service.list_workers()


@router.post("/api/workers", response_model=WorkerResponse)
def create_worker(worker: WorkerCreate):
    try:
        return worker_service.create_worker(worker.name, worker.emoji, worker.agent_type, worker.prompt_template)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/api/workers/{worker_id}", response_model=WorkerResponse)
def get_worker(worker_id: int):
    worker = worker_service.get_worker(worker_id)
    if not worker:
        raise HTTPException(status_code=404, detail="Worker not found")
    return worker


@router.put("/api/workers/{worker_id}", response_model=WorkerResponse)
def update_worker(worker_id: int, worker_update: WorkerUpdate):
    try:
        return worker_service.update_worker(
            worker_id,
            name=worker_update.name,
            emoji=worker_update.emoji,
            agent_type=worker_update.agent_type,
            prompt_template=worker_update.prompt_template,
            is_builtin=worker_update.is_builtin
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/api/workers/{worker_id}")
def delete_worker(worker_id: int):
    try:
        worker_service.delete_worker(worker_id)
        return {"message": "Worker deleted"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# Project worker endpoints
@router.get("/api/projects/{project_id}/workers", response_model=List[ProjectWorkerResponse])
def list_project_workers(project_id: int):
    return worker_service.list_project_workers(project_id)


@router.post("/api/projects/{project_id}/workers", response_model=ProjectWorkerResponse)
def create_project_worker(project_id: int, pw: ProjectWorkerCreate):
    try:
        return worker_service.create_project_worker(project_id, pw.worker_id, pw.custom_prompt_template)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/api/projects/{project_id}/workers/{pw_id}", response_model=ProjectWorkerResponse)
def update_project_worker(project_id: int, pw_id: int, pw_update: ProjectWorkerUpdate):
    try:
        return worker_service.update_project_worker(project_id, pw_id, pw_update.custom_prompt_template)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/api/projects/{project_id}/workers/{pw_id}")
def delete_project_worker(project_id: int, pw_id: int):
    try:
        worker_service.delete_project_worker(project_id, pw_id)
        return {"message": "Project worker deleted"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/api/projects/{project_id}/workers/{worker_id}/effective", response_model=WorkerResponse)
def get_effective_worker(project_id: int, worker_id: int):
    try:
        return worker_service.get_effective_worker(project_id, worker_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/api/projects/{project_id}/issues/{issue_id}/next-worker")
def get_next_worker(project_id: int, issue_id: int):
    return worker_service.get_next_worker(project_id, issue_id)