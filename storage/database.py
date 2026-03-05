"""
Database models and storage using PostgreSQL + SQLAlchemy
"""
import os
from datetime import datetime
from typing import Optional
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.pool import NullPool

# PostgreSQL connection
DATABASE_URL = os.environ.get(
    "DATABASE_URL", 
    "postgresql://postgres:postgres@localhost:5432/dev_orchestrator"
)

engine = create_engine(DATABASE_URL, poolclass=NullPool)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Project(Base):
    __tablename__ = "projects"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, nullable=False)
    repo = Column(String, nullable=False)
    local_path = Column(String, nullable=False)
    default_branch = Column(String, default="main")
    config_yaml = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, onupdate=datetime.utcnow)
    
    sessions = relationship("Session", back_populates="project")
    stories = relationship("Story", back_populates="project")


class Session(Base):
    __tablename__ = "sessions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id"))
    issue_number = Column(Integer, nullable=False)
    branch = Column(String, nullable=False)
    worktree_path = Column(String, nullable=False)
    status = Column(String, default="pending")  # pending/running/done/failed
    agent = Column(String, nullable=False)
    runtime = Column(String, default="tmux")
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    
    project = relationship("Project", back_populates="sessions")
    events = relationship("Event", back_populates="session")


class Story(Base):
    __tablename__ = "stories"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey("projects.id"))
    story_id = Column(String, nullable=False)
    title = Column(String)
    status = Column(String, default="pending")  # pending/in_progress/awaiting_acceptance/accepted/done
    depends_on = Column(Text, default="[]")  # JSON array
    source_file = Column(String)
    completed_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    project = relationship("Project", back_populates="stories")
    issues = relationship("StoryIssue", back_populates="story")


class StoryIssue(Base):
    __tablename__ = "story_issues"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    story_id = Column(Integer, ForeignKey("stories.id"))
    repo = Column(String, nullable=False)
    issue_number = Column(Integer, nullable=False)
    merged = Column(Boolean, default=False)
    
    story = relationship("Story", back_populates="issues")


class Event(Base):
    __tablename__ = "events"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("sessions.id"))
    type = Column(String, nullable=False)  # created/started/pr_created/merged/failed
    payload = Column(Text)  # JSON
    created_at = Column(DateTime, default=datetime.utcnow)
    
    session = relationship("Session", back_populates="events")


def init_db():
    """Initialize database tables"""
    Base.metadata.create_all(bind=engine)


def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Convenience functions
def create_project(name: str, repo: str, local_path: str, default_branch: str = "main", config_yaml: str = "") -> Project:
    db = SessionLocal()
    project = Project(
        name=name, 
        repo=repo, 
        local_path=local_path, 
        default_branch=default_branch,
        config_yaml=config_yaml
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    db.close()
    return project


def get_project(name: str) -> Optional[Project]:
    db = SessionLocal()
    project = db.query(Project).filter(Project.name == name).first()
    db.close()
    return project


def list_projects() -> list[Project]:
    db = SessionLocal()
    projects = db.query(Project).order_by(Project.created_at.desc()).all()
    db.close()
    return projects


def create_session(project_id: int, issue_number: int, branch: str, worktree_path: str, agent: str, runtime: str = "tmux") -> Session:
    db = SessionLocal()
    session = Session(
        project_id=project_id,
        issue_number=issue_number,
        branch=branch,
        worktree_path=worktree_path,
        agent=agent,
        runtime=runtime
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    db.close()
    return session


def update_session_status(session_id: int, status: str):
    db = SessionLocal()
    session = db.query(Session).filter(Session.id == session_id).first()
    if session:
        session.status = status
        if status == "running":
            session.started_at = datetime.utcnow()
        elif status in ("done", "failed"):
            session.completed_at = datetime.utcnow()
        db.commit()
    db.close()


def create_story(project_id: int, story_id: str, title: str, depends_on: str = "[]", source_file: str = "") -> Story:
    db = SessionLocal()
    story = Story(
        project_id=project_id,
        story_id=story_id,
        title=title,
        depends_on=depends_on,
        source_file=source_file
    )
    db.add(story)
    db.commit()
    db.refresh(story)
    db.close()
    return story


def get_ready_stories(project_id: int) -> list[Story]:
    """Get stories with all dependencies completed"""
    import json
    db = SessionLocal()
    stories = db.query(Story).filter(
        Story.project_id == project_id,
        Story.status.notin_(["done", "accepted"])
    ).all()
    
    ready = []
    for story in stories:
        deps = json.loads(story.depends_on) if story.depends_on else []
        if not deps:
            ready.append(story)
        else:
            completed = db.query(Story).filter(
                Story.project_id == project_id,
                Story.story_id.in_(deps),
                Story.status.in_(["done", "accepted"])
            ).count()
            if completed == len(deps):
                ready.append(story)
    
    db.close()
    return ready
