from pydantic import BaseModel
from typing import Optional


# Project Models
class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None
    repo: str = ""
    local_path: str
    default_branch: str = "main"
    favorited: bool = False


class ProjectResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    repo: str
    local_path: str
    status: str
    favorited: bool = False
    created_at: str


# Session Models
class SessionResponse(BaseModel):
    id: int
    issue_id: int
    project_id: int
    branch: str
    worktree_path: str
    status: str
    agent_type: str
    worker_id: Optional[int] = None
    runtime: Optional[str] = None
    command: Optional[str] = None
    prompt: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class SessionCreate(BaseModel):
    issue_id: int
    worker_id: Optional[int] = None
    runtime: Optional[str] = "agent-sdk"


# Worker Models
class WorkerResponse(BaseModel):
    id: int
    name: str
    emoji: str
    agent_type: str
    prompt_template: str
    prompt_file_path: str = ""
    is_builtin: bool = False


class WorkerCreate(BaseModel):
    name: str
    emoji: str = ""
    agent_type: str = "claude-code"
    prompt_template: str = ""
    prompt_file_path: str = ""


class WorkerUpdate(BaseModel):
    name: Optional[str] = None
    emoji: Optional[str] = None
    agent_type: Optional[str] = None
    prompt_template: Optional[str] = None
    prompt_file_path: Optional[str] = None
    is_builtin: Optional[bool] = None


class ProjectWorkerCreate(BaseModel):
    project_id: int
    worker_id: int
    custom_prompt_template: str = ""


class ProjectWorkerUpdate(BaseModel):
    custom_prompt_template: Optional[str] = None


class ProjectWorkerResponse(BaseModel):
    id: int
    project_id: int
    worker_id: int
    worker_name: Optional[str] = None
    emoji: Optional[str] = None
    agent_type: Optional[str] = None
    custom_prompt_template: str
    created_at: str


# PRD Models
class PRDCreate(BaseModel):
    project_id: int
    title: str
    version: str = "v1.0"


class PRDResponse(BaseModel):
    id: int
    project_id: int
    title: str
    version: str
    status: str
    created_at: str


# Issue Models
class IssueCreate(BaseModel):
    title: str
    content: str


class IssueUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    status: Optional[str] = None


class IssueResponse(BaseModel):
    id: int
    project_id: int
    title: Optional[str] = None
    content: Optional[str] = None
    status: str
    worktree: Optional[str] = None
    branch: Optional[str] = None
    worktree_state: Optional[str] = None
    branch_state: Optional[str] = None
    created_at: str


# Message Model for session communication
class MessageInput(BaseModel):
    role: str
    content: str