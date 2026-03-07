"""
Unit tests for storage/database.py
"""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime


class TestConvenienceFunctions:
    """Tests for convenience functions"""

    @patch('storage.database.SessionLocal')
    def test_create_project(self, mock_session_local):
        """Test create_project function"""
        from storage.database import create_project

        # Setup mock
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db

        # Execute
        project = create_project(
            name="Test Project",
            repo="https://github.com/test/repo",
            local_path="/data/repo/test"
        )

        # Verify
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.close.assert_called_once()

    @patch('storage.database.SessionLocal')
    def test_get_project(self, mock_session_local):
        """Test get_project function"""
        from storage.database import get_project

        # Setup mock
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db
        mock_db.query.return_value.filter.return_value.first.return_value = None

        # Execute
        result = get_project("NonExistent")

        # Verify
        mock_db.close.assert_called_once()
        assert result is None

    @patch('storage.database.SessionLocal')
    def test_get_project_found(self, mock_session_local):
        """Test get_project function when project exists"""
        from storage.database import get_project

        # Setup mock
        mock_db = MagicMock()
        mock_project = MagicMock()
        mock_project.name = "Test Project"
        mock_session_local.return_value = mock_db
        mock_db.query.return_value.filter.return_value.first.return_value = mock_project

        # Execute
        result = get_project("Test Project")

        # Verify
        mock_db.close.assert_called_once()
        assert result is not None
        assert result.name == "Test Project"

    @patch('storage.database.SessionLocal')
    def test_list_projects(self, mock_session_local):
        """Test list_projects function"""
        from storage.database import list_projects

        # Setup mock
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db
        mock_db.query.return_value.order_by.return_value.all.return_value = []

        # Execute
        result = list_projects()

        # Verify
        mock_db.close.assert_called_once()
        assert isinstance(result, list)

    @patch('storage.database.SessionLocal')
    def test_create_session(self, mock_session_local):
        """Test create_session function"""
        from storage.database import create_session

        # Setup mock
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db

        # Execute
        session = create_session(
            project_id=1,
            issue_number=1,
            branch="feature/test",
            worktree_path="/data/repo/test",
            agent="claude-code"
        )

        # Verify
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.close.assert_called_once()

    @patch('storage.database.SessionLocal')
    def test_update_session_status_pending(self, mock_session_local):
        """Test update_session_status to pending"""
        from storage.database import update_session_status

        # Setup mock
        mock_db = MagicMock()
        mock_session = MagicMock()
        mock_session.status = "running"
        mock_db.query.return_value.filter.return_value.first.return_value = mock_session
        mock_session_local.return_value = mock_db

        # Execute
        update_session_status(1, "pending")

        # Verify
        assert mock_session.status == "pending"
        mock_db.commit.assert_called_once()
        mock_db.close.assert_called_once()

    @patch('storage.database.SessionLocal')
    def test_update_session_status_running(self, mock_session_local):
        """Test update_session_status to running (sets started_at)"""
        from storage.database import update_session_status

        # Setup mock
        mock_db = MagicMock()
        mock_session = MagicMock()
        mock_session.status = "pending"
        mock_session.started_at = None
        mock_db.query.return_value.filter.return_value.first.return_value = mock_session
        mock_session_local.return_value = mock_db

        # Execute
        update_session_status(1, "running")

        # Verify
        assert mock_session.status == "running"
        assert mock_session.started_at is not None
        mock_db.commit.assert_called_once()
        mock_db.close.assert_called_once()

    @patch('storage.database.SessionLocal')
    def test_update_session_status_done(self, mock_session_local):
        """Test update_session_status to done (sets completed_at)"""
        from storage.database import update_session_status

        # Setup mock
        mock_db = MagicMock()
        mock_session = MagicMock()
        mock_session.status = "running"
        mock_session.completed_at = None
        mock_db.query.return_value.filter.return_value.first.return_value = mock_session
        mock_session_local.return_value = mock_db

        # Execute
        update_session_status(1, "done")

        # Verify
        assert mock_session.status == "done"
        assert mock_session.completed_at is not None
        mock_db.commit.assert_called_once()
        mock_db.close.assert_called_once()

    @patch('storage.database.SessionLocal')
    def test_update_session_status_failed(self, mock_session_local):
        """Test update_session_status to failed"""
        from storage.database import update_session_status

        # Setup mock
        mock_db = MagicMock()
        mock_session = MagicMock()
        mock_session.status = "running"
        mock_session.completed_at = None
        mock_db.query.return_value.filter.return_value.first.return_value = mock_session
        mock_session_local.return_value = mock_db

        # Execute
        update_session_status(1, "failed")

        # Verify
        assert mock_session.status == "failed"
        assert mock_session.completed_at is not None
        mock_db.commit.assert_called_once()
        mock_db.close.assert_called_once()

    @patch('storage.database.SessionLocal')
    def test_update_session_not_found(self, mock_session_local):
        """Test update_session_status when session not found"""
        from storage.database import update_session_status

        # Setup mock
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_session_local.return_value = mock_db

        # Execute - should not raise
        update_session_status(999, "done")

        # Verify
        mock_db.commit.assert_not_called()
        mock_db.close.assert_called_once()

    @patch('storage.database.SessionLocal')
    def test_create_story(self, mock_session_local):
        """Test create_story function"""
        from storage.database import create_story

        # Setup mock
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db

        # Execute
        story = create_story(
            project_id=1,
            story_id="STORY-001",
            title="Test Story"
        )

        # Verify
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.close.assert_called_once()

    @patch('storage.database.SessionLocal')
    def test_get_ready_stories_no_dependencies(self, mock_session_local):
        """Test get_ready_stories function with no dependencies"""
        from storage.database import get_ready_stories

        # Setup mock
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db
        mock_story = MagicMock()
        mock_story.depends_on = "[]"
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_story]

        # Execute
        result = get_ready_stories(1)

        # Verify
        mock_db.close.assert_called_once()
        assert len(result) == 1

    @patch('storage.database.SessionLocal')
    def test_get_ready_stories_with_dependencies_completed(self, mock_session_local):
        """Test get_ready_stories function with completed dependencies"""
        from storage.database import get_ready_stories

        # Setup mock
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db
        mock_story = MagicMock()
        mock_story.depends_on = '["STORY-001", "STORY-002"]'

        # First query returns the story, second query returns completed dependencies
        mock_db.query.return_value.filter.return_value.all.side_effect = [
            [mock_story],
            [MagicMock(), MagicMock()]  # Both dependencies completed
        ]
        mock_db.query.return_value.filter.return_value.count.return_value = 2

        # Execute
        result = get_ready_stories(1)

        # Verify
        mock_db.close.assert_called_once()
        assert len(result) == 1

    @patch('storage.database.SessionLocal')
    def test_get_ready_stories_with_dependencies_incomplete(self, mock_session_local):
        """Test get_ready_stories function with incomplete dependencies"""
        from storage.database import get_ready_stories

        # Setup mock
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db
        mock_story = MagicMock()
        mock_story.depends_on = '["STORY-001", "STORY-002"]'

        mock_db.query.return_value.filter.return_value.all.side_effect = [
            [mock_story],
            [MagicMock()]  # Only 1 dependency completed
        ]
        mock_db.query.return_value.filter.return_value.count.return_value = 1

        # Execute
        result = get_ready_stories(1)

        # Verify
        mock_db.close.assert_called_once()
        assert len(result) == 0

    @patch('storage.database.SessionLocal')
    def test_get_ready_stories_empty_result(self, mock_session_local):
        """Test get_ready_stories function with no stories"""
        from storage.database import get_ready_stories

        # Setup mock
        mock_db = MagicMock()
        mock_session_local.return_value = mock_db
        mock_db.query.return_value.filter.return_value.all.return_value = []

        # Execute
        result = get_ready_stories(1)

        # Verify
        mock_db.close.assert_called_once()
        assert len(result) == 0
