"""
Unit tests for storage/database.py
"""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime


# Mock the database before importing the module
@pytest.fixture(autouse=True)
def mock_database():
    """Mock the database connection and session"""
    with patch('storage.database.create_engine') as mock_engine, \
         patch('storage.database.sessionmaker') as mock_sessionmaker, \
         patch('storage.database.SessionLocal') as mock_session_local:

        # Setup mock session
        mock_session = MagicMock()
        mock_session_local.return_value = mock_session

        # Store mock session for tests
        mock_database.mock_session = mock_session

        yield mock_session


class TestProject:
    """Tests for Project model operations"""

    def test_create_project(self, mock_database):
        """Test creating a new project"""
        from storage.database import create_project

        # Setup mock
        mock_database.add = MagicMock()
        mock_database.commit = MagicMock()
        mock_database.refresh = MagicMock()
        mock_database.close = MagicMock()

        # Create a mock project object
        mock_project = MagicMock()
        mock_project.id = 1
        mock_project.name = "Test Project"
        mock_project.repo = "https://github.com/test/repo"
        mock_project.local_path = "/data/repo/test"
        mock_project.default_branch = "main"
        mock_project.created_at = datetime.utcnow()
        mock_database.refresh.side_effect = lambda x: setattr(x, 'id', 1)

        # Execute
        with patch.object(mock_database, 'query') as mock_query:
            mock_result = MagicMock()
            mock_result.first.return_value = None
            mock_query.return_value = mock_result

            project = create_project("Test Project", "https://github.com/test/repo", "/data/repo/test")

        # Verify
        mock_database.add.assert_called_once()
        mock_database.commit.assert_called_once()
        mock_database.close.assert_called_once()

    def test_get_project(self, mock_database):
        """Test getting a project by name"""
        from storage.database import get_project

        # Setup mock
        mock_database.query.return_value.filter.return_value.first.return_value = None
        mock_database.close = MagicMock()

        # Execute
        result = get_project("NonExistent")

        # Verify
        mock_database.close.assert_called_once()
        assert result is None

    def test_list_projects(self, mock_database):
        """Test listing all projects"""
        from storage.database import list_projects

        # Setup mock
        mock_projects = [MagicMock(), MagicMock()]
        mock_database.query.return_value.order_by.return_value.all.return_value = mock_projects
        mock_database.close = MagicMock()

        # Execute
        result = list_projects()

        # Verify
        mock_database.close.assert_called_once()
        assert len(result) == 2


class TestSession:
    """Tests for Session model operations"""

    def test_create_session(self, mock_database):
        """Test creating a new session"""
        from storage.database import create_session

        # Setup mock
        mock_database.add = MagicMock()
        mock_database.commit = MagicMock()
        mock_database.refresh = MagicMock()
        mock_database.close = MagicMock()
        mock_database.refresh.side_effect = lambda x: setattr(x, 'id', 1)

        # Execute
        session = create_session(
            project_id=1,
            issue_number=1,
            branch="feature/test",
            worktree_path="/data/repo/test",
            agent="claude-code",
            runtime="tmux"
        )

        # Verify
        mock_database.add.assert_called_once()
        mock_database.commit.assert_called_once()
        mock_database.close.assert_called_once()

    def test_update_session_status_pending(self, mock_database):
        """Test updating session status to pending"""
        from storage.database import update_session_status

        # Setup mock
        mock_session = MagicMock()
        mock_session.status = "pending"
        mock_session.started_at = None
        mock_session.completed_at = None
        mock_database.query.return_value.filter.return_value.first.return_value = mock_session
        mock_database.commit = MagicMock()
        mock_database.close = MagicMock()

        # Execute
        update_session_status(1, "pending")

        # Verify
        assert mock_session.status == "pending"
        mock_database.commit.assert_called_once()
        mock_database.close.assert_called_once()

    def test_update_session_status_running(self, mock_database):
        """Test updating session status to running (should set started_at)"""
        from storage.database import update_session_status

        # Setup mock
        mock_session = MagicMock()
        mock_session.status = "pending"
        mock_session.started_at = None
        mock_database.query.return_value.filter.return_value.first.return_value = mock_session
        mock_database.commit = MagicMock()
        mock_database.close = MagicMock()

        # Execute
        update_session_status(1, "running")

        # Verify
        assert mock_session.status == "running"
        assert mock_session.started_at is not None
        mock_database.commit.assert_called_once()
        mock_database.close.assert_called_once()

    def test_update_session_status_done(self, mock_database):
        """Test updating session status to done (should set completed_at)"""
        from storage.database import update_session_status

        # Setup mock
        mock_session = MagicMock()
        mock_session.status = "running"
        mock_session.completed_at = None
        mock_database.query.return_value.filter.return_value.first.return_value = mock_session
        mock_database.commit = MagicMock()
        mock_database.close = MagicMock()

        # Execute
        update_session_status(1, "done")

        # Verify
        assert mock_session.status == "done"
        assert mock_session.completed_at is not None
        mock_database.commit.assert_called_once()
        mock_database.close.assert_called_once()

    def test_update_session_status_failed(self, mock_database):
        """Test updating session status to failed (should set completed_at)"""
        from storage.database import update_session_status

        # Setup mock
        mock_session = MagicMock()
        mock_session.status = "running"
        mock_session.completed_at = None
        mock_database.query.return_value.filter.return_value.first.return_value = mock_session
        mock_database.commit = MagicMock()
        mock_database.close = MagicMock()

        # Execute
        update_session_status(1, "failed")

        # Verify
        assert mock_session.status == "failed"
        assert mock_session.completed_at is not None
        mock_database.commit.assert_called_once()
        mock_database.close.assert_called_once()

    def test_update_session_not_found(self, mock_database):
        """Test updating session that doesn't exist"""
        from storage.database import update_session_status

        # Setup mock
        mock_database.query.return_value.filter.return_value.first.return_value = None
        mock_database.commit = MagicMock()
        mock_database.close = MagicMock()

        # Execute - should not raise error
        update_session_status(999, "done")

        # Verify
        mock_database.commit.assert_not_called()
        mock_database.close.assert_called_once()


class TestStory:
    """Tests for Story model operations"""

    def test_create_story(self, mock_database):
        """Test creating a new story"""
        from storage.database import create_story

        # Setup mock
        mock_database.add = MagicMock()
        mock_database.commit = MagicMock()
        mock_database.refresh = MagicMock()
        mock_database.close = MagicMock()
        mock_database.refresh.side_effect = lambda x: setattr(x, 'id', 1)

        # Execute
        story = create_story(
            project_id=1,
            story_id="STORY-001",
            title="Test Story",
            depends_on="[]",
            source_file="stories/test.md"
        )

        # Verify
        mock_database.add.assert_called_once()
        mock_database.commit.assert_called_once()
        mock_database.close.assert_called_once()

    def test_get_ready_stories_no_dependencies(self, mock_database):
        """Test getting stories with no dependencies"""
        from storage.database import get_ready_stories

        # Setup mock
        mock_stories = [MagicMock(), MagicMock()]
        for story in mock_stories:
            story.depends_on = "[]"

        mock_database.query.return_value.filter.return_value.all.return_value = mock_stories
        mock_database.close = MagicMock()

        # Execute
        result = get_ready_stories(1)

        # Verify
        mock_database.close.assert_called_once()
        assert len(result) == 2

    def test_get_ready_stories_with_dependencies_all_completed(self, mock_database):
        """Test getting stories with all dependencies completed"""
        from storage.database import get_ready_stories

        # Setup mock - story with dependencies
        mock_story = MagicMock()
        mock_story.depends_on = '["STORY-001", "STORY-002"]'

        mock_database.query.return_value.filter.return_value.all.side_effect = [
            [mock_story],  # First call returns stories
            [MagicMock(), MagicMock()]  # Second call returns completed dependencies
        ]
        mock_database.query.return_value.filter.return_value.count.return_value = 2
        mock_database.close = MagicMock()

        # Execute
        result = get_ready_stories(1)

        # Verify
        mock_database.close.assert_called_once()
        assert len(result) == 1

    def test_get_ready_stories_with_dependencies_incomplete(self, mock_database):
        """Test getting stories with incomplete dependencies"""
        from storage.database import get_ready_stories

        # Setup mock - story with dependencies
        mock_story = MagicMock()
        mock_story.depends_on = '["STORY-001", "STORY-002"]'

        mock_database.query.return_value.filter.return_value.all.side_effect = [
            [mock_story],  # First call returns stories
            [MagicMock()]  # Second call returns only 1 completed dependency
        ]
        mock_database.query.return_value.filter.return_value.count.return_value = 1
        mock_database.close = MagicMock()

        # Execute
        result = get_ready_stories(1)

        # Verify
        mock_database.close.assert_called_once()
        assert len(result) == 0

    def test_get_ready_stories_empty(self, mock_database):
        """Test getting ready stories when none exist"""
        from storage.database import get_ready_stories

        # Setup mock
        mock_database.query.return_value.filter.return_value.all.return_value = []
        mock_database.close = MagicMock()

        # Execute
        result = get_ready_stories(1)

        # Verify
        mock_database.close.assert_called_once()
        assert len(result) == 0


class TestDatabaseInit:
    """Tests for database initialization"""

    def test_init_db(self, mock_database):
        """Test database initialization"""
        from storage.database import init_db, Base

        # Setup mock
        with patch.object(Base.metadata, 'create_all') as mock_create_all:
            # Execute
            init_db()

            # Verify
            mock_create_all.assert_called_once()
