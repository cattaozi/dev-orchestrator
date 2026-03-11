from fastapi import APIRouter, HTTPException
from typing import List
from services import issue_service
from models import IssueCreate, IssueUpdate, IssueResponse

router = APIRouter(prefix="/api/projects/{project_id}/issues", tags=["issues"])


@router.get("", response_model=List[IssueResponse])
def list_issues(project_id: int):
    return issue_service.list_issues(project_id)


@router.get("/{issue_id}", response_model=IssueResponse)
def get_issue(project_id: int, issue_id: int):
    issue = issue_service.get_issue(project_id, issue_id)
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")
    return issue


@router.post("", response_model=IssueResponse)
def create_issue(project_id: int, issue: IssueCreate):
    try:
        return issue_service.create_issue(project_id, issue.title, issue.content)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.patch("/{issue_id}", response_model=IssueResponse)
def update_issue(project_id: int, issue_id: int, issue_update: IssueUpdate):
    try:
        return issue_service.update_issue(
            project_id, issue_id,
            title=issue_update.title,
            content=issue_update.content,
            status=issue_update.status
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{issue_id}")
def delete_issue(project_id: int, issue_id: int):
    try:
        issue_service.delete_issue(project_id, issue_id)
        return {"message": "Issue deleted"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{issue_id}/worktree")
def delete_issue_worktree(project_id: int, issue_id: int):
    """删除 issue 的 worktree"""
    try:
        issue_service.delete_issue_worktree(project_id, issue_id)
        return {"message": "Worktree deleted"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{issue_id}/branch")
def delete_issue_branch(project_id: int, issue_id: int):
    """删除 issue 的分支"""
    try:
        issue_service.delete_issue_branch(project_id, issue_id)
        return {"message": "Branch deleted"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))