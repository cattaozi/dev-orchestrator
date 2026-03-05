"""
Core dispatcher - Agent scheduling
"""
import subprocess
import os
from pathlib import Path
from typing import Optional
from .database import Database, Session


class Dispatcher:
    """Agent dispatcher"""
    
    def __init__(self, db: Database):
        self.db = db
    
    def dispatch(
        self,
        project_id: int,
        issue_number: int,
        repo_path: str,
        agent: str = "claude-code",
        runtime: str = "tmux"
    ) -> int:
        """Dispatch an agent to work on an issue"""
        
        # Create branch name
        branch = f"task-issue-{issue_number}"
        
        # Create worktree path
        worktree_base = Path.home() / ".dev-orchestrator" / "worktrees"
        worktree_path = worktree_base / f"proj-{project_id}" / branch
        worktree_path.mkdir(parents=True, exist_ok=True)
        
        # Create session record
        session = Session(
            project_id=project_id,
            issue_number=issue_number,
            branch=branch,
            worktree_path=str(worktree_path),
            status="pending",
            agent=agent,
            runtime=runtime
        )
        session_id = self.db.create_session(session)
        
        # Create worktree
        self._create_worktree(repo_path, str(worktree_path), branch)
        
        # Start agent
        self._start_agent(str(worktree_path), agent, issue_number)
        
        # Update session status
        self.db.update_session_status(session_id, "running")
        
        return session_id
    
    def _create_worktree(self, repo_path: str, worktree_path: str, branch: str):
        """Create git worktree"""
        try:
            subprocess.run([
                "git", "-C", repo_path, "worktree", "add", 
                "--track", "-b", branch, worktree_path, "HEAD"
            ], check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            # Worktree might already exist
            print(f"Worktree creation: {e.stderr}")
    
    def _start_agent(self, worktree_path: str, agent: str, issue_number: int):
        """Start the agent in worktree"""
        if agent == "claude-code":
            # Use Claude Code
            env = os.environ.copy()
            env["CLAUDE_CODE_API_KEY"] = os.environ.get("CLAUDE_CODE_API_KEY", "")
            
            # Start in background (in real implementation, use tmux)
            subprocess.Popen(
                ["claude-code", "--no-color"],
                cwd=worktree_path,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
        elif agent == "codex":
            # Use Codex
            subprocess.Popen(
                ["codex", f"Task: Work on issue #{issue_number}"],
                cwd=worktree_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
    
    def send_message(self, session_id: int, message: str):
        """Send message to a running agent"""
        # In real implementation, this would use tmux send-keys or similar
        print(f"Sending to session {session_id}: {message}")
    
    def kill_session(self, session_id: int):
        """Kill a running session"""
        self.db.update_session_status(session_id, "failed")
