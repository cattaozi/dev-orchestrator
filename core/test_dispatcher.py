"""
Unit tests for core/dispatcher.py
"""
import pytest
from unittest.mock import patch, MagicMock


class TestDispatcherMethods:
    """Tests for dispatcher helper methods"""

    def test_send_message(self):
        """Test sending a message to a session"""
        from core.dispatcher import Dispatcher

        dispatcher = Dispatcher(None)
        # This is a simple print-based implementation
        dispatcher.send_message(1, "test message")

    @patch('core.dispatcher.update_session_status')
    def test_kill_session(self, mock_update):
        """Test killing a session"""
        from core.dispatcher import Dispatcher

        dispatcher = Dispatcher(None)
        dispatcher.kill_session(1)

        mock_update.assert_called_with(1, "failed")

    @patch('core.dispatcher.subprocess.run')
    def test_create_worktree(self, mock_run):
        """Test worktree creation"""
        from core.dispatcher import Dispatcher

        mock_run.return_value = MagicMock()

        dispatcher = Dispatcher(None)
        dispatcher._create_worktree("/data/repo/test-repo", "/tmp/worktree", "feature/test")

        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert "worktree" in call_args
        assert "add" in call_args

    @patch('core.dispatcher.subprocess.run')
    def test_create_worktree_error_handling(self, mock_run):
        """Test worktree creation error handling"""
        from core.dispatcher import Dispatcher
        from subprocess import CalledProcessError

        mock_run.side_effect = CalledProcessError(1, "git", stderr="Worktree already exists")

        # Should not raise
        dispatcher = Dispatcher(None)
        dispatcher._create_worktree("/data/repo/test-repo", "/tmp/worktree", "feature/test")

    @patch('core.dispatcher.subprocess.Popen')
    def test_start_agent_claude_code(self, mock_popen):
        """Test starting Claude Code agent"""
        from core.dispatcher import Dispatcher

        mock_popen.return_value = MagicMock()

        with patch('core.dispatcher.os.environ') as mock_env:
            mock_env.copy.return_value = {}

            dispatcher = Dispatcher(None)
            dispatcher._start_agent("/tmp/worktree", "claude-code", 1)

            mock_popen.assert_called_once()

    @patch('core.dispatcher.subprocess.Popen')
    def test_start_agent_codex(self, mock_popen):
        """Test starting Codex agent"""
        from core.dispatcher import Dispatcher

        mock_popen.return_value = MagicMock()

        dispatcher = Dispatcher(None)
        dispatcher._start_agent("/tmp/worktree", "codex", 42)

        mock_popen.assert_called_once()
        # Verify issue number is in the command
        call_args = mock_popen.call_args[0][0]
        assert any("42" in str(arg) for arg in call_args)
