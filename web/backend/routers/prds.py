from fastapi import APIRouter, HTTPException
from typing import List
from services import prd_service
from models import PRDCreate, PRDResponse

router = APIRouter(prefix="/api/projects/{project_id}/prds", tags=["prds"])


@router.get("", response_model=List[PRDResponse])
def list_prds(project_id: int):
    return prd_service.list_prds(project_id)


@router.get("/{prd_id}", response_model=PRDResponse)
def get_prd(project_id: int, prd_id: int):
    prd = prd_service.get_prd(project_id, prd_id)
    if not prd:
        raise HTTPException(status_code=404, detail="PRD not found")
    return prd


@router.post("", response_model=PRDResponse)
def create_prd(project_id: int, prd: PRDCreate):
    try:
        return prd_service.create_prd(project_id, prd.title, prd.version)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))